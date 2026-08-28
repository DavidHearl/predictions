"""Importer for football-data.co.uk.

Two feeds:
- Per-season results CSVs (https://www.football-data.co.uk/mmz4281/<code>/<div>.csv)
  containing final scores, match stats (shots, corners, cards, sometimes xG)
  and closing bookmaker odds.
- fixtures.csv with upcoming fixtures and current pre-match odds.

Both are free, fast (one request per league-season) and far more reliable than
scraping HTML, so this is the primary source for results and odds.
"""
import io
import logging
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

import pandas as pd
from django.utils import timezone

from data_collection.models import (
    ClubSeason, League, Match, MatchOdds, MatchTeamStat, Season,
)
from .http import fetch
from .team_names import resolve_team

log = logging.getLogger("scraping.football_data")

UK_TZ = ZoneInfo("Europe/London")
SOURCE = "football-data"

RESULTS_URL = "https://www.football-data.co.uk/mmz4281/{code}/{div}.csv"
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"


def season_to_code(season_name):
    """'2026-2027' -> '2627'"""
    start, end = season_name.split("-")
    return start[-2:] + end[-2:]


def season_name_for_date(d):
    """European season for a date: July onwards belongs to the season starting that year."""
    if d.month >= 7:
        return f"{d.year}-{d.year + 1}"
    return f"{d.year - 1}-{d.year}"


def _parse_kickoff(date_str, time_str):
    """Combine the CSV date (dd/mm/yyyy or dd/mm/yy) and optional time into an aware datetime."""
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    parsed_date = None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    if parsed_date is None:
        return None

    kickoff_time = dt_time(15, 0)
    time_str = (time_str or "").strip()
    if time_str:
        try:
            kickoff_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            pass
    return datetime.combine(parsed_date, kickoff_time, tzinfo=UK_TZ)


def _num(row, *columns):
    """First parseable float among the given columns, else None."""
    for col in columns:
        if col in row:
            value = row[col]
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if pd.notna(value):
                return value
    return None


def _int(row, *columns):
    value = _num(row, *columns)
    return int(value) if value is not None else None


def _read_csv(content):
    """football-data CSVs occasionally contain stray commas/encoding quirks."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=encoding, on_bad_lines="skip")
        except Exception as e:  # noqa: BLE001 - fall through to next encoding
            last_error = e
    log.error("Could not parse CSV: %s", last_error)
    return None


def find_or_create_match(season, league, home_team, away_team, kickoff):
    """Locate a match by its natural key (each pairing occurs once per season per league).

    Matching by (season, league, home, away) instead of date means fixtures that get
    rescheduled, or that were first created by a different scraper, are updated
    rather than duplicated.
    """
    match = Match.objects.filter(
        season=season, league=league, home_team=home_team, away_team=away_team
    ).first()
    created = False
    if match is None:
        match = Match.objects.create(
            season=season, league=league,
            home_team=home_team, away_team=away_team,
            date=kickoff,
        )
        created = True
    elif kickoff and match.date != kickoff:
        match.date = kickoff
        match.save(update_fields=["date"])
    return match, created


def _upsert_odds(match, row, is_closing):
    defaults = {
        "home_odds": _num(row, "B365H"),
        "draw_odds": _num(row, "B365D"),
        "away_odds": _num(row, "B365A"),
        "max_home_odds": _num(row, "MaxH", "BbMxH"),
        "max_draw_odds": _num(row, "MaxD", "BbMxD"),
        "max_away_odds": _num(row, "MaxA", "BbMxA"),
        "avg_home_odds": _num(row, "AvgH", "BbAvH"),
        "avg_draw_odds": _num(row, "AvgD", "BbAvD"),
        "avg_away_odds": _num(row, "AvgA", "BbAvA"),
        "over25_odds": _num(row, "B365>2.5", "BbMx>2.5"),
        "under25_odds": _num(row, "B365<2.5", "BbMx<2.5"),
        "max_over25_odds": _num(row, "Max>2.5"),
        "max_under25_odds": _num(row, "Max<2.5"),
        "is_closing": is_closing,
    }
    if all(v is None for k, v in defaults.items() if k != "is_closing"):
        return
    MatchOdds.objects.update_or_create(match=match, source=SOURCE, defaults=defaults)


def _upsert_team_stat(match, team, is_home, row):
    prefix = "H" if is_home else "A"
    stats = {
        "total_shots": _int(row, f"{prefix}S"),
        "shots_on_target": _int(row, f"{prefix}ST"),
        "fouls": _int(row, f"{prefix}F"),
        "corners": _int(row, f"{prefix}C"),
        "yellow_cards": _int(row, f"{prefix}Y"),
        "red_cards": _int(row, f"{prefix}R"),
    }
    xg = _num(row, f"{prefix}xG")
    xga = _num(row, "AxG" if is_home else "HxG")

    if all(v is None for v in stats.values()) and xg is None:
        return

    stat, _ = MatchTeamStat.objects.get_or_create(
        match=match, team=team, defaults={"is_home": is_home}
    )
    stat.is_home = is_home
    for field, value in stats.items():
        if value is not None:
            setattr(stat, field, value)
    # Don't clobber xG that fbref/understat may have provided
    if xg is not None and stat.expected_goals is None:
        stat.expected_goals = xg
    if xga is not None and stat.expected_goals_against is None:
        stat.expected_goals_against = xga
    stat.save()


def import_results(league, season):
    """Import one league-season results CSV. Returns (created, updated) counts."""
    code = season_to_code(season.name)
    url = RESULTS_URL.format(code=code, div=league.fd_code)
    response = fetch(url, allow_404=True)
    if response is None:
        log.info("No results file for %s %s (%s)", league.name, season.name, url)
        return (0, 0)

    df = _read_csv(response.content)
    if df is None or df.empty or "HomeTeam" not in df.columns:
        return (0, 0)

    created = updated = 0
    for _, row in df.iterrows():
        home_name = str(row.get("HomeTeam", "") or "").strip()
        away_name = str(row.get("AwayTeam", "") or "").strip()
        if not home_name or not away_name or home_name == "nan":
            continue

        kickoff = _parse_kickoff(str(row.get("Date", "")), str(row.get("Time", "")))
        if kickoff is None:
            continue

        home_team = resolve_team(home_name, source=SOURCE)
        away_team = resolve_team(away_name, source=SOURCE)

        match, was_created = find_or_create_match(season, league, home_team, away_team, kickoff)

        match.home_score = _int(row, "FTHG")
        match.away_score = _int(row, "FTAG")
        match.ht_home_score = _int(row, "HTHG")
        match.ht_away_score = _int(row, "HTAG")
        referee = str(row.get("Referee", "") or "").strip()
        if referee and referee != "nan" and not match.referee:
            match.referee = referee
        match.save()

        _upsert_team_stat(match, home_team, True, row)
        _upsert_team_stat(match, away_team, False, row)
        _upsert_odds(match, row, is_closing=True)

        for team in (home_team, away_team):
            ClubSeason.objects.get_or_create(team=team, season=season, league=league)

        if was_created:
            created += 1
        else:
            updated += 1

    log.info("%s %s: %d created, %d updated", league.name, season.name, created, updated)
    return (created, updated)


def import_fixtures():
    """Import upcoming fixtures (with current odds) for all leagues we track.
    Returns (created, updated) counts."""
    leagues = {l.fd_code: l for l in League.objects.exclude(fd_code__isnull=True).exclude(fd_code="")}
    if not leagues:
        log.warning("No leagues have fd_code set - nothing to import")
        return (0, 0)

    response = fetch(FIXTURES_URL)
    if response is None:
        return (0, 0)

    df = _read_csv(response.content)
    if df is None or df.empty:
        return (0, 0)

    created = updated = 0
    for _, row in df.iterrows():
        div = str(row.get("Div", "") or "").strip()
        league = leagues.get(div)
        if league is None:
            continue

        home_name = str(row.get("HomeTeam", "") or "").strip()
        away_name = str(row.get("AwayTeam", "") or "").strip()
        if not home_name or not away_name or home_name == "nan":
            continue

        kickoff = _parse_kickoff(str(row.get("Date", "")), str(row.get("Time", "")))
        if kickoff is None:
            continue

        season_name = season_name_for_date(kickoff.date())
        season, _ = Season.objects.get_or_create(name=season_name)

        home_team = resolve_team(home_name, source=SOURCE)
        away_team = resolve_team(away_name, source=SOURCE)

        match, was_created = find_or_create_match(season, league, home_team, away_team, kickoff)
        # Refresh pre-match odds, but never overwrite closing odds on a played match.
        has_closing = MatchOdds.objects.filter(match=match, source=SOURCE, is_closing=True).exists()
        if not (match.is_played and has_closing):
            _upsert_odds(match, row, is_closing=False)

        for team in (home_team, away_team):
            ClubSeason.objects.get_or_create(team=team, season=season, league=league)

        if was_created:
            created += 1
        else:
            updated += 1

    log.info("Fixtures: %d created, %d updated", created, updated)
    return (created, updated)
