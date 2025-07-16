from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from .forms import *
from .utils import *
from django.core.paginator import Paginator
from django.db.models import Avg, Sum, Count, Case, When, IntegerField, FloatField, F
from datetime import date, datetime, timedelta


def home(request):
    form = MatchPredictionDateForm(request.GET or None)

    if form.is_valid():
        selected_date_str = form.cleaned_data.get("match_date")
        selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    else:
        selected_date = date.today()

    matches = Match.objects.filter(date__date=selected_date).order_by("date")

    match_data = []
    for match in matches:
        ml_prediction = predict_match_with_model(match)
        predicted_goals = predict_goals_for_match(match)
        goal_bets = get_goal_bets(predicted_goals) if predicted_goals is not None else []
        score_prediction = None
        if ml_prediction and predicted_goals is not None:
            score_prediction = estimate_score(ml_prediction["predicted_result"], predicted_goals)

        # Get players per team for the match
        home_players = (
            MatchPlayerStat.objects
            .filter(match=match, team=match.home_team)
            .select_related('player')
            .order_by('-minutes_played')[:11]  # assume top 11 are starters
        )

        away_players = (
            MatchPlayerStat.objects
            .filter(match=match, team=match.away_team)
            .select_related('player')
            .order_by('-minutes_played')[:11]
        )

        match_data.append({
            "match": match,
            "prediction": ml_prediction,
            "home_players": home_players,
            "away_players": away_players,
            "predicted_goals": predicted_goals,
            "goal_bets": goal_bets,
            "score_prediction": score_prediction,
        })

        bets = []
        if predicted_goals is not None:
            for threshold in [0.5, 1.5, 2.5, 3.5]:
                confidence = round(min(abs(predicted_goals - threshold) / 2.5, 1.0) * 100, 1)
                if predicted_goals > threshold:
                    bets.append({"type": f"Over {threshold} Goals", "confidence": confidence})
                else:
                    bets.append({"type": f"Under {threshold} Goals", "confidence": confidence})

    context = {
        "form": form,
        "matches": match_data,
        "selected_date": selected_date
    }

    return render(request, "data_collection/home.html", context)


def players(request):
    query = request.GET.get("q", "")
    missing_data = request.GET.get("missing_data") == "on"
    
    players_qs = Player.objects.all()
    
    if query:
        players_qs = players_qs.filter(name__icontains=query)
    
    if missing_data:
        players_qs = players_qs.filter(
            models.Q(height__isnull=True) | 
            models.Q(weight__isnull=True) | 
            models.Q(birth_date__isnull=True) |
            models.Q(nationality__isnull=True)
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
    # Filter by season, team, or date range if provided
    season_id = request.GET.get("season")
    team_id = request.GET.get("team")
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")
    
    matches_qs = Match.objects.all().order_by('-date')
    
    # Apply filters
    if season_id:
        matches_qs = matches_qs.filter(season_id=season_id)
    
    if team_id:
        matches_qs = matches_qs.filter(
            models.Q(home_team_id=team_id) | models.Q(away_team_id=team_id)
        )
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            matches_qs = matches_qs.filter(date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            matches_qs = matches_qs.filter(date__lte=to_date)
        except ValueError:
            pass
    
    # Get counts for context
    total_count = Match.objects.count()
    filtered_count = matches_qs.count()
    
    # Get all seasons and teams for filter dropdowns
    seasons = Season.objects.all().order_by('-name')
    teams = Team.objects.all().order_by('name')
    
    # Pagination
    paginator = Paginator(matches_qs, 50)  # Show 50 matches per page
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
            "selected_season": season_id,
            "selected_team": team_id,
            "date_from": date_from,
            "date_to": date_to,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def match_detail(request, pk):
    match = get_object_or_404(Match, pk=pk)
    # Get related data
    home_stats = MatchTeamStat.objects.filter(match=match, team=match.home_team).first()
    away_stats = MatchTeamStat.objects.filter(match=match, team=match.away_team).first()
    shots = MatchShot.objects.filter(match=match).order_by('minute')
    player_stats = MatchPlayerStat.objects.filter(match=match)
    
    return render(request, "data_collection/match_detail.html", {
        "match": match,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "shots": shots,
        "player_stats": player_stats,
    })


def shots(request):
    """View for displaying shot statistics with filtering options"""
    # Get query parameters for filtering
    team_id = request.GET.get("team")
    player_id = request.GET.get("player")
    match_id = request.GET.get("match")
    season_id = request.GET.get("season")
    outcome = request.GET.get("outcome")
    min_xg = request.GET.get("min_xg")
    max_distance = request.GET.get("max_distance")
    
    # Base query for shots
    shots_qs = MatchShot.objects.all().order_by('-match__date', 'minute')
    
    # Apply filters
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
            min_xg_value = float(min_xg)
            shots_qs = shots_qs.filter(expected_goals__gte=min_xg_value)
        except ValueError:
            pass
    
    if max_distance:
        try:
            max_distance_value = float(max_distance)
            shots_qs = shots_qs.filter(distance__lte=max_distance_value)
        except ValueError:
            pass
    
    # Get total count and filtered count
    total_count = MatchShot.objects.count()
    filtered_count = shots_qs.count()
    
    # Calculate aggregated statistics
    stats = shots_qs.aggregate(
        avg_xg=Avg('expected_goals'),
        avg_distance=Avg('distance'),
        total_xg=Sum('expected_goals'),
        total_shots=Count('id'),
        goals=Count(Case(When(outcome='Goal', then=1), output_field=IntegerField())),
    )
    
    # Calculate conversion rate (goals / total shots)
    conversion_rate = None
    if stats['goals'] and stats['total_shots']:
        conversion_rate = (stats['goals'] / stats['total_shots']) * 100
    
    # Add conversion rate to stats
    stats['conversion_rate'] = conversion_rate
    
    # Get unique values for filters
    teams = Team.objects.all().order_by('name')
    players = Player.objects.all().order_by('name')
    seasons = Season.objects.all().order_by('-name')
    outcome_choices = sorted(MatchShot.objects.exclude(outcome='').values_list('outcome', flat=True).distinct())
    
    # Pagination
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
    # Get query parameters for filtering
    league_id = request.GET.get("league")
    season_id = request.GET.get("season")
    query = request.GET.get("q", "")
    
    # Base query for teams
    teams_qs = Team.objects.all().order_by('name')
    
    # Apply filters
    if league_id:
        # Filter by teams that played in the selected league
        teams_qs = teams_qs.filter(clubseason__season__league_id=league_id).distinct()
    
    if season_id:
        # Filter by teams that played in the selected season
        teams_qs = teams_qs.filter(clubseason__season_id=season_id).distinct()
    
    if query:
        # Filter by team name search
        teams_qs = teams_qs.filter(name__icontains=query)
    
    # Get total count and filtered count
    total_count = Team.objects.count()
    filtered_count = teams_qs.count()
    
    # Get leagues and seasons for filters
    leagues = League.objects.all().order_by('name')
    seasons = Season.objects.all().order_by('-name')
    
    # Pagination
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
    
    # Get seasons where this team played
    team_seasons = ClubSeason.objects.filter(team=team).order_by('-season__name')
    
    # Get recent matches (home and away)
    recent_matches = Match.objects.filter(
        models.Q(home_team=team) | models.Q(away_team=team)
    ).order_by('-date')[:20]
    
    # Get players who played for this team
    players = Player.objects.filter(
        matchplayerstat__team=team
    ).distinct().order_by('name')
    
    # Get team statistics
    team_stats = {}
    for match in recent_matches:
        stats = MatchTeamStat.objects.filter(match=match, team=team).first()
        if stats:
            # Add match stats to aggregate stats dict
            for field in ['goals', 'shots_on_target', 'total_shots', 'possession', 
                         'passes', 'pass_accuracy', 'corners', 'offsides', 'fouls']:
                value = getattr(stats, field, None)
                if value is not None:
                    if field not in team_stats:
                        team_stats[field] = []
                    team_stats[field].append(value)
    
    # Calculate averages
    avg_stats = {}
    for stat, values in team_stats.items():
        if values:
            avg_stats[stat] = sum(values) / len(values)
    
    return render(
        request, 
        "data_collection/team_detail.html",
        {
            "team": team,
            "team_seasons": team_seasons,
            "recent_matches": recent_matches,
            "players": players,
            "avg_stats": avg_stats,
        }
    )