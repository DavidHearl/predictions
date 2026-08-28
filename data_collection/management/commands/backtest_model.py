"""Walk-forward backtest of the Dixon-Coles model.

For each week in the test window the model is refitted using only matches
before that week (no look-ahead), then evaluated on that week's matches:

- prediction quality: accuracy, log-loss (vs the bookmaker's implied
  probabilities as the benchmark to beat)
- betting simulation: flat 1-unit stake on every positive-edge market at
  Bet365 closing prices, reporting ROI

Example:
    python manage.py backtest_model --days 365
    python manage.py backtest_model --country England --days 180
"""
import math
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from data_collection.models import League, Match, MatchOdds
from prediction_engine.dixon_coles import fit_model
from prediction_engine.markets import evaluate_markets, market_probs
from prediction_engine.predictor import TRAINING_WINDOW_DAYS, build_goal_rows, build_xg_rows


class Command(BaseCommand):
    help = "Walk-forward backtest: model quality and betting ROI over a historical window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365,
                            help="Length of the test window ending today (default 365).")
        parser.add_argument("--country", type=str, default="",
                            help="Restrict to one country pool (e.g. England).")
        parser.add_argument("--min-edge", type=float, default=0.02,
                            help="Edge threshold for the betting simulation (default 2%%).")

    def handle(self, *args, **options):
        now = timezone.now()
        test_start = now - timedelta(days=options["days"])

        pools = defaultdict(list)
        for league in League.objects.exclude(fd_code__isnull=True).exclude(fd_code=""):
            pools[league.country or league.name].append(league)
        if options["country"]:
            pools = {c: ls for c, ls in pools.items() if c.lower() == options["country"].lower()}
        if not pools:
            self.stdout.write(self.style.ERROR("No matching leagues."))
            return

        total_correct = total_matches = 0
        model_logloss_sum = book_logloss_sum = 0.0
        book_covered = 0
        bets_placed = 0
        bet_returns = 0.0
        per_market = defaultdict(lambda: [0, 0.0])  # market -> [bets, profit]
        # Sweep of market-blend weights: log-loss of (1-w)*model + w*book
        blend_grid = [round(0.1 * i, 1) for i in range(11)]
        blend_logloss = {w: 0.0 for w in blend_grid}

        for country, leagues in pools.items():
            self.stdout.write(f"\n=== {country} ({', '.join(l.name for l in leagues)}) ===")
            test_matches = list(
                Match.objects.filter(
                    league__in=leagues, date__gte=test_start, date__lte=now,
                    home_score__isnull=False, away_score__isnull=False,
                ).select_related("home_team", "away_team").order_by("date")
            )
            if not test_matches:
                self.stdout.write("  No played matches in window.")
                continue

            # Group test matches by ISO week so we refit ~weekly
            weeks = defaultdict(list)
            for m in test_matches:
                weeks[m.date.isocalendar()[:2]].append(m)

            for week_key in sorted(weeks):
                week_matches = weeks[week_key]
                cutoff = min(m.date for m in week_matches)
                train_since = cutoff - timedelta(days=TRAINING_WINDOW_DAYS)

                goal_rows = [
                    r for r in build_goal_rows(leagues, train_since)
                    if r[0] < cutoff.date()
                ]
                xg_rows = [
                    r for r in build_xg_rows(leagues, train_since)
                    if r[0] < cutoff.date()
                ]
                model = fit_model(goal_rows, xg_rows=xg_rows, reference_date=cutoff.date())
                if model is None:
                    continue

                for match in week_matches:
                    matrix = model.score_matrix(match.home_team_id, match.away_team_id, match.league_id)
                    if matrix is None:
                        continue
                    probs = market_probs(matrix)
                    home_n = model.match_counts.get(match.home_team_id, 0)
                    away_n = model.match_counts.get(match.away_team_id, 0)
                    probs["meta"] = {"min_matches": min(home_n, away_n)}

                    actual = ("home" if match.home_score > match.away_score
                              else "away" if match.away_score > match.home_score else "draw")
                    predicted = max(("home", "draw", "away"), key=lambda k: probs[k])
                    total_matches += 1
                    total_correct += int(predicted == actual)
                    model_logloss_sum += -math.log(max(probs[actual], 1e-12))

                    odds = MatchOdds.objects.filter(match=match, source="football-data").first()
                    if odds and odds.home_odds and odds.draw_odds and odds.away_odds:
                        inv = {
                            "home": 1 / odds.home_odds,
                            "draw": 1 / odds.draw_odds,
                            "away": 1 / odds.away_odds,
                        }
                        overround = sum(inv.values())
                        book_probs = {k: v / overround for k, v in inv.items()}
                        book_logloss_sum += -math.log(max(book_probs[actual], 1e-12))
                        book_covered += 1

                        for w in blend_grid:
                            blended = (1 - w) * probs[actual] + w * book_probs[actual]
                            blend_logloss[w] += -math.log(max(blended, 1e-12))

                        # Betting sim using the exact same market evaluation the
                        # site's value matrix uses (market-blended, longshot-gated).
                        total_goals = match.home_score + match.away_score
                        won_by_key = {
                            "home": actual == "home",
                            "draw": actual == "draw",
                            "away": actual == "away",
                            "over_2.5": total_goals > 2.5,
                            "under_2.5": total_goals < 2.5,
                        }
                        for market in evaluate_markets(probs, odds):
                            if not market["value"] or market["edge"] < options["min_edge"]:
                                continue
                            won = won_by_key[market["key"]]
                            bets_placed += 1
                            profit = (market["odds"] - 1) if won else -1.0
                            bet_returns += profit
                            per_market[market["key"]][0] += 1
                            per_market[market["key"]][1] += profit

        if not total_matches:
            self.stdout.write(self.style.ERROR("No matches evaluated."))
            return

        self.stdout.write("\n===== Backtest summary =====")
        self.stdout.write(f"Matches evaluated:       {total_matches}")
        self.stdout.write(f"1X2 accuracy:            {total_correct / total_matches:.1%}")
        self.stdout.write(f"Model log-loss:          {model_logloss_sum / total_matches:.4f}")
        if book_covered:
            self.stdout.write(f"Bookmaker log-loss:      {book_logloss_sum / book_covered:.4f} "
                              f"(lower is better; the bookmaker is the benchmark)")
            self.stdout.write("\nBlend-weight sweep (log-loss of (1-w)*model + w*market):")
            best_w = min(blend_logloss, key=lambda w: blend_logloss[w])
            for w in blend_grid:
                marker = "  <- best" if w == best_w else ""
                self.stdout.write(f"  w={w:.1f}: {blend_logloss[w] / book_covered:.4f}{marker}")
        self.stdout.write(f"\nBetting sim (edge >= {options['min_edge']:.0%}, 1 unit flat stakes, closing prices):")
        self.stdout.write(f"  Bets placed:           {bets_placed}")
        self.stdout.write(f"  Profit:                {bet_returns:+.1f} units")
        if bets_placed:
            self.stdout.write(f"  ROI:                   {bet_returns / bets_placed:+.1%}")
        for key, (n, profit) in sorted(per_market.items()):
            if n:
                self.stdout.write(f"    {key:<10} {n:>4} bets, {profit:+7.1f} units ({profit / n:+.1%} ROI)")
