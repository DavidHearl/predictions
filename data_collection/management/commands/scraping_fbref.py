from django.core.management.base import BaseCommand
from data_collection.scraping.teams import *


class Command(BaseCommand):
    help = "Builds and prints FBref URL based on database season/league"

    def handle(self, *args, **options):
        populate_team_data()