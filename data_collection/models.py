from django.db import models


class Season(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=50)
    league_id = models.PositiveIntegerField()
    number_of_teams = models.PositiveIntegerField(default=20)

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    unique_code = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name


class ClubSeason(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    number_of_players = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.team.name} - {self.season.name} - {self.league.name}"


class Player(models.Model):
    name = models.CharField(max_length=100, null=True)
    unique_code = models.CharField(max_length=100, null=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    birth_date = models.DateField(null=True)
    nationality = models.CharField(max_length=50, null=True)
    height = models.FloatField(blank=True, null=True, help_text="Height in cm")
    weight = models.FloatField(blank=True, null=True, help_text="Weight in kg")
    footed = models.CharField(max_length=10, choices=[('left', 'Left'), ('right', 'Right'), ('both', 'Both')], null=True)
    player_url = models.URLField(max_length=300, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    date = models.DateTimeField()
    home_team = models.ForeignKey(Team, related_name='home_matches', on_delete=models.CASCADE)
    away_team = models.ForeignKey(Team, related_name='away_matches', on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    attendance = models.IntegerField(null=True, blank=True)
    venue = models.CharField(max_length=100, null=True, blank=True)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    referee = models.CharField(max_length=100, null=True, blank=True)
    match_url = models.URLField(max_length=300, unique=True, null=True, blank=True)

    assistant_referee_1 = models.CharField(max_length=100, null=True, blank=True)
    assistant_referee_2 = models.CharField(max_length=100, null=True, blank=True)
    fourth_official = models.CharField(max_length=100, null=True, blank=True)
    var_official = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.season} : {self.home_team.name} vs {self.away_team.name}"


class MatchShot(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey('Player', on_delete=models.SET_NULL, null=True, blank=True)
    shots_not_available = models.BooleanField(default=True)

    minute = models.PositiveSmallIntegerField(null=True)
    expected_goals = models.FloatField(null=True)
    post_shot_expected_goals = models.FloatField(null=True, default=0.0)

    outcome = models.CharField(max_length=50, null=True, blank=True)        # e.g. "Goal", "Blocked", "Saved"
    distance = models.FloatField(null=True, help_text="Distance in meters")
    body_part = models.CharField(max_length=50, null=True, blank=True)      # e.g. "Left Foot", "Right Foot", "Head"
    is_penalty = models.BooleanField(default=False)
    assisted_by = models.ForeignKey('Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='assists')

    def __str__(self):
        return f"{self.match}"


class MatchTeamStat(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    is_home = models.BooleanField()

    expected_goals = models.FloatField(null=True)
    expected_goals_against = models.FloatField(null=True)
    possession = models.FloatField(null=True)
    passing_accuracy = models.FloatField(null=True)
    shots_on_target = models.PositiveSmallIntegerField(null=True)
    total_shots = models.PositiveSmallIntegerField(null=True)
    saves = models.PositiveSmallIntegerField(null=True)

    fouls = models.PositiveSmallIntegerField(null=True)
    corners = models.PositiveSmallIntegerField(null=True)
    crosses = models.PositiveSmallIntegerField(null=True)
    touches = models.PositiveIntegerField(null=True)
    tackles = models.PositiveSmallIntegerField(null=True)

    interceptions = models.PositiveSmallIntegerField(null=True)
    aerials_won = models.PositiveSmallIntegerField(null=True)
    clearances = models.PositiveSmallIntegerField(null=True)
    offsides = models.PositiveSmallIntegerField(null=True)
    goal_kicks = models.PositiveSmallIntegerField(null=True)
    throwins = models.PositiveSmallIntegerField(null=True)
    long_balls = models.PositiveSmallIntegerField(null=True)

    def __str__(self):
        return f"{self.match} : {'Home' if self.is_home else 'Away'}"


class MatchPlayerStat(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey('Player', on_delete=models.CASCADE)

    # General
    minutes_played = models.PositiveSmallIntegerField(null=True)
    goals = models.PositiveSmallIntegerField(null=True)
    expected_goals = models.FloatField(null=True)
    assists = models.PositiveSmallIntegerField(null=True)
    expected_assists = models.FloatField(null=True)
    non_penalty_expected_goals = models.FloatField(null=True)
    penalty_kicks_made = models.PositiveSmallIntegerField(null=True)
    penalty_kicks_attempted = models.PositiveSmallIntegerField(null=True)
    shot_creation_actions = models.PositiveSmallIntegerField(null=True)
    goal_creation_actions = models.PositiveSmallIntegerField(null=True)

    # Shooting
    shots = models.PositiveSmallIntegerField(null=True)
    shots_on_target = models.PositiveSmallIntegerField(null=True)

    # Passing
    passes_completed = models.PositiveSmallIntegerField(null=True)
    passes_attempted = models.PositiveSmallIntegerField(null=True)
    pass_completion_percentage = models.FloatField(null=True)
    total_passing_distance = models.PositiveIntegerField(null=True)
    progressive_passes = models.PositiveSmallIntegerField(null=True)
    total_progressive_distance = models.PositiveIntegerField(null=True)
    short_passes_completed = models.PositiveSmallIntegerField(null=True)
    short_passes_attempted = models.PositiveSmallIntegerField(null=True)
    short_passes_percentage = models.FloatField(null=True)
    medium_passes_completed = models.PositiveSmallIntegerField(null=True)
    medium_passes_attempted = models.PositiveSmallIntegerField(null=True)
    medium_passes_percentage = models.FloatField(null=True)
    long_passes_completed = models.PositiveSmallIntegerField(null=True)
    long_passes_attempted = models.PositiveSmallIntegerField(null=True)
    long_passes_percentage = models.FloatField(null=True)
    key_passes = models.PositiveSmallIntegerField(null=True)
    passes_into_final_third = models.PositiveSmallIntegerField(null=True)
    passes_into_penalty_area = models.PositiveSmallIntegerField(null=True)
    crosses_into_penalty_area = models.PositiveSmallIntegerField(null=True)

    # Pass Types
    live_passes = models.PositiveSmallIntegerField(null=True)
    dead_passes = models.PositiveSmallIntegerField(null=True)
    free_kicks = models.PositiveSmallIntegerField(null=True)
    through_balls = models.PositiveSmallIntegerField(null=True)
    switches = models.PositiveSmallIntegerField(null=True)
    crosses = models.PositiveSmallIntegerField(null=True)
    throwins = models.PositiveSmallIntegerField(null=True)
    corners = models.PositiveSmallIntegerField(null=True)
    inswinging_corner_kicks = models.PositiveSmallIntegerField(null=True)
    outswinging_corner_kicks = models.PositiveSmallIntegerField(null=True)
    straight_corner_kicks = models.PositiveSmallIntegerField(null=True)

    # Defensive Actions
    tackles = models.PositiveSmallIntegerField(null=True)
    tackles_won = models.PositiveSmallIntegerField(null=True)
    tackles_in_defensive_third = models.PositiveSmallIntegerField(null=True)
    tackles_in_middle_third = models.PositiveSmallIntegerField(null=True)
    tackles_in_attacking_third = models.PositiveSmallIntegerField(null=True)
    dribblers_tackled = models.PositiveSmallIntegerField(null=True)
    dribbles_challenged = models.PositiveSmallIntegerField(null=True)
    dribble_tackle_percent = models.FloatField(null=True)
    blocks = models.PositiveSmallIntegerField(null=True)
    shots_blocked = models.PositiveSmallIntegerField(null=True)
    passes_blocked = models.PositiveSmallIntegerField(null=True)
    interceptions = models.PositiveSmallIntegerField(null=True)
    tackles_and_interceptions = models.PositiveSmallIntegerField(null=True)
    clearances = models.PositiveSmallIntegerField(null=True)
    errors = models.PositiveSmallIntegerField(null=True)

    # Possession
    touches = models.PositiveIntegerField(null=True)
    touches_in_defensive_penalty = models.PositiveSmallIntegerField(null=True)
    touches_in_defensive_third = models.PositiveSmallIntegerField(null=True)
    touches_in_middle_third = models.PositiveSmallIntegerField(null=True)
    touches_in_attacking_third = models.PositiveSmallIntegerField(null=True)
    touches_in_attacking_penalty = models.PositiveSmallIntegerField(null=True)
    attempted_take_ons = models.PositiveSmallIntegerField(null=True)
    successful_take_ons = models.PositiveSmallIntegerField(null=True)
    successful_take_on_percentage = models.FloatField(null=True)
    take_ons_tackled = models.PositiveSmallIntegerField(null=True)
    take_ons_tackled_percentage = models.FloatField(null=True)
    carries = models.PositiveSmallIntegerField(null=True)
    progressive_carries = models.PositiveSmallIntegerField(null=True)
    total_distance_carried = models.PositiveIntegerField(null=True)
    total_progressive_distance_carried = models.PositiveIntegerField(null=True)
    carries_into_attacking_third = models.PositiveSmallIntegerField(null=True)
    carries_into_penalty_area = models.PositiveSmallIntegerField(null=True)
    miscontrols = models.PositiveSmallIntegerField(null=True)
    disposessions = models.PositiveSmallIntegerField(null=True)
    passes_recieved = models.PositiveSmallIntegerField(null=True)
    progressive_passes_recieved = models.PositiveSmallIntegerField(null=True)

    # Miscellaneous
    yellow_cards = models.PositiveSmallIntegerField(null=True)
    red_cards = models.PositiveSmallIntegerField(null=True)
    second_yellow_cards = models.PositiveSmallIntegerField(null=True)
    fouls = models.PositiveSmallIntegerField(null=True)
    fouls_drawn = models.PositiveSmallIntegerField(null=True)
    offsides = models.PositiveSmallIntegerField(null=True)
    penalty_kicks_won = models.PositiveSmallIntegerField(null=True)
    penalty_kicks_conceeded = models.PositiveSmallIntegerField(null=True)
    own_goals = models.PositiveSmallIntegerField(null=True)
    balls_recovered = models.PositiveSmallIntegerField(null=True)
    aerials_won = models.PositiveSmallIntegerField(null=True)
    aerials_lost = models.PositiveSmallIntegerField(null=True)
    aerial_win_percentage = models.FloatField(null=True)

    # Goalkeeping
    gk_shots_on_targets = models.PositiveSmallIntegerField(null=True)
    gk_goals_against = models.PositiveSmallIntegerField(null=True)
    gk_saves = models.PositiveSmallIntegerField(null=True)
    gk_save_percentage = models.FloatField(null=True)
    gk_post_shot_expected_goals = models.FloatField(null=True)
    gk_launches_completed = models.PositiveSmallIntegerField(null=True)
    gk_launches_attempted = models.PositiveSmallIntegerField(null=True)
    gk_launches_completion_percentage = models.FloatField(null=True)
    gk_passes_attempted = models.PositiveSmallIntegerField(null=True)
    gk_thows_attempted = models.PositiveSmallIntegerField(null=True)
    gk_launch_percent = models.FloatField(null=True)
    gk_average_pass_length = models.FloatField(null=True)
    gk_goal_kicks_attempted = models.PositiveSmallIntegerField(null=True)
    gk_goal_kick_launch_percent = models.FloatField(null=True)
    gk_goak_kick_average_length = models.FloatField(null=True)
    gk_crosses_opposed = models.PositiveSmallIntegerField(null=True)
    gk_crosses_stopped = models.PositiveSmallIntegerField(null=True)
    gk_cross_stop_percentage = models.FloatField(null=True)
    gk_actions_outside_penalty_area = models.PositiveSmallIntegerField(null=True)
    gk_average_distance_from_goal = models.FloatField(null=True)

    def __str__(self):
        return f"{self.match} : {self.player.name} ({self.team.name})"


class Prediction(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE)
    predicted_result = models.CharField(max_length=10)  # 'home', 'draw', 'away'
    predicted_home_score = models.FloatField()
    predicted_away_score = models.FloatField()
    model_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

