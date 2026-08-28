"""Tests for the prediction engine maths and cross-source team resolution."""
from datetime import date, timedelta

import numpy as np
from django.test import SimpleTestCase, TestCase

from prediction_engine.dixon_coles import fit_model
from prediction_engine.markets import edge, evaluate_markets, implied_prob, kelly_stake, market_probs


class MarketMathsTests(SimpleTestCase):
    def test_implied_prob(self):
        self.assertAlmostEqual(implied_prob(2.0), 0.5)
        self.assertIsNone(implied_prob(None))
        self.assertIsNone(implied_prob(1.0))

    def test_edge_positive_when_model_beats_odds(self):
        # 60% chance at evens = +20% expected value
        self.assertAlmostEqual(edge(0.6, 2.0), 0.2)
        # 40% chance at evens is a losing bet
        self.assertAlmostEqual(edge(0.4, 2.0), -0.2)

    def test_kelly_zero_without_edge(self):
        self.assertEqual(kelly_stake(0.4, 2.0), 0.0)
        # quarter-Kelly of the full Kelly fraction (p*o-1)/(o-1) = 0.2
        self.assertAlmostEqual(kelly_stake(0.6, 2.0), 0.25 * 0.2, places=4)


class ScoreMatrixTests(SimpleTestCase):
    def _synthetic_model(self):
        """Fit on synthetic data: a strong home team pattern with ~1.9 home goals."""
        rng = np.random.default_rng(42)
        teams = list(range(8))
        rows = []
        start = date(2024, 8, 1)
        for round_num in range(40):
            for i in range(0, 8, 2):
                home, away = teams[i], teams[i + 1]
                rows.append((
                    start + timedelta(days=round_num * 7),
                    home, away,
                    int(rng.poisson(1.9)), int(rng.poisson(1.1)),
                ))
            teams = [teams[0]] + teams[2:] + [teams[1]]  # rotate pairings
        return fit_model(rows)

    def test_probabilities_sum_to_one(self):
        model = self._synthetic_model()
        self.assertIsNotNone(model)
        matrix = model.score_matrix(0, 1)
        self.assertAlmostEqual(matrix.sum(), 1.0, places=6)

        probs = market_probs(matrix)
        self.assertAlmostEqual(probs["home"] + probs["draw"] + probs["away"], 1.0, places=6)
        self.assertAlmostEqual(probs["over_2.5"] + probs["under_2.5"], 1.0, places=6)
        self.assertAlmostEqual(probs["btts_yes"] + probs["btts_no"], 1.0, places=6)

    def test_home_advantage_learned(self):
        model = self._synthetic_model()
        # data was generated with a big home edge; rows carry no league key
        self.assertGreater(model.home_advs[None], 0.1)

    def test_more_goals_expected_means_higher_over_prob(self):
        model = self._synthetic_model()
        probs = market_probs(model.score_matrix(0, 1))
        self.assertGreater(probs["over_0.5"], probs["over_2.5"])
        self.assertGreater(probs["over_2.5"], probs["over_5.5"])


class EvaluateMarketsTests(SimpleTestCase):
    class FakeOdds:
        home_odds = 2.1
        draw_odds = 3.4
        away_odds = 3.6
        avg_home_odds = 2.05
        avg_draw_odds = 3.35
        avg_away_odds = 3.55
        max_home_odds = 2.2
        max_draw_odds = 3.5
        max_away_odds = 3.8
        over25_odds = 1.9
        under25_odds = 1.9
        max_over25_odds = None
        max_under25_odds = None

    def test_pure_model_edges_with_blending_disabled(self):
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20, "over_2.5": 0.5, "under_2.5": 0.5}
        markets = evaluate_markets(probs, self.FakeOdds(), blend_weight=0)
        self.assertEqual(len(markets), 5)
        # Edges are computed at the base (B365) price, NOT the outlier-prone max:
        # home = 0.55 * 2.1 - 1 = +0.155, and it should be the top edge / value.
        self.assertEqual(markets[0]["key"], "home")
        self.assertTrue(markets[0]["value"])
        self.assertAlmostEqual(markets[0]["edge"], 0.155, places=6)
        # The better cross-book price is surfaced separately for display
        self.assertAlmostEqual(markets[0]["best_odds"], 2.2)
        # Sorted descending by edge
        edges = [m["edge"] for m in markets]
        self.assertEqual(edges, sorted(edges, reverse=True))

    def test_market_blend_shrinks_edges_toward_the_market(self):
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20, "over_2.5": 0.5, "under_2.5": 0.5}
        pure = {m["key"]: m for m in evaluate_markets(probs, self.FakeOdds(), blend_weight=0)}
        blended = {m["key"]: m for m in evaluate_markets(probs, self.FakeOdds())}
        # Blending pulls the bet probability toward the (de-margined) market,
        # so the home edge must be smaller than the pure-model edge but positive.
        self.assertLess(blended["home"]["edge"], pure["home"]["edge"])
        self.assertGreater(blended["home"]["edge"], 0)
        self.assertLess(blended["home"]["bet_prob"], 0.55)

    def test_low_data_teams_blend_harder(self):
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20, "over_2.5": 0.5, "under_2.5": 0.5,
                 "meta": {"min_matches": 3}}
        low_data = {m["key"]: m for m in evaluate_markets(probs, self.FakeOdds())}
        probs_full = dict(probs, meta={"min_matches": 100})
        full_data = {m["key"]: m for m in evaluate_markets(probs_full, self.FakeOdds())}
        self.assertLess(low_data["home"]["edge"], full_data["home"]["edge"])

    def test_longshots_are_not_flagged_as_value(self):
        # 11% model prob at high odds: positive edge but below the probability floor
        probs = {"home": 0.80, "draw": 0.12, "away": 0.08}

        class LongshotOdds(self.FakeOdds):
            home_odds = 1.2
            draw_odds = 6.0
            away_odds = 18.0
            max_home_odds = None
            max_draw_odds = None
            max_away_odds = 20.0
            over25_odds = None
            under25_odds = None

        markets = {m["key"]: m for m in evaluate_markets(probs, LongshotOdds(), blend_weight=0)}
        self.assertGreater(markets["away"]["edge"], 0)
        self.assertFalse(markets["away"]["value"])

    def test_no_odds_returns_empty(self):
        self.assertEqual(evaluate_markets({"home": 0.5}, None), [])


class TeamResolutionTests(TestCase):
    def test_canonical_mapping_and_alias_creation(self):
        from data_collection.models import Team, TeamAlias
        from data_collection.scraping.team_names import resolve_team

        team = resolve_team("Man United", source="football-data")
        self.assertEqual(team.name, "Manchester United")
        self.assertTrue(TeamAlias.objects.filter(name="Man United", team=team).exists())

        # Same club from a different source resolves to the same row
        again = resolve_team("Manchester United", source="understat")
        self.assertEqual(again.id, team.id)
        self.assertEqual(Team.objects.filter(name__icontains="United").count(), 1)

    def test_fuzzy_match_reuses_existing_team(self):
        from data_collection.models import Team
        from data_collection.scraping.team_names import resolve_team

        existing = Team.objects.create(name="Borussia Dortmund")
        resolved = resolve_team("Dortmund", source="football-data")
        self.assertEqual(resolved.id, existing.id)

    def test_reserve_teams_never_merge_into_senior_club(self):
        from data_collection.models import Team
        from data_collection.scraping.team_names import resolve_team

        senior = resolve_team("Celta", source="football-data")
        self.assertEqual(senior.name, "Celta Vigo")
        reserve = resolve_team("Celta B", source="football-data")
        self.assertNotEqual(reserve.id, senior.id)
        self.assertEqual(reserve.name, "Celta B")
        # and the reverse: a senior name must not match the reserve team
        second_lookup = resolve_team("Celta Vigo", source="understat")
        self.assertEqual(second_lookup.id, senior.id)
