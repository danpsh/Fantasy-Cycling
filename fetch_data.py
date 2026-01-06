import pandas as pd

# This is a sample function - you'd add your 57 URLs here
def fetch_2025_results(race_url, race_name, tier):
    try:
        # 1. Read the table from the URL
        tables = pd.read_html(race_url)
        results_table = tables[0] # Usually the first table on the page
        
        # 2. Grab Top 10
        top_10 = results_table.head(10).copy()
        
        # 3. Clean up the names (PCS often puts extra info in the name column)
        top_10['Rider'] = top_10['Rider'].str.replace(r'[^a-zA-Z\s]', '', regex=True)
        
        # 4. Map your scoring
        scoring = {
            "Tier 1": [30, 27, 24, 21, 18, 15, 12, 9, 6, 3],
            "Tier 2": [20, 18, 16, 14, 12, 10, 8, 6, 4, 2],
            "Tier 3": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        }
        
        top_10['Points'] = scoring[tier]
        top_10['Race'] = race_name
        
        return top_10[['Race', 'Rider', 'Points']]
    except Exception as e:
        print(f"Skipping {race_name}: {e}")
        return None

# Example: Pulling the 2025 Tour de France Stage 1
# results = fetch_2025_results("https://www.procyclingstats.com/race/tour-de-france/2025/stage-1", "Tour de France", "Tier 1")