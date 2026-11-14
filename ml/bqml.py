"""Render the BigQuery ML SQL templates in ml/sql/ with run parameters.

The same renderer is meant to be used from the command line (manual runs) and
from the Airflow DAG, so both execute identical SQL. Templates use
string.Template placeholders such as ${horizon_minutes}.

Example:
    python ml/bqml.py 01_split --horizon-minutes 1440 > split.sql
"""
from __future__ import annotations

import argparse
import string
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"

DEFAULTS = {
    "project": "ba882-bluebikes-pipeline",
    "dataset": "ml_models",
    "source": "ml.station_availability_training_ready",
    "horizon_minutes": "1440",
    # Last N hours of origins are held out as the final test set.
    "test_hours": "36",
    # Validation window (origins) used for model and threshold selection.
    "val_hours": "24",
    # Must match dbt var availability_label_tolerance_minutes.
    "label_tolerance_minutes": "15",
    # Boosted-tree training keeps every Nth five-minute origin slot (3 = every 15 min).
    # Adjacent snapshots are near-duplicates, and boosted-tree training is billed per
    # byte processed at a much higher rate than ordinary queries.
    "boosted_origin_step": "3",
    # Rider-facing metric: how many of the top-K stations flagged at each prediction time were really empty.
    "top_k": "50",
    # Comma-separated models scored in 04_score (each must exist as {name}_h{horizon}).
    "models": "logreg,boosted",
}

STEPS = sorted(p.stem for p in SQL_DIR.glob("*.sql"))

_PREDICT_BLOCK = """union all
select '{name}', split, prediction_id, station_id, no_bike,
  (select prob from unnest(predicted_no_bike_probs) where label = 1)
from ml.predict(model `{project}.{dataset}.{name}_h{horizon_minutes}`, (select * from eval_rows))"""


def render(step: str, **overrides: object) -> str:
    params = {**DEFAULTS, **{k: str(v) for k, v in overrides.items() if v is not None}}
    params["model_predictions"] = "\n".join(
        _PREDICT_BLOCK.format(name=name.strip(), **params)
        for name in params["models"].split(",") if name.strip()
    )
    template = string.Template((SQL_DIR / f"{step}.sql").read_text(encoding="utf-8"))
    return template.substitute(params)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=STEPS)
    for key in DEFAULTS:
        parser.add_argument(f"--{key.replace('_', '-')}", dest=key)
    args = vars(parser.parse_args())
    step = args.pop("step")
    print(render(step, **args))


if __name__ == "__main__":
    main()
