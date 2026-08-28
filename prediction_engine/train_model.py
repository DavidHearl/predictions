import os

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from .build_dataset import build_dataset

FEATURE_META_COLUMNS = ["result", "total_goals", "match_date"]


def time_ordered_split(df, test_fraction=0.2):
    """Chronological split: train on the past, evaluate on the most recent matches.
    A random split would leak future form into the training set and overstate accuracy."""
    df = df.sort_values("match_date")
    cutoff = int(len(df) * (1 - test_fraction))
    return df.iloc[:cutoff], df.iloc[cutoff:]


def train_model(df=None):
    if df is None:
        df = build_dataset()

    df = df.dropna()
    print(f"Dataset shape after dropping incomplete rows: {df.shape}")
    if len(df) < 200:
        print("Not enough complete rows to train the result model - skipping.")
        return None

    train_df, test_df = time_ordered_split(df)
    X_train = train_df.drop(columns=FEATURE_META_COLUMNS)
    y_train = train_df["result"]
    X_test = test_df.drop(columns=FEATURE_META_COLUMNS)
    y_test = test_df["result"]

    print("Training RandomForestClassifier...")
    model = RandomForestClassifier(
        n_estimators=300, max_depth=12, random_state=42, class_weight="balanced_subsample"
    )
    model.fit(X_train, y_train)

    print("Evaluating on the most recent 20% of matches...")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
    print("Accuracy:", round(accuracy_score(y_test, y_pred) * 100, 2), "%")

    path = os.path.join(os.path.dirname(__file__), "result_model.joblib")
    joblib.dump(model, path)
    print(f"Model saved to {path}")
    return model


if __name__ == "__main__":
    train_model()
