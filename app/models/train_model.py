from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import get_settings

logger = logging.getLogger(__name__)

FEATURE_ORDER = ("income", "age", "debt", "employment_years")


def make_dataset(n: int = 5000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic dataset with 4 features and a binary risk target.

    Rule (before noise):
        high_risk = (debt / income > 0.5) XOR (employment_years < 2)
    Then ~10% of labels are flipped.
    """
    rng = np.random.default_rng(seed)

    income = rng.lognormal(mean=8.5, sigma=0.6, size=n).clip(min=500.0)  # ~5k median
    age = rng.integers(low=18, high=101, size=n)
    debt = rng.lognormal(mean=7.5, sigma=1.0, size=n).clip(min=0.0)
    employment_years = rng.integers(low=0, high=40, size=n)

    ratio = debt / income
    base_label = np.logical_xor(ratio > 0.5, employment_years < 2)
    flip = rng.random(size=n) < 0.10
    y = np.where(flip, ~base_label, base_label).astype(np.int64)

    X = np.column_stack([income, age, debt, employment_years]).astype(np.float64)
    return X, y


def train(model_path: str | None = None) -> Pipeline:
    settings = get_settings()
    target_path = Path(model_path or settings.model_path)

    X, y = make_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("=== Test metrics ===")
    print(f"accuracy : {accuracy_score(y_test, y_pred):.4f}")
    print(f"precision: {precision_score(y_test, y_pred):.4f}")
    print(f"recall   : {recall_score(y_test, y_pred):.4f}")
    print(f"f1       : {f1_score(y_test, y_pred):.4f}")
    print("confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    target_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, target_path)
    print(f"Saved model to {target_path}")
    return pipeline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
