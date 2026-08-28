"""Repair reserve/B teams that were wrongly merged into their senior club.

Before the resolver learned to keep reserve names separate, spellings like
'Celta B' or 'Sociedad B' (Segunda Division) fuzzy-matched onto the senior
club, polluting its match history and ratings. This command:

1. Finds aliases with a reserve-style name ('X B', 'X II', 'X U21/U23')
   pointing at a non-reserve team, and repoints them to a dedicated team.
2. Detects seasons where the senior club appears in two divisions at once
   (impossible in reality - the lower-division entry is the reserve side)
   and moves those matches, stats and club-season rows to the reserve team.

Idempotent; safe to run on the production database after pulling this code.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from data_collection.models import ClubSeason, Match, MatchTeamStat, Team, TeamAlias
from data_collection.scraping.team_names import is_reserve_name


def division_rank(league):
    """Lower number = higher division (E0 < E1 < E2, SP1 < SP2...)."""
    code = league.fd_code or ""
    digits = "".join(c for c in code if c.isdigit())
    return int(digits) if digits else 99


class Command(BaseCommand):
    help = "Split wrongly-merged reserve/B teams out of their senior clubs."

    def handle(self, *args, **options):
        repaired = 0
        for alias in TeamAlias.objects.select_related("team"):
            if not (is_reserve_name(alias.name) and not is_reserve_name(alias.team.name)):
                continue

            senior = alias.team
            reserve, created = Team.objects.get_or_create(name=alias.name)
            alias.team = reserve
            alias.save(update_fields=["team"])
            self.stdout.write(
                f"Alias '{alias.name}' repointed from '{senior.name}' to its own team"
                f"{' (created)' if created else ''}."
            )

            # Seasons where the senior club sits in two divisions at once:
            # the lower division belongs to the reserve side.
            memberships = {}
            for cs in ClubSeason.objects.filter(team=senior).select_related("season", "league"):
                memberships.setdefault(cs.season_id, []).append(cs)

            for season_id, rows in memberships.items():
                if len(rows) < 2:
                    continue
                rows.sort(key=lambda cs: division_rank(cs.league))
                for cs in rows[1:]:  # everything below the top entry is the reserve's
                    moved_matches = Match.objects.filter(
                        Q(home_team=senior) | Q(away_team=senior),
                        season_id=season_id, league=cs.league,
                    )
                    count = 0
                    for match in moved_matches:
                        if match.home_team_id == senior.id:
                            match.home_team = reserve
                        if match.away_team_id == senior.id:
                            match.away_team = reserve
                        match.save()
                        MatchTeamStat.objects.filter(match=match, team=senior).update(team=reserve)
                        count += 1
                    ClubSeason.objects.get_or_create(team=reserve, season_id=season_id, league=cs.league)
                    cs.delete()
                    repaired += count
                    self.stdout.write(
                        f"  {cs.season.name} {cs.league.name}: moved {count} matches "
                        f"from '{senior.name}' to '{reserve.name}'."
                    )

        if repaired == 0:
            self.stdout.write("No wrongly-merged reserve teams found.")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done - {repaired} matches repointed. Re-run update_predictions to refresh ratings."
            ))
