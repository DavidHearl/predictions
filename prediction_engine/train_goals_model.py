import os

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from .build_dataset import build_dataset
from .train_model import FEATURE_META_COLUMNS, time_ordered_split


def train_goals_model(df=None):
    if df is None:
        df = build_dataset()

    df = df.dropna()
    if len(df) < 200:
        print("Not enough complete rows to train the goals model - skipping.")
        return None

    train_df, test_df = time_ordered_split(df)
    X_train = train_df.drop(columns=FEATURE_META_COLUMNS)
    y_train = train_df["total_goals"]
    X_test = test_df.drop(columns=FEATURE_META_COLUMNS)
    y_test = test_df["total_goals"]

    model = RandomForestRegressor(n_estimators=300, max_depth=10, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    print("Mean Absolute Error (most recent 20% of matches):", round(mae, 3))

    # NB: this previously saved to result_model.joblib, silently overwriting the
    # match-result classifier with a regressor.
    path = os.path.join(os.path.dirname(__file__), "goals_model.joblib")
    joblib.dump(model, path)
    print(f"Model saved to {path}")
    return model


if __name__ == "__main__":
    train_goals_model()
