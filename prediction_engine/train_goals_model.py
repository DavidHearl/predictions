import pandas as pd
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
from .build_dataset import *


def train_goals_model(df=None):
    if df is None:
        from .build_dataset import build_dataset
        df = build_dataset()

    df = df.dropna()
    X = df.drop(columns=["result", "total_goals"])
    y = df["total_goals"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    model = RandomForestRegressor(n_estimators=300, max_depth=10)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)

    print("Mean Absolute Error:", round(mae, 3))
    joblib.dump(model, os.path.join(os.path.dirname(__file__), "result_model.joblib"))
    print("Model saved to goals_model.joblib")

if __name__ == "__main__":
    train_goals_model()
