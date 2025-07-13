from django import forms
from .models import *
from datetime import date


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = '__all__'


class MatchPredictionDateForm(forms.Form):
    match_date = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        dates = (
            Match.objects
            .order_by("-date__date")
            .values_list("date__date", flat=True)
            .distinct()
        )

        formatted = [(str(d), d.strftime("%A, %d %B %Y")) for d in dates]

        self.fields["match_date"].choices = formatted