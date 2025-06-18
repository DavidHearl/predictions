from django.core.management.base import BaseCommand
from data_collection.scraping.teams import *
from data_collection.scraping.players import *
from data_collection.scraping.matches import *


class Command(BaseCommand):
    help = "Builds and prints FBref URL based on database season/league"

    def handle(self, *args, **options):
        process_all_matches()
