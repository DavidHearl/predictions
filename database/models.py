from django.db import models


class Season(models.Model):
    season = models.CharField(max_length=100, blank=True, null=True) # eg 2020-2021

    def __str__(self):
        return self.season


class League(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True) # eg Premier League

    def __str__(self):
        return self.name


class Competition(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    league = models.ForeignKey(League, on_delete=models.CASCADE)

    teams = models.ManyToManyField("Team")

    def __str__(self):
        return f"{self.league} - {self.season}"


class Team(models.Model):
    team_name = models.CharField(max_length=100)

    league = models.ForeignKey(League, on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)

    def __str__(self):
        return self.team_name


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    
