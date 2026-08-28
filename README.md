# Football Match Prediction Project

A Django application that collects football data from multiple sources, models match
outcomes with a Dixon-Coles Poisson engine, and surfaces **value bets** — markets where
the model's probability beats the bookmaker's implied probability.

---

## Data sources

| Source | What it provides | Reliability |
|---|---|---|
| **football-data.co.uk** | Results, half-time scores, shots/corners/cards, xG (some leagues), **closing odds**, and `fixtures.csv` with upcoming fixtures + live odds | Excellent (plain CSV downloads) |
| **understat.com** | Match xG for the big-5 leagues | Good (one request per league-season) |
| **fbref.com** | Deep per-match stats: shots, player stats, lineups | Currently blocks most automated requests (403 via Cloudflare) — the scraper degrades gracefully and skips |

Leagues configured out of the box: Premier League, Championship, League One, La Liga,
Segunda, Serie A, Serie B, Bundesliga, 2. Bundesliga, Ligue 1, Ligue 2
(see `manage.py setup_sources`). Second divisions matter: country pools are fitted
together, so promoted teams arrive in the top flight with a real rating.

## Setup (local development, Windows/macOS/Linux)

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
```

Create a `.env` in the project root:

```
SECRET_KEY=change-me
DEBUG=True
USE_SQLITE=True        # local dev; omit on the server to use PostgreSQL (DB_* vars)
```

Then:

```
python manage.py migrate
python manage.py setup_sources          # seed leagues + seasons
```

## Collect data & generate predictions

```
# Results + odds for all leagues (last 4 seasons) and upcoming fixtures:
python manage.py import_football_data

# Longer history / specific leagues:
python manage.py import_football_data --start-season 2019-2020 --leagues E0,E1

# Merge understat xG (big-5 leagues):
python manage.py scrape_understat --start-season 2021-2022

# Fit the Dixon-Coles models and store predictions for upcoming fixtures:
python manage.py update_predictions

# Daily/matchday one-shot refresh (results, fixtures+odds, xG, predictions, settlement):
python manage.py refresh_data

# Or the individual pieces:
python manage.py import_football_data --fixtures-only
python manage.py update_predictions
python manage.py settle_bets

# fbref deep-stats pipeline (players, shots) — only works when fbref allows it:
python manage.py scraping_fbref --from-fixtures
```

## How predictions work

`prediction_engine/dixon_coles.py` fits attack/defence ratings per team by maximum
likelihood with exponential time-decay (recent matches weigh more), a home-advantage
term and the Dixon-Coles low-score correction. Leagues are pooled per country
(Premier League + Championship fit together) so promoted teams keep their rating.
When enough xG data exists, a second model fitted on xG is blended in — xG is less
noisy than goals.

Each upcoming fixture gets a full scoreline probability matrix → probabilities for
1X2, over/under 0.5–5.5, BTTS and correct scores (stored on `Prediction`).

`prediction_engine/markets.py` turns those into betting decisions:

- the betting probability blends the model 35/65 with the **de-margined market price**
  (power method, which corrects the favourite–longshot bias); teams with little data
  blend 15/85
- **edge** = betting probability × odds − 1, computed at Bet365/average prices
  (cross-bookmaker max prices contain boost outliers and are shown for info only)
- longshots below a 12% betting probability are never flagged as value
- suggested stake = **quarter-Kelly**

The *Value Bets* page ranks every priceable market by edge; the home page shows
per-fixture cards with probability bars, expected goals, likely scorelines and any
value bets.

**Honesty note**: walk-forward backtesting (4,217 matches / 12 months, weekly refits,
no look-ahead) shows the model does not beat *closing* prices: blended log-loss improves
monotonically toward the pure market, and flat-staking the surviving 3%+ edges at closing
odds lost money. That is the expected result — nothing public beats the closing line.
The value matrix is therefore a shortlist of large model–market disagreements against
*current pre-match* prices (which are softer than closing), for judgement, not a money
printer. Run `manage.py backtest_model` to reproduce.

## Validating the model

```
python manage.py backtest_model --days 365
```

Walk-forward backtest (weekly refits, no look-ahead): reports 1X2 accuracy, log-loss
vs the bookmaker benchmark, and a flat-stakes betting simulation at closing odds with
per-market ROI.

## Legacy ML models

The RandomForest models (`train_models` command) are retained as a secondary opinion.
Bugs fixed: the goals model previously overwrote `result_model.joblib`; training now
uses a chronological split instead of a random one.

# Deployment

When deploying changes to the server (i.e. git pull), restart with:

```
sudo systemctl restart gunicorn_predictions
```

The server keeps using PostgreSQL — don't set `USE_SQLITE` there. After deploying:

```
python manage.py migrate
python manage.py setup_sources
python manage.py import_football_data --start-season 2019-2020
python manage.py scrape_understat --start-season 2021-2022
python manage.py update_predictions
```

Consider a cron job for the daily refresh:

```
python manage.py refresh_data
```
