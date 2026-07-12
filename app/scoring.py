"""Loads the trained artifacts once and scores individual addresses.

Everything here is read-only after `load()` runs: the booster, the isotonic
calibrator, the SHAP explainer built from that same booster, and the
in-memory feature table. `app/main.py` calls `load()` once from a FastAPI
`lifespan` handler and reuses the resulting `ModelBundle` for every request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
import shap

MODELS_DIR = Path("models")

REQUIRED_FILES = [
    "model.txt",
    "calibrator.joblib",
    "features.parquet",
    "columns.json",
    "metrics.json",
    "thresholds.json",
]

DISCLAIMER = (
    "Risk scores describe patterns in publicly reported data. "
    "They are not an accusation and not financial advice."
)

# Every one of the 14 model features, in both directions. A positive SHAP
# contribution ("raises") reads through the first phrase; a negative one
# ("lowers") reads through the second. Every phrase is an observation about
# activity, not a judgement about the address behind it.
FACTS: dict[str, dict[str, str]] = {
    "sent_tnx": {
        "raises": "Sends an unusually high number of outgoing transactions",
        "lowers": "Sends relatively few outgoing transactions",
    },
    "received_tnx": {
        "raises": "Receives an unusually high number of incoming transactions",
        "lowers": "Receives relatively few incoming transactions",
    },
    "unique_sent_to_addresses": {
        "raises": "Sends to a very large number of distinct addresses",
        "lowers": "Sends to a small, concentrated set of addresses",
    },
    "unique_received_from_addresses": {
        "raises": "Receives from a very large number of distinct addresses",
        "lowers": "Receives from a small, concentrated set of addresses",
    },
    "avg_min_between_sent_tnx": {
        "raises": "Very short gaps between outgoing transactions",
        "lowers": "Long, irregular gaps between outgoing transactions",
    },
    "avg_min_between_received_tnx": {
        "raises": "Very short gaps between incoming transactions",
        "lowers": "Long, irregular gaps between incoming transactions",
    },
    "time_diff_between_first_and_last_mins": {
        "raises": "Short total lifetime of activity",
        "lowers": "Long, sustained history of activity",
    },
    "min_val_sent": {
        "raises": "Even its smallest outgoing transfer moved a large amount",
        "lowers": "Its smallest outgoing transfer moved very little",
    },
    "max_val_sent": {
        "raises": "Has made at least one very large outgoing transfer",
        "lowers": "Has never made a large single outgoing transfer",
    },
    "avg_val_sent": {
        "raises": "Moves large amounts on average with each outgoing transfer",
        "lowers": "Moves only small amounts with each outgoing transfer",
    },
    "avg_val_received": {
        "raises": "Receives large amounts on average with each incoming transfer",
        "lowers": "Receives only small amounts with each incoming transfer",
    },
    "total_ether_balance": {
        "raises": "Balance near zero despite high throughput",
        "lowers": "Retains a substantial balance rather than moving funds through",
    },
    "send_receive_ratio": {
        "raises": "Sends far more often than it receives",
        "lowers": "Receives about as often as it sends, or more",
    },
    "counterparty_reuse": {
        "raises": "Sends to many addresses it never interacts with again",
        "lowers": "Interacts with a small set of repeat counterparties",
    },
}


@dataclass
class ModelBundle:
    booster: lgb.Booster
    calibrator: object
    explainer: shap.TreeExplainer
    features: pd.DataFrame
    columns: list[str]
    thresholds: dict[str, float]
    metrics: dict

    @classmethod
    def load(cls) -> "ModelBundle | None":
        if not all((MODELS_DIR / name).exists() for name in REQUIRED_FILES):
            return None

        booster = lgb.Booster(model_file=str(MODELS_DIR / "model.txt"))
        calibrator = joblib.load(MODELS_DIR / "calibrator.joblib")
        features = pd.read_parquet(MODELS_DIR / "features.parquet")
        columns = json.loads((MODELS_DIR / "columns.json").read_text())
        metrics = json.loads((MODELS_DIR / "metrics.json").read_text())
        thresholds = json.loads((MODELS_DIR / "thresholds.json").read_text())
        explainer = shap.TreeExplainer(booster)

        return cls(booster, calibrator, explainer, features, columns, thresholds, metrics)

    def band(self, score: float) -> str:
        if score >= self.thresholds["high"]:
            return "high"
        if score >= self.thresholds["medium"]:
            return "medium"
        return "low"

    def examples(self) -> list[str]:
        """3 real dataset addresses: 1 flagged, 2 not. Deterministic, labels hidden."""
        flagged = self.features[self.features["flag"] == 1].index
        clean = self.features[self.features["flag"] == 0].index
        return [flagged[0], clean[0], clean[1]]

    def score_address(self, address: str) -> dict | None:
        key = address.lower()
        if key not in self.features.index:
            return None
        row = self.features.loc[key]

        x = row[self.columns].to_numpy(dtype=float).reshape(1, -1)
        raw_score = float(self.booster.predict(x)[0])
        calibrated = float(self.calibrator.predict([raw_score])[0])
        calibrated = min(max(calibrated, 0.0), 1.0)

        shap_row = self.explainer.shap_values(x)[0]
        top_idx = sorted(range(len(self.columns)), key=lambda i: -abs(shap_row[i]))[:3]
        reasons = [
            {
                "fact": FACTS[self.columns[i]]["raises" if shap_row[i] > 0 else "lowers"],
                "weight": round(float(shap_row[i]), 4),
                "direction": "raises" if shap_row[i] > 0 else "lowers",
            }
            for i in top_idx
        ]

        activity = {
            "sent": int(row["sent_tnx"]),
            "received": int(row["received_tnx"]),
            "unique_counterparties": int(
                row["unique_sent_to_addresses"] + row["unique_received_from_addresses"]
            ),
            "lifetime_days": int(round(row["time_diff_between_first_and_last_mins"] / 1440)),
        }

        return {
            "address": key,
            "risk_score": round(calibrated, 4),
            "risk_band": self.band(calibrated),
            "top_reasons": reasons,
            "activity": activity,
            "disclaimer": DISCLAIMER,
        }
