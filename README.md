# Football Match Prediction Project

A Django-based application that uses historical match data to predict football outcomes using statistical scraping and modeling.

---

## Define the model
**Model here**

## Project Steps
1. Add some seasons to the database as a starting point
```
python3 manage.py shell

from data_collection.models import Season
season = Season.objects.create(name="2023-2024")
```
2. Add a league to the database
```
python3 manage.py shell

from data_collection.models import League
league = League.objects.create(
    name="Premier League",
    country="England"
)
```
3. Import packages
```
pip install requests beautifulsoup4
pip install lxml
pip freeze > requirements.txt
```

4. Create a function to get build the urls which will be used to scrape a list of the teams
- build_fbref_urls()

5. Create a function to get all the href links from a page
- We want to filter out the urls that only occur once
- We want to filter out the urls that do not have the season inside



