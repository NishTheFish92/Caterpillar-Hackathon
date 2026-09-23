"""
train_estimation_model.py
--------------------------
Trains the Task Time Estimation regression model on `task_features.csv`
(produced by feature_engineering/build_features.py) and saves it as a
scikit-learn Pipeline (preprocessing + model bundled together) so the API
can call `.predict(df)` directly on raw feature columns at request time.

Also saves a small metadata JSON with the feature schema, dataset-wide
default values (used when a request doesn't supply operator_id/machine_id
to look real experience/machine-age up from), and holdout metrics — the
API reads this at startup instead of hardcoding any of it.

Run:
    python ml/train_estimation_model.py --data-dir data --out-dir ml/models
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL_FEATURES = [
    "task_type", "environmental_condition", "terrain_type",
    "certification_level", "machine_type", "site_traffic_density",
]
NUMERIC_FEATURES = [
    "experience_years", "machine_age_years", "machine_health_score",
    "ambient_temp_c", "visibility_pct",
]
TARGET = "actual_duration_min"


def build_pipeline():
    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERIC_FEATURES),
    ])
    model = RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=3,
                                   random_state=42, n_jobs=-1)
    return Pipeline([("preprocess", preprocess), ("model", model)])


def main(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(os.path.join(data_dir, "task_features.csv"))
    df = df.dropna(subset=[TARGET] + CATEGORICAL_FEATURES + NUMERIC_FEATURES)

    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    # Refit on the full dataset for the deployed model (the split above was
    # only to get an honest, reportable holdout metric).
    pipeline_full = build_pipeline()
    pipeline_full.fit(X, y)

    model_path = os.path.join(out_dir, "task_time_model.joblib")
    joblib.dump(pipeline_full, model_path)

    defaults = {
        "experience_years": round(float(df["experience_years"].median()), 1),
        "machine_age_years": round(float(df["machine_age_years"].median()), 1),
        "machine_health_score": round(float(df["machine_health_score"].median()), 1),
        "ambient_temp_c": round(float(df["ambient_temp_c"].median()), 1),
        "visibility_pct": round(float(df["visibility_pct"].median()), 1),
        "certification_level": df["certification_level"].mode().iat[0],
        "machine_type": df["machine_type"].mode().iat[0],
        "site_traffic_density": df["site_traffic_density"].mode().iat[0],
    }

    meta = {
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "target": TARGET,
        "defaults": defaults,
        "holdout_mae_min": round(mae, 2),
        "holdout_r2": round(r2, 3),
        "n_train_rows": int(len(df)),
    }
    with open(os.path.join(out_dir, "task_time_model_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Trained on {len(df)} tasks. Holdout MAE: {mae:.1f} min, R^2: {r2:.3f}")
    print(f"Saved model -> {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="ml/models")
    args = parser.parse_args()
    main(args.data_dir, args.out_dir)
