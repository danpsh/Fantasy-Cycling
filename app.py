import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
from datetime import datetime

# --- 1. SETUP & SCORING ---
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

# --- 2. THE SCRAPER ENGINE ---
@st.cache_data(show_spinner=False)
def scrape_data(schedule_df, season_year):
    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (_, row) in enumerate(schedule_df.iterrows()):
        race_name = row['race_name']
        status_text.text(f"Checking {race_name}...")
        
        try:
            # Build URL (e.g., race/tour-down-under/2026)
            base_url = row['url'].strip().strip('/')
            url = base_url if str(season_year) in base_url else f"{base_url}/{season_year}"
            
            race = Race(url)
            
            # Find stages (e.g., stage-1, stage-2)
            try:
                stages = race.stages()
                target_urls = [s['stage_url'] for s in stages] if stages else [f"{url}/result"]
            except:
                target_urls = [f"{url}/result"]
            
            for s_url in target_urls:
                try:
                    stage_data = Stage(s_url)
                    res = stage_data.results()
                    if res:
                        df = pd.DataFrame(res)
                        df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
                        df = df[df['rank'] <= 10].copy()
                        df['Race Name'] = race_name
                        df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                        df['tier'] = row['tier']
                        df['Date'] = stage_data.date()
                        all_results.append(df)
                except:
                    continue
        except:
            continue
        
        progress_bar.progress((i + 1) / len(schedule_df))

    status_text.empty()
    progress_bar.empty()
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. MAIN APP ---
def main():
    st.title("🚴‍♂️ 2026 Fantasy Cycling League")

    with st.sidebar:
        st.header("Settings")
        year = st.selectbox("Season", [2026, 2025], index=0)
        if st.button("🔄 Sync Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        page = st.radio("Go to:", ["Leaderboard", "Race Results", "Rosters"])

    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except:
        st.error("Missing riders.csv or schedule.csv on GitHub.")
        return

    results_raw = scrape_data(schedule_df, year)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            if not merged.empty:
                standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
                st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner', text_auto=True))
                st.table(standings.rename(columns={'owner': 'Team Owner', 'pts': 'Total Pts'}))
            else:
                st.info(f"No results for your riders found in {year} yet.")

        elif page == "Race Results":
            st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False), hide_index=True)

        else:
            for owner in riders_df['owner'].unique():
                with st.expander(f"Team {owner}"):
                    st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.warning("No data found. Ensure schedule.csv URLs look like 'race/tour-down-under'.")

if __name__ == "__main__":
    main()
