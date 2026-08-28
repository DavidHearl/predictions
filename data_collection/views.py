from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, IntegerField, Q, Sum, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import PlayerForm
from .models import (
    Bet, BettingAccount, ClubSeason, League, Match, MatchOdds,
    MatchPlayerStat, MatchShot, MatchTeamStat, Player, Prediction, Season, Team,
)
from .utils import get_recent_results
from prediction_engine.markets import evaluate_markets


def _can_view_predictions(request):
    """Prediction pages are private; allow superusers (and anyone in local DEBUG runs)."""
    return request.user.is_superuser or settings.DEBUG


def _match_card(match):
    """Assemble everything the templates need for one fixture card."""
    prediction = getattr(match, "prediction", None)
    odds = match.odds.filter(source="football-data").first()
    markets = evaluate_markets(prediction.market_probs, odds) if prediction and prediction.market_probs else []
    value_bets = [m for m in markets if m["value"]]

    top_scores = []
    market_probs = prediction.market_probs if prediction else None
    if market_probs:
        top_scores = market_probs.get("top_scores", [])[:3]

    return {
        "match": match,
        "prediction": prediction,
        "odds": odds,
        "markets": markets,
        "value_bets": value_bets,
        "top_scores": top_scores,
        "home_form": get_recent_results(match.home_team, match.date),
        "away_form": get_recent_results(match.away_team, match.date),
        "market_probs": market_probs,
    }


def home(request):
    if not _can_view_predictions(request):
        return render(request, "data_collection/home.html", {"access_denied": True})

    today = date.today()

    match_dates = list(
        Match.objects.order_by("date__date").values_list("date__date", flat=True).distinct()
    )
    match_dates_str = [d.strftime("%Y-%m-%d") for d in match_dates]

    # Default to the next day with matches (or today)
    next_match_date = next((d for d in match_dates if d >= today), today)

    selected_date_str = request.GET.get("match_date")
    if selected_date_str:
        try:
            selected_date = date.fromisoformat(selected_date_str)
        except ValueError:
            selected_date = next_match_date
    else:
        selected_date = next_match_date

    league_id = request.GET.get("league") or ""
    matches = (
        Match.objects.filter(date__date=selected_date)
        .select_related("home_team", "away_team", "league", "season", "prediction")
        .prefetch_related("odds")
        .order_by("league__name", "date")
    )
    if league_id:
        matches = matches.filter(league_id=league_id)

    match_data = [_match_card(m) for m in matches]

    # Headline value bets across the next week for the banner
    week_ahead = timezone.now() + timedelta(days=7)
    upcoming_predictions = (
        Prediction.objects.filter(
            match__home_score__isnull=True,
            match__date__gte=timezone.now(),
            match__date__lte=week_ahead,
        )
        .select_related("match__home_team", "match__away_team", "match__league")
        .prefetch_related("match__odds")
    )
    headline_bets = []
    for prediction in upcoming_predictions:
        odds = prediction.match.odds.filter(source="football-data").first()
        if not odds or not prediction.market_probs:
            continue
        for market in evaluate_markets(prediction.market_probs, odds):
            if market["value"]:
                headline_bets.append({"match": prediction.match, **market})
    headline_bets.sort(key=lambda b: b["edge"], reverse=True)

    context = {
        "matches": match_data,
        "selected_date": selected_date,
        "match_dates": match_dates_str,
        "leagues": League.objects.order_by("name"),
        "selected_league": league_id,
        "headline_bets": headline_bets[:5],
        "prediction_count": Prediction.objects.count(),
    }
    return render(request, "data_collection/home.html", context)


def value_bets(request):
    """The betting decision matrix: every priceable market on upcoming fixtures,
    ranked by model edge over the bookmaker."""
    if not _can_view_predictions(request):
        return render(request, "data_collection/value_bets.html", {"access_denied": True})

    try:
        horizon_days = min(int(request.GET.get("days", 7)), 30)
    except ValueError:
        horizon_days = 7
    try:
        min_edge = float(request.GET.get("min_edge", 0))
    except ValueError:
        min_edge = 0.0
    league_id = request.GET.get("league") or ""
    market_filter = request.GET.get("market") or ""

    predictions = (
        Prediction.objects.filter(
            match__home_score__isnull=True,
            match__date__gte=timezone.now() - timedelta(hours=2),
            match__date__lte=timezone.now() + timedelta(days=horizon_days),
        )
        .select_related("match__home_team", "match__away_team", "match__league")
        .prefetch_related("match__odds")
        .order_by("match__date")
    )
    if league_id:
        predictions = predictions.filter(match__league_id=league_id)

    rows = []
    fixtures_covered = 0
    for prediction in predictions:
        odds = prediction.match.odds.filter(source="football-data").first()
        if not odds or not prediction.market_probs:
            continue
        fixtures_covered += 1
        for market in evaluate_markets(prediction.market_probs, odds):
            if market["edge"] is None or market["edge"] < min_edge:
                continue
            if market_filter and market["key"] != market_filter:
                continue
            rows.append({
                "match": prediction.match,
                "prediction": prediction,
                **market,
            })

    sort = request.GET.get("sort", "edge")
    if sort == "date":
        rows.sort(key=lambda r: r["match"].date)
    elif sort == "prob":
        rows.sort(key=lambda r: r["model_prob"], reverse=True)
    else:
        rows.sort(key=lambda r: r["edge"], reverse=True)

    market_choices = [
        ("home", "Home win"), ("draw", "Draw"), ("away", "Away win"),
        ("over_2.5", "Over 2.5"), ("under_2.5", "Under 2.5"),
    ]

    value_rows = [r for r in rows if r["value"]]
    strong_count = sum(1 for r in value_rows if r.get("tier") == "strong")
    best_edge = max((r["edge"] for r in value_rows), default=None)

    context = {
        "rows": rows,
        "value_count": len(value_rows),
        "strong_count": strong_count,
        "best_edge": best_edge,
        "fixtures_covered": fixtures_covered,
        "horizon_days": horizon_days,
        "min_edge": min_edge,
        "leagues": League.objects.order_by("name"),
        "selected_league": league_id,
        "market_choices": market_choices,
        "selected_market": market_filter,
        "sort": sort,
    }
    return render(request, "data_collection/value_bets.html", context)


def players(request):
    query = request.GET.get("q", "")
    missing_data = request.GET.get("missing_data") == "on"

    players_qs = Player.objects.all().order_by("name")

    if query:
        players_qs = players_qs.filter(name__icontains=query)

    if missing_data:
        players_qs = players_qs.filter(
            Q(height__isnull=True) |
            Q(weight__isnull=True) |
            Q(birth_date__isnull=True) |
            Q(nationality__isnull=True)
        )

    total_count = Player.objects.count()
    filtered_count = players_qs.count()

    paginator = Paginator(players_qs, 200)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "data_collection/players.html",
        {
            "players": page_obj.object_list,
            "page_obj": page_obj,
            "query": query,
            "missing_data": missing_data,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    return render(request, "data_collection/player_detail.html", {"player": player})


def player_edit(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if request.method == "POST":
        form = PlayerForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            return redirect("player_detail", pk=player.pk)
    else:
        form = PlayerForm(instance=player)
    return render(request, "data_collection/player_edit.html", {"form": form, "player": player})


def matches(request):
    season_id = request.GET.get("season")
    team_id = request.GET.get("team")
    league_id = request.GET.get("league")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    matches_qs = (
        Match.objects.all()
        .select_related("home_team", "away_team", "season", "league")
        .order_by("-date")
    )

    if season_id:
        matches_qs = matches_qs.filter(season_id=season_id)
    if league_id:
        matches_qs = matches_qs.filter(league_id=league_id)
    if team_id:
        matches_qs = matches_qs.filter(Q(home_team_id=team_id) | Q(away_team_id=team_id))

    if date_from:
        try:
            matches_qs = matches_qs.filter(date__gte=datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            matches_qs = matches_qs.filter(date__lte=datetime.strptime(date_to, "%Y-%m-%d"))
        except ValueError:
            pass

    total_count = Match.objects.count()
    filtered_count = matches_qs.count()

    seasons = Season.objects.all().order_by("-name")
    teams = Team.objects.all().order_by("name")
    leagues = League.objects.all().order_by("name")

    paginator = Paginator(matches_qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "data_collection/matches.html",
        {
            "matches": page_obj.object_list,
            "page_obj": page_obj,
            "seasons": seasons,
            "teams": teams,
            "leagues": leagues,
            "selected_season": season_id,
            "selected_team": team_id,
            "selected_league": league_id,
            "date_from": date_from,
            "date_to": date_to,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.select_related("home_team", "away_team", "league", "season"), pk=pk
    )
    home_stats = MatchTeamStat.objects.filter(match=match, team=match.home_team).first()
    away_stats = MatchTeamStat.objects.filter(match=match, team=match.away_team).first()
    shots = MatchShot.objects.filter(match=match).select_related("team", "player", "assisted_by").order_by("minute")
    player_stats = MatchPlayerStat.objects.filter(match=match).select_related("player", "team")

    prediction = getattr(match, "prediction", None)
    odds = match.odds.filter(source="football-data").first()
    markets = evaluate_markets(prediction.market_probs, odds) if prediction and prediction.market_probs else []

    # Head-to-head comparison rows with percentage widths for the bars
    h2h_rows = []
    if home_stats and away_stats:
        comparisons = [
            ("Expected goals (xG)", home_stats.expected_goals, away_stats.expected_goals, 2),
            ("Possession %", home_stats.possession, away_stats.possession, 0),
            ("Total shots", home_stats.total_shots, away_stats.total_shots, 0),
            ("Shots on target", home_stats.shots_on_target, away_stats.shots_on_target, 0),
            ("Passing accuracy %", home_stats.passing_accuracy, away_stats.passing_accuracy, 0),
            ("Corners", home_stats.corners, away_stats.corners, 0),
            ("Fouls", home_stats.fouls, away_stats.fouls, 0),
            ("Yellow cards", getattr(home_stats, "yellow_cards", None), getattr(away_stats, "yellow_cards", None), 0),
        ]
        for label, h, a, decimals in comparisons:
            if h is None and a is None:
                continue
            h = h or 0
            a = a or 0
            total = h + a
            h2h_rows.append({
                "label": label,
                "home": h,
                "away": a,
                "decimals": decimals,
                "home_pct": round(h / total * 100, 1) if total else 50,
                "away_pct": round(a / total * 100, 1) if total else 50,
            })

    return render(request, "data_collection/match_detail.html", {
        "match": match,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h_rows": h2h_rows,
        "shots": shots,
        "player_stats": player_stats,
        "prediction": prediction,
        "odds": odds,
        "markets": markets,
        "can_view": _can_view_predictions(request),
    })


def shots(request):
    """View for displaying shot statistics with filtering options"""
    team_id = request.GET.get("team")
    player_id = request.GET.get("player")
    match_id = request.GET.get("match")
    season_id = request.GET.get("season")
    outcome = request.GET.get("outcome")
    min_xg = request.GET.get("min_xg")
    max_distance = request.GET.get("max_distance")

    shots_qs = MatchShot.objects.all().select_related(
        "match__home_team", "match__away_team", "team", "player"
    ).order_by("-match__date", "minute")

    if team_id:
        shots_qs = shots_qs.filter(team_id=team_id)
    if player_id:
        shots_qs = shots_qs.filter(player_id=player_id)
    if match_id:
        shots_qs = shots_qs.filter(match_id=match_id)
    if season_id:
        shots_qs = shots_qs.filter(match__season_id=season_id)
    if outcome:
        shots_qs = shots_qs.filter(outcome=outcome)

    if min_xg:
        try:
            shots_qs = shots_qs.filter(expected_goals__gte=float(min_xg))
        except ValueError:
            pass
    if max_distance:
        try:
            shots_qs = shots_qs.filter(distance__lte=float(max_distance))
        except ValueError:
            pass

    total_count = MatchShot.objects.count()
    filtered_count = shots_qs.count()

    stats = shots_qs.aggregate(
        avg_xg=Avg("expected_goals"),
        avg_distance=Avg("distance"),
        total_xg=Sum("expected_goals"),
        total_shots=Count("id"),
        goals=Count(Case(When(outcome="Goal", then=1), output_field=IntegerField())),
    )

    conversion_rate = None
    if stats["goals"] and stats["total_shots"]:
        conversion_rate = (stats["goals"] / stats["total_shots"]) * 100
    stats["conversion_rate"] = conversion_rate

    teams = Team.objects.all().order_by("name")
    players = Player.objects.all().order_by("name")
    seasons = Season.objects.all().order_by("-name")
    outcome_choices = sorted(
        MatchShot.objects.exclude(outcome="").exclude(outcome__isnull=True)
        .values_list("outcome", flat=True).distinct()
    )

    paginator = Paginator(shots_qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "data_collection/shots.html",
        {
            "shots": page_obj.object_list,
            "page_obj": page_obj,
            "teams": teams,
            "players": players,
            "seasons": seasons,
            "outcome_choices": outcome_choices,
            "stats": stats,
            "selected_team": team_id,
            "selected_player": player_id,
            "selected_match": match_id,
            "selected_season": season_id,
            "selected_outcome": outcome,
            "min_xg": min_xg,
            "max_distance": max_distance,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def teams(request):
    """View for displaying teams with filtering options"""
    league_id = request.GET.get("league")
    season_id = request.GET.get("season")
    query = request.GET.get("q", "")

    teams_qs = Team.objects.all().order_by("name")

    if league_id:
        # ClubSeason carries the league directly (the old lookup went via Season,
        # which has no league field, and crashed this view).
        teams_qs = teams_qs.filter(clubseason__league_id=league_id).distinct()
    if season_id:
        teams_qs = teams_qs.filter(clubseason__season_id=season_id).distinct()
    if query:
        teams_qs = teams_qs.filter(name__icontains=query)

    total_count = Team.objects.count()
    filtered_count = teams_qs.count()

    leagues = League.objects.all().order_by("name")
    seasons = Season.objects.all().order_by("-name")

    paginator = Paginator(teams_qs, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "data_collection/teams.html",
        {
            "teams": page_obj.object_list,
            "page_obj": page_obj,
            "leagues": leagues,
            "seasons": seasons,
            "selected_league": league_id,
            "selected_season": season_id,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def team_detail(request, pk):
    """View for displaying detailed information about a team"""
    team = get_object_or_404(Team, pk=pk)

    team_seasons = ClubSeason.objects.filter(team=team).select_related(
        "season", "league"
    ).order_by("-season__name")

    recent_matches = (
        Match.objects.filter(Q(home_team=team) | Q(away_team=team))
        .select_related("home_team", "away_team", "league", "season")
        .order_by("-date")[:20]
    )

    players = Player.objects.filter(matchplayerstat__team=team).distinct().order_by("name")

    # Averages over the team's recorded match stats (only fields that exist!)
    avg_stats = MatchTeamStat.objects.filter(team=team).aggregate(
        expected_goals=Avg("expected_goals"),
        expected_goals_against=Avg("expected_goals_against"),
        possession=Avg("possession"),
        passing_accuracy=Avg("passing_accuracy"),
        total_shots=Avg("total_shots"),
        shots_on_target=Avg("shots_on_target"),
        corners=Avg("corners"),
        fouls=Avg("fouls"),
        yellow_cards=Avg("yellow_cards"),
    )
    avg_stats = {k: v for k, v in avg_stats.items() if v is not None}

    played = [m for m in recent_matches if m.is_played]
    wins = draws = losses = 0
    for m in played:
        if m.home_score == m.away_score:
            draws += 1
        elif (m.home_team_id == team.id) == (m.home_score > m.away_score):
            wins += 1
        else:
            losses += 1

    return render(
        request,
        "data_collection/team_detail.html",
        {
            "team": team,
            "team_seasons": team_seasons,
            "recent_matches": recent_matches,
            "players": players,
            "avg_stats": avg_stats,
            "record": {"wins": wins, "draws": draws, "losses": losses, "played": len(played)},
        },
    )


def bets(request):
    accounts = BettingAccount.objects.all().order_by("name")
    error = None

    if request.method == "POST":
        account_id = request.POST.get("account")
        match_id = request.POST.get("match")
        bet_type = request.POST.get("bet_type")
        fractional_odds = (request.POST.get("fractional_odds") or "").strip()
        stake_raw = request.POST.get("stake")
        winnings_raw = request.POST.get("winnings")
        bet_result = request.POST.get("bet_result") or "pending"
        notes = request.POST.get("notes", "")

        match = Match.objects.filter(id=match_id).first()
        account = BettingAccount.objects.filter(id=account_id).first()

        try:
            stake = float(stake_raw)
        except (TypeError, ValueError):
            stake = None

        if not match:
            error = "Select a match."
        elif not account:
            error = "Select an account."
        elif stake is None or stake <= 0:
            error = "Enter a valid stake."
        elif not fractional_odds:
            error = "Enter the odds (e.g. 5/2 or 3.5)."
        else:
            bet = Bet(
                account=account,
                match=match,
                bet_type=bet_type,
                fractional_odds=fractional_odds,
                stake=stake,
                bet_result=bet_result,
                notes=notes,
            )
            winnings = None
            if winnings_raw not in (None, ""):
                try:
                    winnings = float(winnings_raw)
                except ValueError:
                    winnings = None
            if winnings is None and bet_result == "win" and bet.decimal_odds:
                winnings = round(stake * (bet.decimal_odds - 1), 2)
            bet.winnings = winnings
            bet.save()
            return redirect("bets")

    bets_qs = (
        Bet.objects.select_related("account", "match__home_team", "match__away_team")
        .order_by("-placed_at", "-id")
    )

    # Matches selectable in the form: upcoming week + recent fortnight
    now = timezone.now()
    selectable_matches = (
        Match.objects.filter(
            date__gte=now - timedelta(days=14),
            date__lte=now + timedelta(days=10),
        )
        .select_related("home_team", "away_team", "league")
        .order_by("date")
    )

    # Prefill from a value-matrix "add to slip" link:
    # ?match=<id>&bet_type=<key>&odds=<decimal>&kelly=<fraction>
    prefill = {
        "match": request.GET.get("match", ""),
        "bet_type": request.GET.get("bet_type", ""),
        "odds": request.GET.get("odds", ""),
    }
    prefill_match = Match.objects.filter(id=prefill["match"]).select_related(
        "home_team", "away_team"
    ).first() if prefill["match"] else None
    # If the prefilled match falls outside the default window, still show it
    if prefill_match and not any(m.id == prefill_match.id for m in selectable_matches):
        selectable_matches = list(selectable_matches) + [prefill_match]

    suggested_stake = None
    try:
        kelly = float(request.GET.get("kelly", ""))
    except ValueError:
        kelly = None
    if kelly and kelly > 0 and accounts:
        # Quarter-Kelly fraction of the first account's current balance
        first = accounts[0]
        balance = first.starting_balance + sum(b.profit for b in first.bets.all())
        if balance > 0:
            suggested_stake = max(round(balance * kelly, 2), 0.1)
    prefill["stake"] = f"{suggested_stake:.2f}" if suggested_stake else ""

    # Account dashboards are computed purely from bet history (starting balance
    # + settled profit), so nothing is double-counted.
    for account in accounts:
        account_bets = list(account.bets.all())
        settled_profit = sum(b.profit for b in account_bets)
        pending_stake = sum(b.stake for b in account_bets if b.bet_result == "pending")
        bets_won = sum(1 for b in account_bets if b.bet_result == "win")
        bets_lost = sum(1 for b in account_bets if b.bet_result == "lose")

        account.bets_placed = len(account_bets)
        account.bets_won = bets_won
        account.bets_lost = bets_lost
        account.bets_pending = sum(1 for b in account_bets if b.bet_result == "pending")
        account.pending_stake = pending_stake
        account.current_balance_display = account.starting_balance + settled_profit - pending_stake
        account.starting_balance_display = account.starting_balance
        account.win_percentage = (
            round(bets_won / (bets_won + bets_lost) * 100, 1) if (bets_won + bets_lost) else 0
        )
        account.returns = settled_profit
        account.returns_percentage = (
            round(settled_profit / account.starting_balance * 100, 1)
            if account.starting_balance else 0
        )

    return render(
        request,
        "data_collection/bets.html",
        {
            "accounts": accounts,
            "bets": bets_qs,
            "selectable_matches": selectable_matches,
            "bet_type_choices": Bet.BET_TYPE_CHOICES,
            "error": error,
            "prefill": prefill,
            "suggested_stake": suggested_stake,
        },
    )
