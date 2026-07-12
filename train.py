"""Train the ChainGuard risk model, top to bottom, one script.

Reads the raw Ethereum Fraud Detection CSV, cleans it, engineers two ratio
features, trains a calibrated LightGBM classifier, and writes every artifact
`app/scoring.py` needs at serve time. Run once, offline: `python train.py`.
The container never runs this file.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path("data/raw/transaction_dataset.csv")
MODELS_DIR = Path("models")
RANDOM_STATE = 42

# The two engineered ratios — the raw 12 behavioural columns are resolved by
# name *after* slugifying, not hand-typed, because the source CSV's headers
# are inconsistently cased and spaced (see the slugify step below).
ENGINEERED_COLUMNS = ["send_receive_ratio", "counterparty_reuse"]


def slugify(col: str) -> str:
    """Turn a raw, inconsistently formatted CSV header into snake_case."""
    col = re.sub(r"[^0-9a-zA-Z]+", "_", col.strip())
    col = re.sub(r"_+", "_", col).strip("_")
    return col.lower()


def load_clean_frame() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

    # Drop the stray index columns before anything else touches column names.
    df = df.drop(columns=[c for c in ("Unnamed: 0", "Index") if c in df.columns])

    df.columns = [slugify(c) for c in df.columns]

    # Dedupe on address *before* splitting — duplicate rows landing in both
    # train and test are the single biggest source of fake accuracy here.
    before = len(df)
    df = df.drop_duplicates(subset="address", keep="first").reset_index(drop=True)
    print(f"Dropped {before - len(df)} duplicate address rows ({before} -> {len(df)})")

    df["send_receive_ratio"] = df["sent_tnx"] / (df["received_tnx"] + 1)
    df["counterparty_reuse"] = df["unique_sent_to_addresses"] / (df["sent_tnx"] + 1)

    return df


def resolve_base_feature_columns(df: pd.DataFrame) -> list[str]:
    """Map the spec's 12 behavioural columns onto their slugified names.

    The source CSV spells some headers with "val" and others with "value"
    (e.g. "min val sent" vs "min value received") — an artifact of the raw
    data noted in README.md, not something to paper over by hand-typing a
    different string here. This resolves each intended column by slugifying
    the same raw header the dataset actually uses.
    """
    raw_headers = [
        "Sent tnx",
        "Received Tnx",
        "Unique Sent To Addresses",
        "Unique Received From Addresses",
        "Avg min between sent tnx",
        "Avg min between received tnx",
        "Time Diff between first and last (Mins)",
        "min val sent",
        "max val sent",
        "avg val sent",
        "avg val received",
        "total ether balance",
    ]
    resolved = [slugify(h) for h in raw_headers]
    missing = [h for h, r in zip(raw_headers, resolved) if r not in df.columns]
    if missing:
        raise KeyError(f"Expected columns missing after slugify: {missing}")
    return resolved


def derive_thresholds(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float]:
    """Derive band thresholds from the precision-recall curve, not round numbers.

    `high`   = the lowest score at which precision first reaches 0.90.
    `medium` = the highest score for which recall is still at least 0.80
               (i.e. the point above which recall drops below 0.80).
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    precision, recall = precision[:-1], recall[:-1]  # align with `thresholds`

    high_idx = np.where(precision >= 0.90)[0]
    high = float(thresholds[high_idx[0]]) if len(high_idx) else float(thresholds[-1])

    medium_idx = np.where(recall >= 0.80)[0]
    medium = float(thresholds[medium_idx[-1]]) if len(medium_idx) else float(thresholds[0])

    # The calibrated score for this model is heavily bimodal (most addresses
    # land near 0 or 1, with a thin band of genuinely uncertain scores in
    # between), so the precision curve can clear 0.90 before recall drops
    # below 0.80 — i.e. the two crossings can come out with `medium` above
    # `high`. Enforce `high >= medium` by construction so the band is never
    # empty; both numbers still come straight off the PR curve, just labelled
    # by relative order rather than by which condition produced which value.
    high, medium = max(high, medium), min(high, medium)

    return {"high": round(high, 4), "medium": round(medium, 4)}


def recall_at_precision(y_true: np.ndarray, y_score: np.ndarray, target_precision: float) -> float:
    precision, recall, _ = precision_recall_curve(y_true, y_score)
    idx = np.where(precision[:-1] >= target_precision)[0]
    return float(recall[:-1][idx[0]]) if len(idx) else 0.0


def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    order = np.argsort(-y_score)[:k]
    return float(np.mean(np.asarray(y_true)[order]))


def main() -> None:
    MODELS_DIR.mkdir(exist_ok=True)

    df = load_clean_frame()
    base_cols = resolve_base_feature_columns(df)
    feature_cols = base_cols + ENGINEERED_COLUMNS

    X = df[feature_cols].to_numpy(dtype=float)
    y = df["flag"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    print(f"\nSplit: {len(X_train)} train / {len(X_test)} test "
          f"({y_train.mean():.1%} / {y_test.mean():.1%} positive)")

    # --- 5-fold stratified CV on the train half, LightGBM, PR-AUC ----------
    cv_model = LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=31,
        min_child_samples=30, subsample=0.9, colsample_bytree=0.8,
        class_weight="balanced", random_state=RANDOM_STATE, verbose=-1,
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_scores = cross_val_score(cv_model, X_train, y_train, cv=cv, scoring="average_precision")
    print(f"5-fold CV PR-AUC (train half): {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    # --- Baseline: logistic regression, standardised features ---------------
    baseline = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE),
    )
    baseline.fit(X_train, y_train)
    baseline_scores = baseline.predict_proba(X_test)[:, 1]
    baseline_pr_auc = average_precision_score(y_test, baseline_scores)
    print(f"\nBaseline (LogisticRegression) PR-AUC on test: {baseline_pr_auc:.4f}")

    # --- LightGBM, held out 15% of train for isotonic calibration ----------
    X_fit, X_calib, y_fit, y_calib = train_test_split(
        X_train, y_train, test_size=0.15, stratify=y_train, random_state=RANDOM_STATE
    )
    lgbm = LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=31,
        min_child_samples=30, subsample=0.9, colsample_bytree=0.8,
        class_weight="balanced", random_state=RANDOM_STATE, verbose=-1,
    )
    lgbm.fit(X_fit, y_fit)

    raw_test_scores = lgbm.predict_proba(X_test)[:, 1]
    lgbm_pr_auc = average_precision_score(y_test, raw_test_scores)
    print(f"LightGBM (uncalibrated) PR-AUC on test:  {lgbm_pr_auc:.4f}")
    if lgbm_pr_auc <= baseline_pr_auc:
        raise SystemExit(
            "LightGBM did not beat the logistic baseline on PR-AUC — "
            "something is wrong with the features. Stopping before calibration."
        )
    print("LightGBM clears the baseline.")

    brier_before = brier_score_loss(y_test, raw_test_scores)

    # CalibratedClassifierCV(method="isotonic", cv="prefit") — using the
    # FrozenEstimator wrapper, sklearn 1.6's non-deprecated spelling of
    # "prefit". Fit on the 15% calibration slice held out above.
    calibrated = CalibratedClassifierCV(FrozenEstimator(lgbm), method="isotonic")
    calibrated.fit(X_calib, y_calib)
    isotonic = calibrated.calibrated_classifiers_[0].calibrators[0]

    calibrated_test_scores = isotonic.predict(raw_test_scores)
    brier_after = brier_score_loss(y_test, calibrated_test_scores)
    print(f"\nBrier score before calibration: {brier_before:.4f}")
    print(f"Brier score after calibration:  {brier_after:.4f}")
    if brier_after >= brier_before:
        raise SystemExit("Calibration did not improve the Brier score. Stopping.")
    print("Calibration improves the Brier score.")

    # --- Metrics on test, using the calibrated score ------------------------
    pr_auc = average_precision_score(y_test, calibrated_test_scores)
    roc_auc = roc_auc_score(y_test, calibrated_test_scores)
    p_at_100 = precision_at_k(y_test, calibrated_test_scores, 100)
    recall_at_90p = recall_at_precision(y_test, calibrated_test_scores, 0.90)

    decision_threshold = 0.5
    preds_at_threshold = (calibrated_test_scores >= decision_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, preds_at_threshold).ravel()

    thresholds = derive_thresholds(y_test, calibrated_test_scores)

    print(f"\nPR-AUC (calibrated):            {pr_auc:.4f}")
    print(f"ROC-AUC (calibrated):           {roc_auc:.4f}")
    print(f"Precision@100:                  {p_at_100:.4f}")
    print(f"Recall at 90% precision:        {recall_at_90p:.4f}")
    print(f"Confusion matrix @ {decision_threshold}: tn={tn} fp={fp} fn={fn} tp={tp}")
    print(f"Derived thresholds: {thresholds}")

    # --- Save artifacts -------------------------------------------------------
    # `lgbm` (fit on X_fit/y_fit) and `isotonic` (fit on X_calib/y_calib) are
    # exactly the pair the metrics above were computed with — ship that pair,
    # not a retrain, so the committed artifacts match the reported numbers.
    lgbm.booster_.save_model(str(MODELS_DIR / "model.txt"))
    joblib.dump(isotonic, MODELS_DIR / "calibrator.joblib")

    features_table = df[["address", "flag"] + feature_cols].set_index("address")
    features_table.to_parquet(MODELS_DIR / "features.parquet")

    with open(MODELS_DIR / "columns.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    metrics = {
        "trained_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "n_rows": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "positive_rate": round(float(y.mean()), 4),
        "cv_pr_auc_mean": round(float(cv_scores.mean()), 4),
        "cv_pr_auc_std": round(float(cv_scores.std()), 4),
        "baseline_logreg_pr_auc": round(float(baseline_pr_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "roc_auc": round(float(roc_auc), 4),
        "precision_at_100": round(float(p_at_100), 4),
        "recall_at_90_precision": round(float(recall_at_90p), 4),
        "brier_before_calibration": round(float(brier_before), 4),
        "brier_after_calibration": round(float(brier_after), 4),
        "confusion_matrix": {
            "threshold": decision_threshold,
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        },
    }
    with open(MODELS_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(MODELS_DIR / "thresholds.json", "w") as f:
        json.dump(thresholds, f, indent=2)

    print(f"\nArtifacts written to {MODELS_DIR}/")


if __name__ == "__main__":
    main()
