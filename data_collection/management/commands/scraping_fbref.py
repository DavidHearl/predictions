from django.core.management.base import BaseCommand
from data_collection.scraping.teams import *


class Command(BaseCommand):
    help = "Builds and prints FBref URL based on database season/league"

    def handle(self, *args, **options):
        urls = build_fbref_urls()  # This returns a list of URLs
        
        # Loop through each URL in the list
        for url in urls:
            self.stdout.write(url)
