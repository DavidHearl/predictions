from django.core.management.base import BaseCommand
from django.db.models import Q
from data_collection.models import *

class Command(BaseCommand):
    help = "Removes all data for seasons before 2001-2002"

    def handle(self, *args, **options):
        # Identify seasons before 2001-2002
        cutoff_year = 2001
        # Filter seasons where the first part of the name (before the dash) is less than cutoff_year
        old_seasons = Season.objects.filter(name__lt=f"{cutoff_year}-")
        
        # Count before deletion for reporting
        old_season_count = old_seasons.count()
        club_season_count = ClubSeason.objects.filter(season__in=old_seasons).count()
        match_count = Match.objects.filter(season__in=old_seasons).count()
        
        print(f"=== Preparing to delete data for {old_season_count} seasons before 2001-2002 ===")
        print(f"- Club seasons to delete: {club_season_count}")
        print(f"- Matches to delete: {match_count}")
        
        confirm = input("Are you sure you want to delete this data? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled.")
            return
            
        print("\n=== Deleting data... ===")
        
        Match.objects.filter(season__in=old_seasons).delete()
        ClubSeason.objects.filter(season__in=old_seasons).delete()
        deletion_count = old_seasons.delete()[0]
        
        print(f"\n=== Successfully deleted {deletion_count} seasons and all related data ===")