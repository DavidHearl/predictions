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
```
pip install -r requirements.txt
```

- To collect the data run

``` python3 manage.py scraping_fbref ```

## Define the model
**Model here**

## Project Stages

- create_seasons(): # Utilities function (datacollect/utils/seasons.py)
    - Create the seasons within a specified range and populate the *Season* model with:
        - **name**: Season name, ie 2021-2022

- build_fbref_urls():
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



