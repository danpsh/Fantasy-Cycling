import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
import time

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

# --- 2. DATA SCRAPER ENGINE ---
@st.cache_data(show_spinner="Syncing results from ProCyclingStats...")
def scrape_data(schedule_df):
    all_results = []
    
    for _, row in schedule_df.iterrows():
        try:
            # Step 1: Initialize Race
            url = row['url'].strip()
            race = Race(url)
            
            # Step 2: Get stages (empty list if it's a one-day race)
            try:
                stages = race.stages()
            except:
                stages = []
            
            # Step 3: Determine which URLs to hit
            # If no stages, add '/result' to the race URL for one-day races
            if not stages:
                target_urls = [f"{url}/result" if not url.endswith('/result') else url]
            else:
                target_urls = [s['stage_url'] for s in stages]
            
            for s_url in target_urls:
                try:
                    # Small delay to prevent bot blocking
                    time.sleep(0.5)
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
                except Exception as stage_e:
                    continue
                    
        except Exception as race_e:
            st.sidebar.warning(f"Skipping {row['race_name']}: URL error.")
            continue
            
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. UI LOGIC ---
def main():
    with st.sidebar:
        st.title("Admin")
        if st.button("🔄 Sync 2025 Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        page = st.radio("Navigation", ["Leaderboard", "Detailed Points", "Rosters"])

    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("Missing riders.csv or schedule.csv on GitHub!")
        return

    results_raw = scrape_data(schedule_df)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title("🏆 2025 Standings")
            standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner'))
            st.table(standings)

        elif page == "Detailed Points":
            st.title("📊 Stage-by-Stage Results")
            st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False))
            
        else:
            st.title("📋 Rosters")
            for owner in riders_df['owner'].unique():
                with st.expander(f"Team {owner}"):
                    st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.warning("No data found. Ensure URLs in schedule.csv look like 'race/tour-de-france/2025' and click Sync.")

if __name__ == "__main__":
    main()
