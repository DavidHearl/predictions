import logging
import os

import joblib
import numpy as np
from django.db.models import Avg

from .models import Match, MatchTeamStat

log = logging.getLogger("data_collection.utils")

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "prediction_engine")

# Lazily-loaded sklearn models. These are the legacy RandomForest models kept
# as a secondary opinion; the primary predictions come from the Dixon-Coles
# engine and are stored on the Prediction model. A missing/incompatible
# joblib file must never take the whole site down, hence the guarded loading.
_models = {}


def _load_model(filename):
    if filename in _models:
        return _models[filename]
    path = os.path.join(_MODEL_DIR, filename)
    model = None
    if os.path.exists(path):
        try:
            model = joblib.load(path)
        except Exception as e:  # noqa: BLE001 - version mismatch, corrupt file, etc.
            log.warning("Could not load %s: %s", filename, e)
    _models[filename] = model
    return model


def get_result_model():
    return _load_model("result_model.joblib")


def get_goals_model():
    return _load_model("goals_model.joblib")


def get_team_form(team, before_date, is_home=None, n_matches=5):
    qs = MatchTeamStat.objects.filter(match__date__lt=before_date, team=team)
    if is_home is not None:
        qs = qs.filter(is_home=is_home)
    qs = qs.order_by('-match__date')[:n_matches]

    return qs.aggregate(
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


def extract_features_from_match(match):
    home = get_team_form(match.home_team, match.date, is_home=True)
    away = get_team_form(match.away_team, match.date, is_home=False)

    if not home["xg"] or not away["xg"]:
        return None

    features = [
        home["xg"], home["xga"], home["pass_acc"], home["possession"],
        home["shots"], home["shots_on_target"], home["saves"], home["fouls"], home["tackles"],
        away["xg"], away["xga"], away["pass_acc"], away["possession"],
        away["shots"], away["shots_on_target"], away["saves"], away["fouls"], away["tackles"],
    ]
    if any(value is None for value in features):
        return None
    return np.array(features)


def predict_match_with_model(match):
    """Legacy RandomForest 1X2 prediction. Returns None when the model or
    the team-form features are unavailable."""
    model = get_result_model()
    if model is None:
        return None

    features = extract_features_from_match(match)
    if features is None:
        return None

    try:
        prediction = model.predict([features])[0]
        probs = model.predict_proba([features])[0]
    except Exception as e:  # noqa: BLE001
        log.warning("result model prediction failed: %s", e)
        return None

    label_map = {0: "home", 1: "draw", 2: "away"}
    return {
        "predicted_result": label_map[int(prediction)],
        "confidence": {
            "home": round(probs[0] * 100, 1),
            "draw": round(probs[1] * 100, 1),
            "away": round(probs[2] * 100, 1),
        }
    }


def predict_goals_for_match(match):
    """Legacy RandomForest total-goals prediction."""
    model = get_goals_model()
    if model is None:
        return None

    features = extract_features_from_match(match)
    if features is None:
        return None

    try:
        predicted_goals = model.predict([features])[0]
    except Exception as e:  # noqa: BLE001
        log.warning("goals model prediction failed: %s", e)
        return None
    return round(float(predicted_goals), 2)


def get_team_stats(team, season=None, league=None, last_n_matches=5, is_home=None):
    matches = Match.objects.filter(
        matchteamstat__team=team
    ).order_by("-date")

    if season:
        matches = matches.filter(season=season)
    if league:
        matches = matches.filter(league=league)
    if is_home is not None:
        matches = matches.filter(matchteamstat__is_home=is_home)

    matches = matches.distinct()[:last_n_matches]

    stats = MatchTeamStat.objects.filter(match__in=matches, team=team)

    return stats.aggregate(
        avg_goals_for=Avg('expected_goals'),
        avg_goals_against=Avg('expected_goals_against'),
        avg_possession=Avg('possession'),
        avg_shots=Avg('total_shots'),
        avg_on_target=Avg('shots_on_target')
    )


def get_recent_results(team, before_date, n=5):
    """Last n results for a team as a list of 'W'/'D'/'L' (most recent first)."""
    matches = (
        Match.objects.filter(date__lt=before_date, home_score__isnull=False)
        .filter(away_score__isnull=False)
        .filter(models_q_team(team))
        .order_by("-date")[:n]
    )
    results = []
    for m in matches:
        if m.home_score == m.away_score:
            results.append("D")
        elif (m.home_team_id == team.id) == (m.home_score > m.away_score):
            results.append("W")
        else:
            results.append("L")
    return results


def models_q_team(team):
    from django.db.models import Q
    return Q(home_team=team) | Q(away_team=team)
