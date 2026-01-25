import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import unicodedata
import time

# --- 1. SETTINGS ---
st.set_page_config(page_title="2026 Fantasy Cycling", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return " ".join(sorted(name.lower().replace('-', ' ').split()))

# --- 2. CUSTOM SCRAPER (The Bot-Bypasser) ---
def get_pcs_data(path):
    # This headers dictionary makes the app look like a real Chrome browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    url = f"https://www.procyclingstats.com/{path}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        results = []
        
        # Look for the results table (standard PCS class)
        table = soup.find('table', class_='results')
        if not table:
            return None
            
        rows = table.find('tbody').find_all('tr')
        for row in rows[:10]: # Only top 10
            cols = row.find_all('td')
            if len(cols) > 3:
                rank = cols[0].text.strip()
                rider = cols[3].find('a').text.strip() if cols[3].find('a') else cols[3].text.strip()
                results.append({'rank': rank, 'rider_name': rider})
        
        return results
    except Exception as e:
        st.sidebar.error(f"Scraper Error: {e}")
        return None

# --- 3. LOGIC ---
@st.cache_data(ttl=3600)
def load_all_results(schedule_df):
    all_data = []
    for _, row in schedule_df.iterrows():
        # Adjust URL for stages or results
        # If it's a stage race, you'll need the specific stage path
        path = f"{row['url']}/2026/result"
        results = get_pcs_data(path)
        
        if results:
            df = pd.DataFrame(results)
            df['Race'] = row['race_name']
            df['tier'] = row['tier']
            all_data.append(df)
        time.sleep(1) # Be polite to avoid IP ban
        
    return pd.concat(all_data) if all_data else None

def main():
    st.sidebar.header("Admin")
    if st.sidebar.button("🔄 Sync Live Data"):
        st.cache_data.clear()
    
    # Load your CSV files
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("riders.csv or schedule.csv not found!")
        return

    results_raw = load_all_results(schedule_df)

    if results_raw is not None:
        # Match riders and calculate points
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        st.title("🏆 2026 Season Leaderboard")
        standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
        st.table(standings)
        
        with st.expander("Show Raw Scraped Results"):
            st.dataframe(results_raw)
    else:
        st.warning("Still no data. Ensure your schedule.csv 'url' is like 'race/tour-down-under'")

if __name__ == "__main__":
    main()
