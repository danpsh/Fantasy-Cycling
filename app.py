import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
import requests

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    words = name.lower().replace('-', ' ').split()
    return " ".join(sorted(words))

# --- 2. THE "FORCE" SCRAPER ---
@st.cache_data(show_spinner="Connecting to PCS...")
def scrape_data(schedule_df):
    all_results = []
    # This headers dictionary tricks the website into thinking you are a real person
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for _, row in schedule_df.iterrows():
        try:
            # Add /result to the URL if it's missing to ensure we hit the data page
            clean_url = row['url'].strip()
            if not clean_url.endswith('/result') and not clean_url.endswith('/2025'):
                 clean_url += '/result'
            
            # Use the library but with a safety check
            race = Race(clean_url)
            
            # Try to get stages. If it fails, assume it's a one-day race
            try:
                stages = race.stages()
            except:
                stages = []
            
            target_urls = [s['stage_url'] for s in stages] if stages else [clean_url]
            
            for s_url in target_urls:
                try:
                    # Initialize Stage with our fake 'real person' identity
                    stage_data = Stage(s_url)
                    results = stage_data.results()
                    
                    if results:
                        df = pd.DataFrame(results)
                        df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
                        df = df[df['rank'] <= 10].copy()
                        df['Race Name'] = row['race_name']
                        df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                        df['tier'] = row['tier']
                        df['Date'] = stage_data.date()
                        all_results.append(df)
                except:
                    continue
        except Exception as e:
            st.sidebar.error(f"Failed {row['race_name']}: {str(e)[:50]}")
            continue
            
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. UI LOGIC ---
def main():
    with st.sidebar:
        st.header("App Admin")
        if st.button("🔄 Force Sync Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        page = st.radio("Navigation", ["Leaderboard", "Raw Results", "Roster Check"])

    # Load Files
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("Missing riders.csv or schedule.csv on GitHub!")
        return

    # Scrape
    results_raw = scrape_data(schedule_df)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title("🏆 Season Standings")
            if not merged.empty:
                standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
                st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner'))
                st.table(standings)
            else:
                st.warning("Found results on PCS, but none of your riders matched. Check names!")

        elif page == "Raw Results":
            st.title("🔍 All Top 10s Found")
            st.dataframe(results_raw[['Date', 'Race Name', 'Stage', 'rider_name', 'rank']])
            
        else:
            st.title("📋 Your Rosters")
            st.dataframe(riders_df[['owner', 'rider_name']])
    else:
        st.warning("No data found. Ensure schedule.csv URLs are like: race/tour-de-france/2025")

if __name__ == "__main__":
    main()
