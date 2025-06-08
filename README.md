## Define the model

1. 




1. Add a season, we will do this by going into the shell
- python3 manage.py shell
- from data_collection.models import Season
- season = Season.objects.create(name="2023-2024")

2. Add a league, we will do this using the same methodology as before
- python3 manage.py shell
- from data_collection.models import League
- league = League.objects.create(
    name="Premier League",
    country="England"
)
- League.objects.all()

3. Add the teams in the league now that we have the season and the league
- Install packages first
- pip install requests beautifulsoup4
- pip install lxml (Faster parsing for BS4)
- pip freeze > requirements.txt
- Generate new fi
- Write the get_teams() function

