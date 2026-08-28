"""Automatically settle pending bets whose match now has a final score.

Winnings on a win are recorded as net profit: stake * (decimal_odds - 1).
Bets of type 'other' are left for manual settlement.
"""
from django.core.management.base import BaseCommand

from data_collection.models import Bet


def _bet_won(bet, match):
    """True/False when the outcome is decidable, None for manual types."""
    total = match.home_score + match.away_score
    checks = {
        "over_0.5": total > 0.5,
        "over_1.5": total > 1.5,
        "over_2.5": total > 2.5,
        "over_3.5": total > 3.5,
        "under_2.5": total < 2.5,
        "under_3.5": total < 3.5,
        "under_4.5": total < 4.5,
        "under_5.5": total < 5.5,
        "home_win": match.home_score > match.away_score,
        "away_win": match.away_score > match.home_score,
        "draw": match.home_score == match.away_score,
        "btts": match.home_score > 0 and match.away_score > 0,
    }
    return checks.get(bet.bet_type)


class Command(BaseCommand):
    help = "Settle pending bets using final scores (bet_type 'other' is skipped)."

    def handle(self, *args, **options):
        pending = Bet.objects.filter(bet_result="pending").select_related("match")
        settled = skipped = 0

        for bet in pending:
            match = bet.match
            if not match.is_played:
                continue
            won = _bet_won(bet, match)
            if won is None:
                skipped += 1
                continue

            if won:
                bet.bet_result = "win"
                if bet.winnings is None and bet.decimal_odds:
                    bet.winnings = round(bet.stake * (bet.decimal_odds - 1), 2)
            else:
                bet.bet_result = "lose"
            bet.save()
            settled += 1
            self.stdout.write(
                f"  {match.home_team.name} {match.home_score}-{match.away_score} {match.away_team.name}: "
                f"{bet.get_bet_type_display()} -> {bet.bet_result.upper()}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Settled {settled} bets ({skipped} left for manual settlement)."
        ))
