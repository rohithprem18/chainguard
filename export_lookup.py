"""Precompute every dataset address's score into models/lookup.json.gz.

The full `ModelBundle` (LightGBM, isotonic calibrator, SHAP) scores each
address here, once, offline. The result is a gzipped JSON table that
`app/lookup.py` can serve with nothing but the standard library, which is
how the app runs on hosts whose function size limit rules out the ML stack
(Vercel). Scores are byte-for-byte what the live model returns.
"""

from __future__ import annotations

import gzip
import json

from app.scoring import DISCLAIMER, MODELS_DIR, ModelBundle

OUT = MODELS_DIR / "lookup.json.gz"


def main() -> None:
    bundle = ModelBundle.load()
    if bundle is None:
        raise SystemExit("models/ is incomplete. Run `make train` first.")

    scores = {}
    for address in bundle.features.index:
        result = bundle.score_address(address)
        scores[result["address"]] = {
            "risk_score": result["risk_score"],
            "risk_band": result["risk_band"],
            "top_reasons": result["top_reasons"],
            "activity": result["activity"],
        }

    payload = {
        "disclaimer": DISCLAIMER,
        "metrics": bundle.metrics,
        "thresholds": bundle.thresholds,
        "examples": bundle.examples(),
        "scores": scores,
    }
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    print(f"Wrote {len(scores)} scores to {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
