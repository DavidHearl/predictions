"""Dixon-Coles Poisson model for match outcome probabilities.

This replaces ad-hoc confidence heuristics with a proper probabilistic model:

- Every team gets an attack and defence rating, fitted by maximum likelihood
  over recent seasons with exponential time-decay (recent form counts more).
- A home-advantage parameter and the Dixon-Coles `rho` correction for the
  dependence between low scores (0-0, 1-0, 0-1, 1-1).
- Leagues are pooled per country (e.g. Premier League + Championship fit
  together) so promoted teams carry their rating up instead of starting blind.
- Optionally, a second model is fitted on xG instead of goals and the two
  expected-goal estimates are blended - xG is less noisy than goals.

Outputs, per fixture: expected goals for both sides and a full scoreline
probability matrix, from which any market probability (1X2, over/under,
BTTS, correct score) can be read.
"""
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

# Exponential time-decay: weight = exp(-XI * days_ago). 0.0023 ~ 300-day half-life.
DEFAULT_XI = 0.0023
MAX_GOALS = 10          # scoreline matrix dimension (0..MAX_GOALS)
XG_BLEND_WEIGHT = 0.4   # how much the xG model contributes to expected goals
MIN_XG_MATCHES = 8      # a team needs this many xG data points before blending kicks in


@dataclass
class DixonColesModel:
    teams: list                      # team ids, index-aligned with ratings
    attack: np.ndarray
    defence: np.ndarray
    home_advs: dict                  # league key -> home advantage (None key = overall)
    rho: float
    team_index: dict = field(default_factory=dict)
    match_counts: dict = field(default_factory=dict)   # team id -> matches in the goals fit
    # Optional xG-based ratings (same team indexing)
    xg_attack: np.ndarray = None
    xg_defence: np.ndarray = None
    xg_home_advs: dict = None
    xg_match_counts: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.team_index:
            self.team_index = {t: i for i, t in enumerate(self.teams)}

    def knows(self, team_id):
        return team_id in self.team_index

    def _home_adv(self, advs, league_key):
        """Home advantage for a league, falling back to the fit-wide average.
        Home advantage genuinely differs between divisions, and a pooled
        England fit (Premier League + Championship) needs both."""
        if not advs:
            return 0.0
        if league_key in advs:
            return advs[league_key]
        return sum(advs.values()) / len(advs)

    def expected_goals(self, home_id, away_id, league_key=None):
        """Blended (goals + xG) expected goals for a fixture, or None if a team is unknown."""
        if not (self.knows(home_id) and self.knows(away_id)):
            return None
        hi, ai = self.team_index[home_id], self.team_index[away_id]
        lam = math.exp(self._home_adv(self.home_advs, league_key) + self.attack[hi] + self.defence[ai])
        mu = math.exp(self.attack[ai] + self.defence[hi])

        if (
            self.xg_attack is not None
            and self.xg_match_counts.get(home_id, 0) >= MIN_XG_MATCHES
            and self.xg_match_counts.get(away_id, 0) >= MIN_XG_MATCHES
        ):
            lam_xg = math.exp(self._home_adv(self.xg_home_advs, league_key)
                              + self.xg_attack[hi] + self.xg_defence[ai])
            mu_xg = math.exp(self.xg_attack[ai] + self.xg_defence[hi])
            w = XG_BLEND_WEIGHT
            lam = lam ** (1 - w) * lam_xg ** w
            mu = mu ** (1 - w) * mu_xg ** w
        return lam, mu

    def score_matrix(self, home_id, away_id, league_key=None):
        """P(home=i, away=j) matrix with the Dixon-Coles low-score correction."""
        expectation = self.expected_goals(home_id, away_id, league_key)
        if expectation is None:
            return None
        lam, mu = expectation
        goals = np.arange(MAX_GOALS + 1)
        p_home = np.exp(-lam) * lam ** goals / np.array([math.factorial(k) for k in goals])
        p_away = np.exp(-mu) * mu ** goals / np.array([math.factorial(k) for k in goals])
        matrix = np.outer(p_home, p_away)

        rho = self.rho
        matrix[0, 0] *= 1 - lam * mu * rho
        matrix[0, 1] *= 1 + lam * rho
        matrix[1, 0] *= 1 + mu * rho
        matrix[1, 1] *= 1 - rho
        matrix = np.clip(matrix, 0, None)
        return matrix / matrix.sum()


def _negative_log_likelihood(params, home_idx, away_idx, home_goals, away_goals,
                             weights, n_teams, n_leagues, league_idx, use_tau):
    attack = params[:n_teams]
    defence = params[n_teams:2 * n_teams]
    home_advs = params[2 * n_teams:2 * n_teams + n_leagues]
    rho = params[-1]

    lam = np.exp(home_advs[league_idx] + attack[home_idx] + defence[away_idx])
    mu = np.exp(attack[away_idx] + defence[home_idx])

    # Poisson log-pmf (valid as quasi-likelihood for non-integer xG targets too)
    log_lik = (
        home_goals * np.log(lam) - lam - gammaln(home_goals + 1)
        + away_goals * np.log(mu) - mu - gammaln(away_goals + 1)
    )

    if use_tau:
        tau = np.ones_like(lam)
        is00 = (home_goals == 0) & (away_goals == 0)
        is01 = (home_goals == 0) & (away_goals == 1)
        is10 = (home_goals == 1) & (away_goals == 0)
        is11 = (home_goals == 1) & (away_goals == 1)
        tau[is00] = 1 - lam[is00] * mu[is00] * rho
        tau[is01] = 1 + lam[is01] * rho
        tau[is10] = 1 + mu[is10] * rho
        tau[is11] = 1 - rho
        log_lik = log_lik + np.log(np.clip(tau, 1e-10, None))

    nll = -np.sum(weights * log_lik)
    # Soft identifiability constraint (mean attack = 0) plus a ridge penalty.
    # The ridge matters for newly promoted teams with a handful of matches:
    # without meaningful shrinkage three bad results produce an absurd rating
    # (and absurd "value bets" against them). For established teams the data
    # term dwarfs the penalty, so their ratings are unaffected.
    nll += 1000.0 * np.mean(attack) ** 2
    nll += 2.0 * (np.sum(attack ** 2) + np.sum(defence ** 2))
    return nll


def fit_ratings(rows, xi=DEFAULT_XI, use_tau=True, reference_date=None):
    """Fit attack/defence ratings with one home-advantage parameter per league.

    rows: iterable of (date, home_team_id, away_team_id, home_goals, away_goals)
    or the same with a trailing league key. Returns
    (teams, attack, defence, home_advs, rho, match_counts) or None if there is
    not enough data.
    """
    rows = [r for r in rows if r[3] is not None and r[4] is not None]
    if len(rows) < 50:
        return None

    if reference_date is None:
        reference_date = max(r[0] for r in rows)

    teams = sorted({r[1] for r in rows} | {r[2] for r in rows})
    index = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    league_keys = sorted({(r[5] if len(r) > 5 else None) for r in rows}, key=str)
    league_index = {k: i for i, k in enumerate(league_keys)}
    n_leagues = len(league_keys)

    home_idx = np.array([index[r[1]] for r in rows])
    away_idx = np.array([index[r[2]] for r in rows])
    league_idx = np.array([league_index[r[5] if len(r) > 5 else None] for r in rows])
    home_goals = np.array([float(r[3]) for r in rows])
    away_goals = np.array([float(r[4]) for r in rows])
    days_ago = np.array([max((reference_date - r[0]).days, 0) for r in rows])
    weights = np.exp(-xi * days_ago)

    match_counts = {}
    for r in rows:
        match_counts[r[1]] = match_counts.get(r[1], 0) + 1
        match_counts[r[2]] = match_counts.get(r[2], 0) + 1

    x0 = np.concatenate([np.zeros(n), np.zeros(n), np.full(n_leagues, 0.25), [-0.05]])
    bounds = [(-3, 3)] * (2 * n) + [(-1, 1)] * n_leagues + [(-0.2, 0.2)]

    result = minimize(
        _negative_log_likelihood, x0,
        args=(home_idx, away_idx, home_goals, away_goals, weights, n, n_leagues, league_idx, use_tau),
        method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 400},
    )

    attack = result.x[:n]
    defence = result.x[n:2 * n]
    home_advs = {k: float(result.x[2 * n + i]) for k, i in league_index.items()}
    rho = float(result.x[-1])
    return teams, attack, defence, home_advs, rho, match_counts


def fit_model(goal_rows, xg_rows=None, xi=DEFAULT_XI, reference_date=None):
    """Fit the full model: goals-based DC ratings, plus optional xG ratings for blending."""
    fitted = fit_ratings(goal_rows, xi=xi, use_tau=True, reference_date=reference_date)
    if fitted is None:
        return None
    teams, attack, defence, home_advs, rho, match_counts = fitted

    model = DixonColesModel(
        teams=teams, attack=attack, defence=defence, home_advs=home_advs, rho=rho,
        match_counts=match_counts,
    )

    if xg_rows:
        xg_fitted = fit_ratings(xg_rows, xi=xi, use_tau=False, reference_date=reference_date)
        if xg_fitted is not None:
            xg_teams, xg_attack, xg_defence, xg_home_advs, _, xg_counts = xg_fitted
            # Re-align xG ratings onto the goals-model team ordering
            aligned_attack = np.zeros(len(teams))
            aligned_defence = np.zeros(len(teams))
            xg_index = {t: i for i, t in enumerate(xg_teams)}
            for t, i in model.team_index.items():
                if t in xg_index:
                    aligned_attack[i] = xg_attack[xg_index[t]]
                    aligned_defence[i] = xg_defence[xg_index[t]]
            model.xg_attack = aligned_attack
            model.xg_defence = aligned_defence
            model.xg_home_advs = xg_home_advs
            model.xg_match_counts = xg_counts

    return model
