from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import Team, Match, Bet
from .forms import MatchForm, BetForm, TeamForm
from decimal import Decimal, ROUND_DOWN


def index(request):
    teams = Team.objects.all()
    matches = Match.objects.all()
    bets = Bet.objects.all()

    pot = 20

    for bet in bets:
        bet.bet_decimal_odds = (Decimal(bet.bet_odds_numerator) / Decimal(bet.bet_odds_denominator)).quantize(Decimal('0.00'), rounding=ROUND_DOWN)
        bet.save()
        if bet.bet_stake is not None:
            bet.bet_return = round(bet.bet_stake * bet.bet_decimal_odds, 2)
            bet.save()
        if bet.bet_win:
            pot += bet.bet_return
        else:
            pot -= bet.bet_stake

    if request.method == 'POST':
        team_form = TeamForm(request.POST)
        if team_form.is_valid():
            team = team_form.save(commit=False)
            team.save()
            messages.success(request, 'Team Added Sucessfully.')
            return redirect('index')

    if request.method == 'POST':
        match_form = MatchForm(request.POST)
        if match_form.is_valid():
            match = match_form.save(commit=False)
            match.save()
            messages.success(request, 'Ship added successfully.')
            return redirect('index')

    if request.method == 'POST':
        bet_form = BetForm(request.POST)
        if bet_form.is_valid():
            bet = bet_form.save(commit=False)
            bet.save()
            messages.success(request, 'Ship added successfully.')
            return redirect('index')

    team_form = TeamForm()
    match_form = MatchForm()
    bet_form = BetForm()

    context = {
        'teams': teams,
        'matches': matches,
        'bets': bets,
        'pot': pot,
        'team_form': team_form,
        'match_form': match_form,
        'bet_form': bet_form,
    }

    return render(request, 'overall_statistics.html', context)
