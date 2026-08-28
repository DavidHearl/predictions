"""Glue between the Django models and the Dixon-Coles engine.

Leagues are pooled per country before fitting, so England fits the Premier
League and Championship together - promotion/relegation connects the two
divisions and gives promoted teams a meaningful rating from day one.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from data_collection.models import League, Match, MatchTeamStat, Prediction
from .dixon_coles import fit_model
from .markets import market_probs

log = logging.getLogger("prediction_engine")

MODEL_NAME = "dixon-coles-v2"
TRAINING_WINDOW_DAYS = 1500     # ~4 seasons; time-decay handles the rest


def _pooled_leagues():
    """Group tracked leagues by country."""
    pools = defaultdict(list)
    for league in League.objects.exclude(fd_code__isnull=True).exclude(fd_code=""):
        pools[league.country or league.name].append(league)
    return dict(pools)


def build_goal_rows(leagues, since):
    matches = (
        Match.objects.filter(
            league__in=leagues, date__gte=since,
            home_score__isnull=False, away_score__isnull=False,
        )
        .values_list("date", "home_team_id", "away_team_id", "home_score", "away_score",
                     "league_id")
    )
    return [(d.date(), h, a, hs, as_, lg) for d, h, a, hs, as_, lg in matches]


def build_xg_rows(leagues, since):
    """Matches where both sides have an xG figure recorded."""
    stats = (
        MatchTeamStat.objects.filter(
            match__league__in=leagues, match__date__gte=since,
            expected_goals__isnull=False,
        )
        .values_list("match_id", "match__date", "match__home_team_id",
                     "match__away_team_id", "team_id", "is_home", "expected_goals",
                     "match__league_id")
    )
    by_match = {}
    for match_id, date, home_id, away_id, team_id, is_home, xg, league_id in stats:
        entry = by_match.setdefault(match_id, {
            "date": date.date(), "home": home_id, "away": away_id, "league": league_id,
        })
        if is_home or team_id == home_id:
            entry["home_xg"] = xg
        else:
            entry["away_xg"] = xg
    return [
        (e["date"], e["home"], e["away"], e["home_xg"], e["away_xg"], e["league"])
        for e in by_match.values()
        if "home_xg" in e and "away_xg" in e
    ]


def fit_country_models(verbose=print):
    """Fit one Dixon-Coles model per country pool. Returns {league_id: model}."""
    since = timezone.now() - timedelta(days=TRAINING_WINDOW_DAYS)
    models_by_league = {}

    for country, leagues in _pooled_leagues().items():
        goal_rows = build_goal_rows(leagues, since)
        xg_rows = build_xg_rows(leagues, since)
        if verbose:
            verbose(f"  {country}: {len(goal_rows)} results, {len(xg_rows)} with xG "
                    f"({', '.join(l.name for l in leagues)})")
        model = fit_model(goal_rows, xg_rows=xg_rows)
        if model is None:
            if verbose:
                verbose(f"  {country}: not enough data to fit a model - skipped")
            continue
        for league in leagues:
            models_by_league[league.id] = model

    return models_by_league


def predict_match(model, match):
    """Return (prediction_fields, market_probs_dict) for a fixture, or None."""
    matrix = model.score_matrix(match.home_team_id, match.away_team_id, match.league_id)
    if matrix is None:
        return None
    lam, mu = model.expected_goals(match.home_team_id, match.away_team_id, match.league_id)
    probs = market_probs(matrix)
    home_matches = model.match_counts.get(match.home_team_id, 0)
    away_matches = model.match_counts.get(match.away_team_id, 0)
    probs["meta"] = {
        "home_matches": home_matches,
        "away_matches": away_matches,
        "min_matches": min(home_matches, away_matches),
    }
    outcome = max(("home", "draw", "away"), key=lambda k: probs[k])
    fields = {
        "predicted_result": outcome,
        "predicted_home_score": round(lam, 2),
        "predicted_away_score": round(mu, 2),
        "prob_home": round(probs["home"], 4),
        "prob_draw": round(probs["draw"], 4),
        "prob_away": round(probs["away"], 4),
        "market_probs": probs,
        "model_name": MODEL_NAME,
    }
    return fields


def update_predictions(horizon_days=14, include_played_without_prediction=False, verbose=print):
    """Fit models and upsert Prediction rows for upcoming fixtures.
    Returns (predicted_count, skipped_count)."""
    models_by_league = fit_country_models(verbose=verbose)
    if not models_by_league:
        return (0, 0)

    now = timezone.now()
    fixtures = Match.objects.filter(
        league_id__in=models_by_league.keys(),
        home_score__isnull=True,
        date__gte=now - timedelta(hours=12),
        date__lte=now + timedelta(days=horizon_days),
    ).select_related("home_team", "away_team", "league")

    predicted = skipped = 0
    for match in fixtures:
        model = models_by_league[match.league_id]
        result = predict_match(model, match)
        if result is None:
            skipped += 1
            continue
        Prediction.objects.update_or_create(match=match, defaults=result)
        predicted += 1

    return (predicted, skipped)
