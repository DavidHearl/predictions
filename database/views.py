from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from .models import *
from decimal import Decimal, ROUND_DOWN


def index(request):
#     teams = Team.objects.all()
#     matches = Match.objects.all()
#     bets = Bet.objects.all()

#     pot = 20

#     for bet in bets:
#         bet.bet_decimal_odds = (Decimal(bet.bet_odds_numerator) / Decimal(bet.bet_odds_denominator)).quantize(Decimal('0.00'), rounding=ROUND_DOWN)
#         bet.save()
#         if bet.bet_stake is not None:
#             bet.bet_return = round(bet.bet_stake * bet.bet_decimal_odds, 2)
#             bet.save()
#         if bet.bet_win:
#             pot += bet.bet_return
#         else:
#             pot -= bet.bet_stake

#     context = {
#         'teams': teams,
#         'matches': matches,
#         'bets': bets,
#         'pot': pot,
#     }

    return render(request, 'overall_statistics.html')
