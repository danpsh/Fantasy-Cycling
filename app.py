import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
import time

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="Cycling Fantasy League", layout="wide")

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

# --- 2. THE STAGE-AWARE SCRAPER ---
@st.cache_data(show_spinner=False)
def scrape_data(schedule_df):
    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_races = len(schedule_df)
    
    for i, (_, row) in enumerate(schedule_df.iterrows()):
        race_name = row['race_name']
        status_text.text(f"Processing: {race_name}...")
        
        try:
            url = row['url'].strip()
            race = Race(url)
            
            # Check for stages (Multi-day)
            try:
                stages = race.stages()
            except:
                stages = []

            # If it's a stage race, we need to loop through each stage URL
            if stages:
                for s in stages:
                    try:
                        s_url = s['stage_url']
                        stage_data = Stage(s_url)
                        res = stage_data.results()
                        if res:
                            df = pd.DataFrame(res)
                            df['Race Name'] = race_name
                            df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                            df['tier'] = row['tier']
                            df['Date'] = stage_data.date()
                            all_results.append(df)
                    except:
                        continue
            else:
                # If it's a one-day race, use the main URL + /result
                try:
                    one_day_url = f"{url}/result" if not url.endswith('/result') else url
                    stage_data = Stage(one_day_url)
                    res = stage_data.results()
                    if res:
                        df = pd.DataFrame(res)
                        df['Race Name'] = race_name
                        df['Stage'] = "One Day"
                        df['tier'] = row['tier']
                        df['Date'] = stage_data.date()
                        all_results.append(df)
                except:
                    pass
                    
        except Exception as e:
            st.sidebar.error(f"Error on {race_name}: {e}")
        
        # Update Progress
        progress_bar.progress((i + 1) / total_races)
        time.sleep(0.1) # Small delay to be polite to the server

    status_text.empty()
    progress_bar.empty()
    
    if not all_results:
        return None
        
    final_df = pd.concat(all_results, ignore_index=True)
    final_df['rank'] = pd.to_numeric(final_df['rank'], errors='coerce')
    return final_df[final_df['rank'] <= 10]

# --- 3. UI LAYOUT ---
def main():
    st.title("🏆 2025/2026 Fantasy Leaderboard")
    
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Sync All Races", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        page = st.radio("View", ["Leaderboard", "Race-by-Race", "Roster Check"])

    # Load Files
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("Check your GitHub: riders.csv or schedule.csv is missing!")
        return

    # Run Scraper
    results_raw = scrape_data(schedule_df)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        # Merge Scraped Results with Team Owners
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            if not merged.empty:
                standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
                st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner', text_auto=True))
                st.table(standings.rename(columns={'owner': 'Team', 'pts': 'Total Points'}))
            else:
                st.warning("Data was fetched, but none of the riders in the Top 10 are on your roster list.")

        elif page == "Race-by-Race":
            st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False))
            
        else:
            st.header("Current Teams")
            for owner in riders_df['owner'].unique():
                with st.expander(f"Team {owner}"):
                    st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.warning("No data found. Check your schedule.csv URLs and hit 'Sync'.")

if __name__ == "__main__":
    main()
