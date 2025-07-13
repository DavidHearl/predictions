# Football Match Prediction Project

A Django-based application that uses historical match data to predict football outcomes using statistical scraping and modeling.

---

## Setup & Collect Data

- Navigate to the directory

``` 
cd 'Documents/08 - Programming/GitHub/predictions' 
cd 'C:\Users\David\iCloudDrive\Documents\08 - Programming\GitHub'
```

- Activate the virtual environment

``` 
source virtual_environment/bin/activate 
```

- Download all of the dependencies
- Save your dependencies to a requirements file

```
pip freeze > requirements.txt
```

```
pip install -r requirements.txt
```

- To collect the data run

``` python3 manage.py scraping_fbref ```

## Define the model
**Model here**

## Project Stages


""" 
Create a simple utility function to populate the season dates at the start of the project.
When the database has been populated this will become redundant and not reqiured.
"""
- create_seasons(): # Utilities function (datacollect/utils/seasons.py)
    - Create the seasons within a specified range and populate the *Season* model with:
        - **name**: Season name, ie 2021-2022

- build_season_urls():
    - Use the season and the league to generate a list of urls which will be used to scrape the following...



- populate_team_data():
    - Get the unique code for all the teams
    - Get the team name
    - Get the season which the team is participating in e.g 2021-2022
    - Populate the *Team* model with:
        - **name**: The name of the team.
        - **unique_code**: A unique identifier for the team.
    - Populate the *ClubSeason* model with:
        - **team**: Foreign Key for the name
        - **season**: Season which they participated in
        - **league**: League which they were in this season

- build_team_urls():
    - Create a list of urls for each team in each season

- extract_player_urls():
    - Get the player name in a team
    - Get the link for that player
    - Populate the *Player* Model with:
        - **name**
        - **player_url**

- populate_player_details():
    - Iterate through the player_urls and get the unique_code
    - Get the position
    - Get the players DOB
    - Get the players Nationality
    - Get the players Height
    - Get the players Wegiht
    - Get the players dominant foot
    - Populate the *Player* Model with:
        - **position**
        - **birth_date**
        - **nationality**
        - **height**
        - **wegiht**
        - **footed**

- build_fixture_urls()
    - Create a list of urls for each league and season

- extract_team_name_from_href()
    - Extract the team name from the href found in the match table

- get_fixture_tables()
    
# Deployment
When deploying some changes to the server (ie git pull)
Make sure you restart the server with this command

```
sudo systemctl restart gunicorn_predictions
```



