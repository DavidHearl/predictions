# prediction_engine/dataset_builder.py

import pandas as pd
from collections import defaultdict
from data_collection.models import Match, MatchTeamStat

def build_dataset(n_matches=5):
    rows = []

    matches = Match.objects.filter(
        home_score__isnull=False,
        away_score__isnull=False
    ).order_by("date")

    total_matches = matches.count()
    print(f"Found {total_matches} matches with scores.")

    all_stats = (
        MatchTeamStat.objects
        .select_related("match", "team")
        .order_by("match__date")
    )

    stats_by_team = defaultdict(list)
    for stat in all_stats:
        stats_by_team[(stat.team_id, stat.is_home)].append(stat)

    for idx, match in enumerate(matches):
        if idx % 100 == 0:
            print(f"Processing match {idx + 1} of {total_matches}...")

        def avg_or_none(values):
            """Average of the non-missing values; None when a stat was never recorded.
            (Using `or 0` here poisoned the features - a missing stat became a 0.)"""
            present = [v for v in values if v is not None]
            return sum(present) / len(present) if present else None

        def get_recent_stats(team_id, before_date, is_home):
            stats = stats_by_team[(team_id, is_home)]
            recent = [s for s in stats if s.match.date < before_date][-n_matches:]
            if len(recent) < 3:  # not enough form to be meaningful
                return None
            return {
                "xg": avg_or_none([s.expected_goals for s in recent]),
                "xga": avg_or_none([s.expected_goals_against for s in recent]),
                "pass_acc": avg_or_none([s.passing_accuracy for s in recent]),
                "possession": avg_or_none([s.possession for s in recent]),
                "shots": avg_or_none([s.total_shots for s in recent]),
                "shots_on_target": avg_or_none([s.shots_on_target for s in recent]),
                "saves": avg_or_none([s.saves for s in recent]),
                "fouls": avg_or_none([s.fouls for s in recent]),
                "tackles": avg_or_none([s.tackles for s in recent]),
            }

        home_form = get_recent_stats(match.home_team_id, match.date, is_home=True)
        away_form = get_recent_stats(match.away_team_id, match.date, is_home=False)

        if not home_form or not away_form:
            continue

        def result_label(h, a):
            if h > a:
                return 0
            elif a > h:
                return 2
            else:
                return 1

        row = {
            "home_xg": home_form["xg"],
            "home_xga": home_form["xga"],
            "home_pass_acc": home_form["pass_acc"],
            "home_possession": home_form["possession"],
            "home_shots": home_form["shots"],
            "home_shots_on_target": home_form["shots_on_target"],
            "home_saves": home_form["saves"],
            "home_fouls": home_form["fouls"],
            "home_tackles": home_form["tackles"],

            "away_xg": away_form["xg"],
            "away_xga": away_form["xga"],
            "away_pass_acc": away_form["pass_acc"],
            "away_possession": away_form["possession"],
            "away_shots": away_form["shots"],
            "away_shots_on_target": away_form["shots_on_target"],
            "away_saves": away_form["saves"],
            "away_fouls": away_form["fouls"],
            "away_tackles": away_form["tackles"],

            "result": result_label(match.home_score, match.away_score),
            "total_goals": match.home_score + match.away_score,  # for the goals model
            "match_date": match.date,  # kept so trainers can split by time, dropped before fitting
        }

        rows.append(row)

    print(f"Dataset complete: {len(rows)} rows.")
    return pd.DataFrame(rows)
