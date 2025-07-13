from .models import Match, MatchTeamStat, MatchTeamStat
from datetime import timedelta
from data_collection.models import MatchTeamStat
from django.db.models import Avg
import numpy as np
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "result_model.joblib")
model = joblib.load(MODEL_PATH)

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

    return np.array([
        home["xg"], home["xga"], home["pass_acc"], home["possession"],
        home["shots"], home["shots_on_target"], home["saves"], home["fouls"], home["tackles"],
        away["xg"], away["xga"], away["pass_acc"], away["possession"],
        away["shots"], away["shots_on_target"], away["saves"], away["fouls"], away["tackles"],
    ])

def predict_match_with_model(match):
    features = extract_features_from_match(match)
    if features is None:
        return None

    prediction = model.predict([features])[0]
    probs = model.predict_proba([features])[0]

    label_map = {0: "home", 1: "draw", 2: "away"}
    return {
        "predicted_result": label_map[prediction],
        "confidence": {
            "home": round(probs[0] * 100, 1),
            "draw": round(probs[1] * 100, 1),
            "away": round(probs[2] * 100, 1),
        }
    }

_goals_model = None

def get_goals_model():
    global _goals_model
    if _goals_model is None:
        path = os.path.join(os.path.dirname(__file__), "goals_model.joblib")
        if not os.path.exists(path):
            return None
        _goals_model = joblib.load(path)
    return _goals_model

def predict_goals_for_match(match):
    features = extract_features_from_match(match)
    if features is None:
        return None

    model = get_goals_model()
    if model is None:
        return None

    predicted_goals = model.predict([features])[0]
    return round(predicted_goals, 2)

def pick_best_goal_bet(predicted_goals: float):
    if predicted_goals is None:
        return None
    lines = [0.5, 1.5, 2.5, 3.5]
    # pick the line the prediction is furthest from ⇒ highest confidence
    best = max(lines, key=lambda l: abs(predicted_goals - l))
    direction = "Over" if predicted_goals > best else "Under"
    confidence = round(min(abs(predicted_goals - best) / 2.5, 1.0) * 100, 1)
    return {"type": f"{direction} {best} Goals", "confidence": confidence}


def get_goal_bets(predicted_goals: float):
    if predicted_goals is None:
        return []

    bets = []
    goal_lines = [0.5, 1.5, 4.5, 5.5]

    for line in goal_lines:
        if line in [0.5, 1.5]:  # Over bets
            direction = "Over"
            confidence = min((predicted_goals - line) / 2.5, 1.0)
        else:  # Under bets
            direction = "Under"
            confidence = min((line - predicted_goals) / 2.5, 1.0)

        confidence = round(max(confidence, 0.0) * 100, 1)

        bets.append({
            "type": f"{direction} {line} Goals",
            "confidence": confidence
        })

    return sorted(bets, key=lambda b: b["confidence"], reverse=True)


def estimate_score(result: str, predicted_goals: float):
    if predicted_goals is None or result is None:
        return None

    total_goals = round(predicted_goals)

    if result == "home":
        return (total_goals - 1, 1) if total_goals > 1 else (1, 0)
    elif result == "away":
        return (1, total_goals - 1) if total_goals > 1 else (0, 1)
    else:  # draw
        return (total_goals // 2, total_goals // 2)


def get_prediction_for_match(match):
    try:
        home_stats = MatchTeamStat.objects.get(match=match, team=match.home_team)
        away_stats = MatchTeamStat.objects.get(match=match, team=match.away_team)

        home_xg = home_stats.expected_goals or 0
        away_xg = away_stats.expected_goals or 0

        predicted_home_score = round(home_xg)
        predicted_away_score = round(away_xg)

        if predicted_home_score > predicted_away_score:
            result = "home"
        elif predicted_home_score < predicted_away_score:
            result = "away"
        else:
            result = "draw"

        return {
            "home_score": predicted_home_score,
            "away_score": predicted_away_score,
            "result": result
        }

    except MatchTeamStat.DoesNotExist:
        return None


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


def predict_from_history(match, last_n_matches=5):
    home_team = match.home_team
    away_team = match.away_team

    home_stats = get_team_stats(home_team, season=match.season, league=match.league, is_home=True, last_n_matches=last_n_matches)
    away_stats = get_team_stats(away_team, season=match.season, league=match.league, is_home=False, last_n_matches=last_n_matches)

    if not home_stats["avg_goals_for"] or not away_stats["avg_goals_for"]:
        return None

    home_xg = (home_stats["avg_goals_for"] + away_stats["avg_goals_against"]) / 2
    away_xg = (away_stats["avg_goals_for"] + home_stats["avg_goals_against"]) / 2

    predicted_home_score = round(home_xg, 2)
    predicted_away_score = round(away_xg, 2)
    total_goals = predicted_home_score + predicted_away_score

    # Result
    if predicted_home_score > predicted_away_score:
        result = "home"
    elif predicted_home_score < predicted_away_score:
        result = "away"
    else:
        result = "draw"

    score_diff = abs(predicted_home_score - predicted_away_score)
    result_conf = round(min(score_diff / 2.5, 1.0) * 100, 1)  # Less confident

    # --- Match-based bets ---
    bets = []

    ## 1. Smart Over/Under Goals
    if total_goals >= 3.0:
        bets.append({"type": "Over 2.5 Goals", "confidence": round(min((total_goals - 2.5) / 2, 1.0) * 100, 1)})
    elif total_goals >= 2.0:
        bets.append({"type": "Over 1.5 Goals", "confidence": round(min((total_goals - 1.5) / 2, 1.0) * 100, 1)})
    elif total_goals >= 1.0:
        bets.append({"type": "Over 0.5 Goals", "confidence": round(min((total_goals - 0.5) / 2, 1.0) * 100, 1)})
    else:
        bets.append({"type": "Under 0.5 Goals", "confidence": 80.0})

    ## 2. BTTS
    btts = predicted_home_score > 0.7 and predicted_away_score > 0.7
    btts_conf = round(min(min(predicted_home_score, predicted_away_score) / 1.5, 1.0) * 100, 1)
    bets.append({
        "type": "Both Teams To Score: " + ("Yes" if btts else "No"),
        "confidence": btts_conf
    })

    ## 3. Clean Sheets
    if predicted_away_score < 0.5:
        bets.append({"type": f"{home_team.name} Clean Sheet", "confidence": round((0.5 - predicted_away_score) * 200, 1)})
    if predicted_home_score < 0.5:
        bets.append({"type": f"{away_team.name} Clean Sheet", "confidence": round((0.5 - predicted_home_score) * 200, 1)})

    ## 4. Full Time Result
    bets.append({
        "type": f"Full Time Result: {result.title()}",
        "confidence": result_conf
    })

    ## 5. Double Chance
    if result in ["home", "draw"]:
        bets.append({"type": "Double Chance: Home or Draw", "confidence": max(90 - result_conf / 2, 60)})
    if result in ["away", "draw"]:
        bets.append({"type": "Double Chance: Away or Draw", "confidence": max(90 - result_conf / 2, 60)})

    ## 6. Draw No Bet
    if result in ["home", "away"]:
        bets.append({"type": f"Draw No Bet: {result.title()}", "confidence": result_conf})

    # --- Optional: Correct score estimate ---
    bets.append({
        "type": f"Correct Score: {round(predicted_home_score)}–{round(predicted_away_score)}",
        "confidence": max(min(score_diff * 25, 60), 10)  # less confident
    })

    return {
        "home_score": predicted_home_score,
        "away_score": predicted_away_score,
        "result": result,
        "result_confidence": result_conf,
        "bets": sorted(bets, key=lambda b: b["confidence"], reverse=True)
    }


def get_player_bet_insights(match):
    from .models import MatchPlayerStat

    player_stats = MatchPlayerStat.objects.filter(match=match).select_related("player")

    insights = []

    for stat in player_stats:
        player = stat.player
        if not player or not player.name:
            continue

        # Foul alert
        if stat.fouls and stat.fouls >= 3:
            insights.append({
                "player": player.name,
                "team": stat.team.name,
                "type": "Over 2.5 Fouls",
                "confidence": 70 + stat.fouls * 5
            })

        # Card alert
        if stat.yellow_cards and stat.yellow_cards >= 1:
            insights.append({
                "player": player.name,
                "team": stat.team.name,
                "type": "Player to Be Carded",
                "confidence": 75.0
            })

        # Shot alert
        if stat.shots and stat.shots >= 3:
            insights.append({
                "player": player.name,
                "team": stat.team.name,
                "type": "Over 2.5 Shots",
                "confidence": 65 + stat.shots * 5
            })

    return sorted(insights, key=lambda x: x["confidence"], reverse=True)
