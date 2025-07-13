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

        def get_recent_stats(team_id, before_date, is_home):
            stats = stats_by_team[(team_id, is_home)]
            recent = [s for s in stats if s.match.date < before_date][-n_matches:]
            if not recent:
                return None
            return {
                "xg": sum([s.expected_goals or 0 for s in recent]) / len(recent),
                "xga": sum([s.expected_goals_against or 0 for s in recent]) / len(recent),
                "pass_acc": sum([s.passing_accuracy or 0 for s in recent]) / len(recent),
                "possession": sum([s.possession or 0 for s in recent]) / len(recent),
                "shots": sum([s.total_shots or 0 for s in recent]) / len(recent),
                "shots_on_target": sum([s.shots_on_target or 0 for s in recent]) / len(recent),
                "saves": sum([s.saves or 0 for s in recent]) / len(recent),
                "fouls": sum([s.fouls or 0 for s in recent]) / len(recent),
                "tackles": sum([s.tackles or 0 for s in recent]) / len(recent),
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
            "total_goals": match.home_score + match.away_score  # ✅ for goal model
        }

        rows.append(row)

    print(f"Dataset complete: {len(rows)} rows.")
    return pd.DataFrame(rows)
