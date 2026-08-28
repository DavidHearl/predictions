"""Team name resolution across data sources.

Every source spells team names differently (football-data.co.uk: 'Man United',
fbref: 'Manchester United', understat: 'Manchester United'). This module
resolves any incoming name to a single Team row using, in order:

1. A stored TeamAlias for that (name, source)
2. A curated canonical-name dictionary
3. Exact (case-insensitive) match on Team.name
4. High-confidence fuzzy match against existing names and aliases
5. Creation of a new Team

Successful resolutions are recorded as TeamAlias rows so subsequent imports
hit step 1 immediately.
"""
import logging
import re

from rapidfuzz import fuzz, process
from unidecode import unidecode

from data_collection.models import Team, TeamAlias

log = logging.getLogger("scraping.team_names")

# Maps source-specific spellings to a canonical full name (fbref-style naming
# so existing fbref-scraped Team rows are reused rather than duplicated).
CANONICAL_NAMES = {
    # England
    "Man United": "Manchester United",
    "Man Utd": "Manchester United",
    "Man City": "Manchester City",
    "Nott'm Forest": "Nottingham Forest",
    "Sheffield Weds": "Sheffield Wednesday",
    "QPR": "Queens Park Rangers",
    "Wolves": "Wolverhampton Wanderers",
    "West Brom": "West Bromwich Albion",
    "West Ham": "West Ham United",
    "Newcastle": "Newcastle United",
    "Tottenham": "Tottenham Hotspur",
    "Spurs": "Tottenham Hotspur",
    "Brighton": "Brighton and Hove Albion",
    "Leeds": "Leeds United",
    "Leicester": "Leicester City",
    "Norwich": "Norwich City",
    "Stoke": "Stoke City",
    "Swansea": "Swansea City",
    "Cardiff": "Cardiff City",
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
    "Luton": "Luton Town",
    "Blackburn": "Blackburn Rovers",
    "Bolton": "Bolton Wanderers",
    "Charlton": "Charlton Athletic",
    "Derby": "Derby County",
    "Huddersfield": "Huddersfield Town",
    "Preston": "Preston North End",
    "Rotherham": "Rotherham United",
    "Birmingham": "Birmingham City",
    "Coventry": "Coventry City",
    "Oxford": "Oxford United",
    "Plymouth": "Plymouth Argyle",
    "Wigan": "Wigan Athletic",
    "Peterboro": "Peterborough United",
    "Bristol City": "Bristol City",
    "Bristol Rvs": "Bristol Rovers",
    # Spain
    "Ath Madrid": "Atletico Madrid",
    "Ath Bilbao": "Athletic Club",
    "Athletic Bilbao": "Athletic Club",
    "Espanol": "Espanyol",
    "Espanyol": "Espanyol",
    "Sociedad": "Real Sociedad",
    "Betis": "Real Betis",
    "Celta": "Celta Vigo",
    "Vallecano": "Rayo Vallecano",
    "La Coruna": "Deportivo La Coruna",
    "Oviedo": "Real Oviedo",
    # Germany
    "Ein Frankfurt": "Eintracht Frankfurt",
    "FC Koln": "Koln",
    "FC Cologne": "Koln",
    "M'gladbach": "Monchengladbach",
    "Borussia M.Gladbach": "Monchengladbach",
    "Dortmund": "Borussia Dortmund",
    "Borussia Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Hertha": "Hertha BSC",
    "Greuther Furth": "Greuther Furth",
    "Fortuna Dusseldorf": "Dusseldorf",
    "Hamburg": "Hamburger SV",
    "Schalke 04": "Schalke 04",
    "St Pauli": "St Pauli",
    "Werder Bremen": "Werder Bremen",
    "RB Leipzig": "RB Leipzig",
    "RasenBallsport Leipzig": "RB Leipzig",
    "Union Berlin": "Union Berlin",
    # Italy
    "Inter": "Internazionale",
    "Milan": "AC Milan",
    "Verona": "Hellas Verona",
    # France
    "Paris SG": "Paris Saint-Germain",
    "Paris Saint Germain": "Paris Saint-Germain",
    "St Etienne": "Saint-Etienne",
    "Saint-Etienne": "Saint-Etienne",
}

FUZZY_THRESHOLD = 90

# Reserve/B teams ("Celta B", "Sociedad B", "Stuttgart II", "Barcelona U23")
# are separate entities from the senior club and must never be fuzzy-merged
# into it - their results would pollute the senior team's ratings.
RESERVE_RE = re.compile(r"\s(B|II|U2[13])$")


def is_reserve_name(name):
    return bool(RESERVE_RE.search((name or "").strip()))


def normalise(name):
    return unidecode((name or "").strip())


def resolve_team(raw_name, source=""):
    """Return the Team for a source-specific name, creating one if needed.
    Returns None only for empty input."""
    raw_name = (raw_name or "").strip()
    if not raw_name:
        return None

    # 1. Stored alias (source-specific first, then any source)
    alias = (
        TeamAlias.objects.filter(name=raw_name, source=source).first()
        or TeamAlias.objects.filter(name=raw_name).first()
    )
    if alias:
        return alias.team

    norm = normalise(raw_name)
    canonical = CANONICAL_NAMES.get(raw_name) or CANONICAL_NAMES.get(norm) or norm
    reserve = is_reserve_name(raw_name)

    # 2/3. Exact (case-insensitive) match on canonical or raw name.
    # Reserve teams skip the canonical dictionary (it maps senior clubs).
    if reserve:
        team = Team.objects.filter(name__iexact=raw_name).first()
        canonical = norm
    else:
        team = (
            Team.objects.filter(name__iexact=canonical).first()
            or Team.objects.filter(name__iexact=raw_name).first()
        )

    # 4. High-confidence fuzzy match against existing names + aliases.
    # Never fuzzy-match reserve names, and never fuzzy-match a non-reserve
    # name onto a reserve team.
    if team is None and not reserve:
        candidates = {}
        for t in Team.objects.all():
            if not is_reserve_name(t.name):
                candidates.setdefault(normalise(t.name).lower(), t)
        for a in TeamAlias.objects.select_related("team"):
            if not is_reserve_name(a.name) and not is_reserve_name(a.team.name):
                candidates.setdefault(normalise(a.name).lower(), a.team)

        if candidates:
            best = process.extractOne(
                canonical.lower(), list(candidates.keys()), scorer=fuzz.token_set_ratio
            )
            if best and best[1] >= FUZZY_THRESHOLD:
                team = candidates[best[0]]
                log.info("Fuzzy-matched '%s' -> '%s' (%.0f)", raw_name, team.name, best[1])

    # 5. Create
    if team is None:
        team = Team.objects.create(name=canonical)
        log.info("Created new team '%s' (from '%s', source=%s)", canonical, raw_name, source)

    # Record the alias for next time (only when the spelling differs)
    if raw_name != team.name:
        TeamAlias.objects.get_or_create(name=raw_name, source=source, defaults={"team": team})

    return team
