"""
train_safety_model.py
-----------------------
Trains the Safety hazard-PREDICTION model on `hazard_training_data.csv`
(produced by feature_engineering/build_features.py): given a rolling
5-minute window of telemetry (closing distance to a hazard, proximity
alert rate, speed, seatbelt/idle rates) plus machine/site context, predict
whether a proximity-alert episode occurs in the NEXT 5 minutes.

Important: this model's prediction is NOT the final word. Per the
functional spec, its output only becomes a surfaced "predicted hazard"
after passing back through a rule-based gate at request time (see
backend/routers/safety.py::_apply_hazard_gate) - the model raises
candidates, rules decide what's actually shown as a hazard.

Run:
    python ml/train_safety_model.py --data-dir data --out-dir ml/models
"""

import argparse
import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL_FEATURES = ["site_traffic_density"]
NUMERIC_FEATURES = [
    "avg_distance_5min", "min_distance_5min", "distance_trend_5min",
    "proximity_rate_5min", "avg_speed_5min", "seatbelt_off_rate_5min", "idle_rate_5min",
    "machine_health_score", "visibility_pct", "ambient_temp_c",
]
TARGET = "hazard_next_5min"


def build_pipeline():
    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERIC_FEATURES),
    ])
    model = RandomForestClassifier(
        n_estimators=300, max_depth=10, min_samples_leaf=5,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    return Pipeline([("preprocess", preprocess), ("model", model)])


def main(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(os.path.join(data_dir, "hazard_training_data.csv"))
    df = df.dropna(subset=[TARGET] + CATEGORICAL_FEATURES + NUMERIC_FEATURES)

    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_proba = pipeline.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    auc = float(roc_auc_score(y_test, y_proba))

    # Refit on the full dataset for the deployed model.
    pipeline_full = build_pipeline()
    pipeline_full.fit(X, y)

    model_path = os.path.join(out_dir, "safety_hazard_model.joblib")
    joblib.dump(pipeline_full, model_path)

    defaults = {
        "avg_distance_5min": round(float(df["avg_distance_5min"].median()), 2),
        "min_distance_5min": round(float(df["min_distance_5min"].median()), 2),
        "distance_trend_5min": round(float(df["distance_trend_5min"].median()), 2),
        "proximity_rate_5min": round(float(df["proximity_rate_5min"].median()), 3),
        "avg_speed_5min": round(float(df["avg_speed_5min"].median()), 2),
        "seatbelt_off_rate_5min": round(float(df["seatbelt_off_rate_5min"].median()), 3),
        "idle_rate_5min": round(float(df["idle_rate_5min"].median()), 3),
        "machine_health_score": round(float(df["machine_health_score"].median()), 1),
        "visibility_pct": round(float(df["visibility_pct"].median()), 1),
        "ambient_temp_c": round(float(df["ambient_temp_c"].median()), 1),
        "site_traffic_density": df["site_traffic_density"].mode().iat[0],
    }

    meta = {
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "target": TARGET,
        "defaults": defaults,
        "holdout_precision": round(precision, 3),
        "holdout_recall": round(recall, 3),
        "holdout_roc_auc": round(auc, 3),
        "n_train_rows": int(len(df)),
        "positive_rate": round(float(df[TARGET].mean()), 4),
    }
    with open(os.path.join(out_dir, "safety_hazard_model_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Trained on {len(df)} telemetry rows ({df[TARGET].mean():.1%} positive).")
    print(f"Holdout precision: {precision:.3f}, recall: {recall:.3f}, ROC-AUC: {auc:.3f}")
    print(f"Saved model -> {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="ml/models")
    args = parser.parse_args()
    main(args.data_dir, args.out_dir)
