from data_collection.models import Season


def create_seasons(start="2020-2021", end="1995-1996"):
    """
    Creates Season entries in the format 'YYYY-YYYY' from the given start to end range.
    
    Args:
        start (str): The most recent season, e.g., "2020-2021"
        end (str): The oldest season, e.g., "1995-1996"

    Notes:
        This function assumes both years are in 'YYYY-YYYY' format.
    """

    # Extract the starting and ending year (as integers) from input strings
    start_year = int(start.split("-")[0])
    end_year = int(end.split("-")[0])

    created = 0  # Counter for how many new seasons are created

    # Loop backwards from start_year to end_year (inclusive)
    for year in range(start_year, end_year - 1, -1):
        # Format season name as 'YYYY-YYYY'
        season_name = f"{year}-{year + 1}"

        # Create the season if it doesn't already exist
        obj, created_flag = Season.objects.get_or_create(name=season_name)

        if created_flag:
            created += 1

    print(f"Created {created} new seasons.")
