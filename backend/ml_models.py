"""
ml_models.py
-------------
Loads the two trained scikit-learn pipelines (Task Time Estimation
regressor, Safety hazard-prediction classifier) plus their metadata once
at import time, mirroring how `data_access/repository.py` loads CSVs once
at startup. Routers depend on the singletons below rather than touching
joblib/model files directly - if a model ever needs hot-reloading or a
different serving mechanism, this is the only file that changes.

Models are trained offline by ml/train_estimation_model.py and
ml/train_safety_model.py (batch jobs, same philosophy as
feature_engineering/build_features.py) and loaded here for fast in-process
inference at request time - no training ever happens on the request path.
"""

from __future__ import annotations

import json
import os

import joblib
import pandas as pd

from backend import config

_MODELS_DIR = config.ML_MODELS_DIR


class TaskTimeModel:
    def __init__(self, models_dir: str = _MODELS_DIR):
        self.pipeline = joblib.load(os.path.join(models_dir, "task_time_model.joblib"))
        with open(os.path.join(models_dir, "task_time_model_meta.json")) as f:
            self.meta = json.load(f)

    def predict(self, features: dict) -> dict:
        """features: dict with keys from meta['categorical_features'] +
        meta['numeric_features'] (missing keys are filled from defaults)."""
        row = {**self.meta["defaults"], **{k: v for k, v in features.items() if v is not None}}
        cols = self.meta["categorical_features"] + self.meta["numeric_features"]
        X = pd.DataFrame([{c: row[c] for c in cols}])

        prediction = float(self.pipeline.predict(X)[0])

        # Prediction spread across the forest's trees as a cheap, honest
        # confidence signal - tight agreement between trees -> High
        # confidence, wide disagreement -> Low, without needing a second
        # model or a hardcoded lookup table.
        preprocess = self.pipeline.named_steps["preprocess"]
        forest = self.pipeline.named_steps["model"]
        X_transformed = preprocess.transform(X)
        tree_preds = [est.predict(X_transformed)[0] for est in forest.estimators_]
        std = float(pd.Series(tree_preds).std())
        spread_ratio = std / max(prediction, 1.0)
        if spread_ratio < 0.15:
            confidence = "High"
        elif spread_ratio < 0.30:
            confidence = "Medium"
        else:
            confidence = "Low"

        return {
            "predicted_duration_min": round(prediction, 1),
            "confidence": confidence,
            "std_min": round(std, 1),
        }


class SafetyHazardModel:
    def __init__(self, models_dir: str = _MODELS_DIR):
        self.pipeline = joblib.load(os.path.join(models_dir, "safety_hazard_model.joblib"))
        with open(os.path.join(models_dir, "safety_hazard_model_meta.json")) as f:
            self.meta = json.load(f)

    def predict_proba(self, features: dict) -> float:
        row = {**self.meta["defaults"], **{k: v for k, v in features.items() if v is not None}}
        cols = self.meta["categorical_features"] + self.meta["numeric_features"]
        X = pd.DataFrame([{c: row[c] for c in cols}])
        return float(self.pipeline.predict_proba(X)[0, 1])


# Singletons, loaded once at process startup - same pattern as
# dependencies.py's repository singleton.
_task_time_model: TaskTimeModel | None = None
_safety_hazard_model: SafetyHazardModel | None = None


def get_task_time_model() -> TaskTimeModel:
    global _task_time_model
    if _task_time_model is None:
        _task_time_model = TaskTimeModel()
    return _task_time_model


def get_safety_hazard_model() -> SafetyHazardModel:
    global _safety_hazard_model
    if _safety_hazard_model is None:
        _safety_hazard_model = SafetyHazardModel()
    return _safety_hazard_model
