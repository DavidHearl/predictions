from django import forms
from django.contrib.auth.models import User
from .models import Match, Team, Bet


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = '__all__'


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = '__all__'


class BetForm(forms.ModelForm):
    class Meta:
        model = Bet
        fields = '__all__'