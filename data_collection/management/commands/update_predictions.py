"""Fit the Dixon-Coles models and generate predictions for upcoming fixtures.

Examples:
    python manage.py update_predictions
    python manage.py update_predictions --horizon 7
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from data_collection.models import MatchOdds, Prediction
from prediction_engine.markets import evaluate_markets
from prediction_engine.predictor import update_predictions


class Command(BaseCommand):
    help = "Fit prediction models and store predictions (with market probabilities) for upcoming fixtures."

    def add_arguments(self, parser):
        parser.add_argument("--horizon", type=int, default=14,
                            help="How many days ahead to predict (default 14).")
        parser.add_argument("--min-edge", type=float, default=0.0,
                            help="Minimum edge for the value-bet summary printout (default 0).")

    def handle(self, *args, **options):
        self.stdout.write("Fitting Dixon-Coles models per country pool...")
        predicted, skipped = update_predictions(
            horizon_days=options["horizon"], verbose=self.stdout.write
        )
        self.stdout.write(self.style.SUCCESS(
            f"Predictions stored for {predicted} fixtures ({skipped} skipped - unknown teams)."
        ))

        # Value-bet summary: cross fresh predictions with stored odds
        self.stdout.write("\nTop value bets (model probability vs best bookmaker odds):")
        rows = []
        predictions = (
            Prediction.objects.filter(
                match__home_score__isnull=True,
                match__date__gte=timezone.now(),
            )
            .select_related("match__home_team", "match__away_team", "match__league")
            .order_by("match__date")
        )
        for prediction in predictions:
            odds = MatchOdds.objects.filter(match=prediction.match).first()
            if odds is None or not prediction.market_probs:
                continue
            for market in evaluate_markets(prediction.market_probs, odds):
                if market["value"] and market["edge"] >= options["min_edge"]:
                    rows.append((market["edge"], prediction.match, market))

        rows.sort(key=lambda r: r[0], reverse=True)
        if not rows:
            self.stdout.write("  (none found - no positive-edge markets right now)")
        for edge_value, match, market in rows[:20]:
            self.stdout.write(
                f"  {match.date:%a %d %b %H:%M}  {match.home_team.name} v {match.away_team.name}  "
                f"[{match.league.name}]  {market['market']}: "
                f"model {market['model_prob']:.0%} / blended {market['bet_prob']:.0%} "
                f"vs odds {market['odds']:.2f} "
                f"(edge {edge_value:+.1%}, ¼-Kelly {market['kelly']:.1%} of bankroll)"
            )
