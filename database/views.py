from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from .models import Team, Match


def index(request):
    teams = Team.objects.all()
    matches = Match.objects.all()

    context = {
        'teams': teams,
        'matches': matches
    }

    return render(request, 'overall_statistics.html', context)
