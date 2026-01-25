import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
from datetime import datetime
import time

# --- 1. CONFIGURATION & SCORING ---
st.set_page_config(page_title="2026 Fantasy Cycling", layout="wide")

# Scoring logic for Top 10 finishes
SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    """Standardizes names for matching (e.g. 'Pogačar' -> 'pogacar')"""
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    words = name.lower().replace('-', ' ').split()
    return " ".join(sorted(words))

# --- 2. THE DYNAMIC SCRAPER ---
@st.cache_data(show_spinner=False)
def scrape_data(schedule_df, season_year):
    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (_, row) in enumerate(schedule_df.iterrows()):
        race_name = row['race_name']
        status_text.text(f"Searching for {race_name} ({season_year})...")
        
        try:
            # Clean URL and add year if missing
            base_url = row['url'].strip()
            # If the user didn't put a year in the CSV, we add the selected season
            if not any(char.isdigit() for char in base_url.split('/')[-1]):
                url = f"{base_url}/{season_year}"
            else:
                url = base_url
            
            race = Race(url)
            
            # Check for stages (Multi-day)
            try:
                stages = race.stages()
            except:
                stages = []

            # Determine target URLs (all stages or the one-day result)
            target_urls = [s['stage_url'] for s in stages] if stages else [f"{url}/result"]
            
            for s_url in target_urls:
                try:
                    stage_data = Stage(s_url)
                    res = stage_data.results()
                    if res:
                        df = pd.DataFrame(res)
                        df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
                        df = df[df['rank'] <= 10].copy() # Keep only top 10
                        
                        df['Race Name'] = race_name
                        df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                        df['tier'] = row['tier']
                        df['Date'] = stage_data.date()
                        all_results.append(df)
                except:
                    continue
                    
        except Exception as e:
            st.sidebar.warning(f"Skipping {race_name}: Not yet available.")
        
        progress_bar.progress((i + 1) / len(schedule_df))

    status_text.empty()
    progress_bar.empty()
    
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. MAIN INTERFACE ---
def main():
    st.title("🚴‍♂️ 2026 Fantasy Pro Cycling")
    
    # Sidebar Setup
    with st.sidebar:
        st.header("App Controls")
        # Allow user to toggle seasons
        selected_year = st.selectbox("Select Season", [2026, 2025], index=0)
        
        if st.button("🔄 Sync Live Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        page = st.radio("Navigation", ["🏆 Leaderboard", "📊 Detailed Points", "📋 Team Rosters"])
        st.divider()
        st.info("The app checks for results based on the year selected above.")

    # Load local CSVs from GitHub
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("Error: Ensure riders.csv and schedule.csv are in your GitHub folder.")
        return

    # Run Scraper
    results_raw = scrape_data(schedule_df, selected_year)

    if results_raw is not None:
        # Prepare Data for Matching
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        # Merge Scraped Results with Owners
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        # --- PAGE: LEADERBOARD ---
        if page == "🏆 Leaderboard":
            if not merged.empty:
                standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
                
                # Visual Chart
                fig = px.bar(standings, x='owner', y='pts', color='owner', 
                             labels={'owner': 'Team Owner', 'pts': 'Total Points'},
                             text_auto=True)
                st.plotly_chart(fig, use_container_width=True)
                
                # Table
                st.subheader("Current Standings")
                st.table(standings.rename(columns={'owner': 'Team', 'pts': 'Points'}))
            else:
                st.warning(f"No results found for your riders in {selected_year} yet.")

        # --- PAGE: DETAILED RESULTS ---
        elif page == "📊 Detailed Points":
            st.subheader(f"Points Breakdown ({selected_year})")
            if not merged.empty:
                st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False), 
                             hide_index=True, use_container_width=True)
            else:
                st.write("No race data available.")

        # --- PAGE: ROSTERS ---
        else:
            st.subheader("League Rosters")
            for owner in riders_df['owner'].unique():
                with st.expander(f"Team {owner}"):
                    team_list = riders_df[riders_df['owner'] == owner]['rider_name'].tolist()
                    st.write(" • " + "\n • ".join(team_list))
    else:
        st.warning(f"No data found for the {selected_year} season. Try syncing or check your schedule URLs.")

if __name__ == "__main__":
    main()
