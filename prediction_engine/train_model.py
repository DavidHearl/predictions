import pandas as pd
from django.db.models import Avg, Q
from data_collection.models import Match, MatchTeamStat
from datetime import timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
from data_collection.models import Match
from collections import defaultdict
from .build_dataset import *


def get_form_stats(team, before_date, is_home=None, n_matches=5):
    filters = Q(match__date__lt=before_date, team=team)
    if is_home is not None:
        filters &= Q(is_home=is_home)

    stats = (
        MatchTeamStat.objects
        .filter(filters)
        .order_by('-match__date')[:n_matches]
    )

    return stats.aggregate(
        xg=Avg("expected_goals"),
        xga=Avg("expected_goals_against"),
        pass_acc=Avg("passing_accuracy"),
        possession=Avg("possession"),
        shots=Avg("total_shots"),
        shots_on_target=Avg("shots_on_target"),
        saves=Avg("saves"),
        fouls=Avg("fouls"),
        tackles=Avg("tackles")
    )


def label_result(home_score, away_score):
    if home_score > away_score:
        return 0  # home win
    elif home_score < away_score:
        return 2  # away win
    else:
        return 1  # draw


def train_model(df=None):
    if df is None:
        from .build_dataset import build_dataset
        df = build_dataset()

    print(f"✅ Dataset shape: {df.shape}")
    df = df.dropna()

    X = df.drop(columns=["result", "total_goals"])
    y = df["result"]

    print("Splitting dataset...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y)

    print("Training RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=300, max_depth=12, random_state=42)
    model.fit(X_train, y_train)

    print("Evaluating...")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
    print("Accuracy:", round(accuracy_score(y_test, y_pred) * 100, 2), "%")

    print("Saving model to result_model.joblib...")
    joblib.dump(model, "result_model.joblib")

if __name__ == "__main__":
    train_model()
