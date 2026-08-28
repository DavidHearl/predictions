"""One-shot matchday refresh: current-season results, upcoming fixtures + odds,
understat xG, fresh predictions, and bet settlement.

This is the command to run daily (or before placing bets):
    python manage.py refresh_data
"""
from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand

from data_collection.scraping.football_data import season_name_for_date


class Command(BaseCommand):
    help = "Refresh current-season results, fixtures/odds and xG, then update predictions and settle bets."

    def handle(self, *args, **options):
        current_season = season_name_for_date(date.today())

        self.stdout.write(self.style.MIGRATE_HEADING("1/4 Results + fixtures (football-data.co.uk)"))
        call_command("import_football_data", start_season=current_season)

        self.stdout.write(self.style.MIGRATE_HEADING("2/4 xG (understat)"))
        call_command("scrape_understat")

        self.stdout.write(self.style.MIGRATE_HEADING("3/4 Predictions"))
        call_command("update_predictions")

        self.stdout.write(self.style.MIGRATE_HEADING("4/4 Settling bets"))
        call_command("settle_bets")

        self.stdout.write(self.style.SUCCESS("Refresh complete."))
