from .models import Match, MatchTeamStat, MatchTeamStat
from django.db.models import Avg, Count

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

    # Result prediction
    if predicted_home_score > predicted_away_score:
        result = "home"
    elif predicted_home_score < predicted_away_score:
        result = "away"
    else:
        result = "draw"

    # Confidence (based on score difference)
    result_confidence = round(
        min(abs(predicted_home_score - predicted_away_score) / 2, 1.0) * 100, 1
    )

    # Bet recommendations
    total_goals = predicted_home_score + predicted_away_score

    bets = []

    # Over/Under 2.5 Goals
    if total_goals >= 2.5:
        over_confidence = round(min((total_goals - 2.5) / 2, 1.0) * 100, 1)
        bets.append({
            "type": "Over 2.5 Goals",
            "confidence": over_confidence
        })
    else:
        under_confidence = round(min((2.5 - total_goals) / 2, 1.0) * 100, 1)
        bets.append({
            "type": "Under 2.5 Goals",
            "confidence": under_confidence
        })

    # Both Teams To Score
    btts = predicted_home_score > 0.7 and predicted_away_score > 0.7
    btts_confidence = round(min(min(predicted_home_score, predicted_away_score) / 1.5, 1.0) * 100, 1)
    bets.append({
        "type": "Both Teams To Score: " + ("Yes" if btts else "No"),
        "confidence": btts_confidence
    })

    # 1X2 (Match Result)
    bets.append({
        "type": f"Full Time Result: {result.title()}",
        "confidence": result_confidence
    })

    return {
        "home_score": predicted_home_score,
        "away_score": predicted_away_score,
        "result": result,
        "result_confidence": result_confidence,
        "bets": bets
    }
