"""Market probabilities and value-bet maths.

Given a scoreline probability matrix from the Dixon-Coles model, derive the
probability of every common market, then compare against bookmaker odds:

- implied probability = 1 / decimal odds (contains the bookmaker margin)
- edge (expected value per unit staked) = model_prob * odds - 1
- Kelly criterion stake fraction = (p*o - 1) / (o - 1), reported as a
  quarter-Kelly, the usual practical compromise against model error.

A bet is only worth taking when the edge is positive after the margin - the
decision matrix on the site ranks bets by exactly this number.
"""
import numpy as np

GOAL_LINES = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)
KELLY_FRACTION = 0.25


def market_probs(matrix):
    """All market probabilities from a score matrix. Keys are stable strings
    so they can be stored in Prediction.market_probs as JSON."""
    n = matrix.shape[0]
    goals_h, goals_a = np.indices(matrix.shape)
    totals = goals_h + goals_a

    probs = {
        "home": float(np.tril(matrix, -1).sum()),   # home goals > away goals
        "draw": float(np.trace(matrix)),
        "away": float(np.triu(matrix, 1).sum()),
        "btts_yes": float(matrix[1:, 1:].sum()),
        "btts_no": float(1.0 - matrix[1:, 1:].sum()),
    }
    for line in GOAL_LINES:
        over = float(matrix[totals > line].sum())
        probs[f"over_{line}"] = over
        probs[f"under_{line}"] = 1.0 - over

    # A few most likely scorelines for display
    flat = [
        (float(matrix[i, j]), i, j)
        for i in range(n) for j in range(n)
    ]
    flat.sort(reverse=True)
    probs["top_scores"] = [
        {"score": f"{i}-{j}", "prob": round(p, 4)} for p, i, j in flat[:5]
    ]
    return probs


def implied_prob(odds):
    return 1.0 / odds if odds and odds > 1.0 else None


def edge(model_prob, odds):
    """Expected value per unit staked; positive means a value bet."""
    if model_prob is None or not odds or odds <= 1.0:
        return None
    return model_prob * odds - 1.0


def kelly_stake(model_prob, odds, fraction=KELLY_FRACTION):
    """Fractional-Kelly stake as a proportion of bankroll (0 when no edge)."""
    e = edge(model_prob, odds)
    if e is None or e <= 0:
        return 0.0
    return round(fraction * e / (odds - 1.0), 4)


# How much weight the (de-margined) market price gets when computing the
# betting probability. The market aggregates a lot of information the model
# doesn't have (injuries, lineups, motivation), so pure-model edges are
# systematically overstated - especially for longshots and newly promoted
# teams. Blending is what keeps the value matrix honest.
#
# Calibration (walk-forward backtest, 2,257 matches over 12 months): blended
# 1X2 log-loss improves monotonically as weight shifts toward the market -
# the closing price is the best public forecast, and this model does not beat
# it. The weight below is deliberately high so that only large model-market
# disagreements surface as "value"; edges against earlier (pre-closing)
# prices, which is what the site bets into, retain more of their meaning.
MARKET_BLEND_WEIGHT = 0.65
LOW_DATA_BLEND_WEIGHT = 0.85     # used when a team has few matches in the fit
LOW_DATA_MATCHES = 10
MIN_VALUE_PROB = 0.12            # never tout longshots below this blended probability


def demargin(odds_group):
    """Remove the bookmaker margin from a group of mutually exclusive odds
    using the power method: find k so that sum((1/o_i)^k) = 1.

    Bookmakers load most of their margin onto longshots (favourite-longshot
    bias). Proportional scaling under-corrects that, leaving longshot "fair"
    probabilities too high - which showed up in backtests as bleeding money on
    home/away underdogs. The power method pushes longshots down and favourites
    up, matching how the margin is actually distributed.

    [2.0, 3.5, 4.0] -> fair probabilities summing to 1, or None if incomplete.
    """
    if not odds_group or any(o is None or o <= 1.0 for o in odds_group):
        return None
    raw = [1.0 / o for o in odds_group]

    # Newton iteration on f(k) = sum(raw_i^k) - 1 (f is decreasing in k, k>1
    # because the raw probabilities overround to >1).
    import math
    k = 1.0
    for _ in range(50):
        powered = [r ** k for r in raw]
        f = sum(powered) - 1.0
        if abs(f) < 1e-10:
            break
        derivative = sum(p * math.log(r) for p, r in zip(powered, raw) if r > 0)
        if derivative == 0:
            break
        k -= f / derivative
        k = max(k, 0.2)
    powered = [r ** k for r in raw]
    total = sum(powered)
    return [p / total for p in powered]


def evaluate_markets(probs, odds_row, blend_weight=None):
    """Cross model probabilities with a MatchOdds row.

    The betting probability is a blend of the model probability and the
    de-margined market probability; the blend leans harder on the market when
    either team had little data in the fit (probs["meta"]["min_matches"]).

    Returns a list of market dicts sorted by edge descending. `value` is only
    True for positive-edge markets with a blended probability above
    MIN_VALUE_PROB (longshot edges are usually model error, not value).
    """
    if odds_row is None:
        return []

    meta = probs.get("meta") or {}
    if blend_weight is None:
        min_matches = meta.get("min_matches")
        low_data = min_matches is not None and min_matches < LOW_DATA_MATCHES
        blend_weight = LOW_DATA_BLEND_WEIGHT if low_data else MARKET_BLEND_WEIGHT

    # De-margined market probabilities per market group (base odds: more stable
    # than the cross-bookmaker max, which is what we pay out at).
    fair_1x2 = demargin([odds_row.home_odds, odds_row.draw_odds, odds_row.away_odds])
    fair_ou = demargin([odds_row.over25_odds, odds_row.under25_odds])

    fair = {}
    if fair_1x2:
        fair["home"], fair["draw"], fair["away"] = fair_1x2
    if fair_ou:
        fair["over_2.5"], fair["under_2.5"] = fair_ou

    # Edges are computed at the Bet365 price (falling back to the market
    # average): a price you can actually get. The cross-bookmaker maximum is
    # frequently an odds-boost or feed outlier, and computing "value" against
    # it produced absurd edges - it is exposed as `best_odds` for display only.
    candidates = [
        ("Home win", "home", odds_row.home_odds, odds_row.avg_home_odds, odds_row.max_home_odds),
        ("Draw", "draw", odds_row.draw_odds, odds_row.avg_draw_odds, odds_row.max_draw_odds),
        ("Away win", "away", odds_row.away_odds, odds_row.avg_away_odds, odds_row.max_away_odds),
        ("Over 2.5 goals", "over_2.5", odds_row.over25_odds, None, odds_row.max_over25_odds),
        ("Under 2.5 goals", "under_2.5", odds_row.under25_odds, None, odds_row.max_under25_odds),
    ]

    markets = []
    for label, key, base_odds, avg_odds, max_odds in candidates:
        odds = base_odds or avg_odds
        model_p = probs.get(key)
        if model_p is None or not odds or odds <= 1.0:
            continue

        if key in fair:
            bet_p = (1 - blend_weight) * model_p + blend_weight * fair[key]
        else:
            bet_p = model_p

        market_edge = edge(bet_p, odds)
        is_value = market_edge > 0 and bet_p >= MIN_VALUE_PROB
        markets.append({
            "market": label,
            "key": key,
            "bet_type": BET_TYPE_FOR_MARKET.get(key, "other"),
            "model_prob": round(model_p, 4),
            "bet_prob": round(bet_p, 4),
            "odds": odds,
            "best_odds": max_odds if (max_odds and max_odds > odds) else None,
            "implied_prob": round(implied_prob(odds), 4),
            "edge": round(market_edge, 4),
            "kelly": kelly_stake(bet_p, odds),
            "value": is_value,
            "tier": tier(market_edge, bet_p) if is_value else None,
        })
    markets.sort(key=lambda m: m["edge"], reverse=True)
    return markets


# Maps a market key to the Bet.bet_type choice used when logging the bet,
# so the value matrix can prefill the bet slip.
BET_TYPE_FOR_MARKET = {
    "home": "home_win",
    "draw": "draw",
    "away": "away_win",
    "over_2.5": "over_2.5",
    "under_2.5": "under_2.5",
}

# Display tiers for positive-edge bets: a rough "how seriously to take this"
# banding used by the UI. Strong = meaningful edge on a likely outcome;
# slim = technically positive but within model noise.
TIER_STRONG_EDGE = 0.06
TIER_GOOD_EDGE = 0.03
TIER_STRONG_MIN_PROB = 0.30


def tier(edge_value, prob):
    if edge_value is None or edge_value <= 0:
        return None
    if edge_value >= TIER_STRONG_EDGE and prob >= TIER_STRONG_MIN_PROB:
        return "strong"
    if edge_value >= TIER_GOOD_EDGE:
        return "good"
    return "slim"
