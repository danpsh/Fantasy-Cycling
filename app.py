import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="Cycling Fantasy League", layout="wide")

# Scoring points for Top 10 finishes
SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# Helper function to match names even if accents or order vary
def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    words = name.lower().replace('-', ' ').split()
    return " ".join(sorted(words))

# --- 2. DATA SCRAPER (THE ENGINE) ---
@st.cache_data(show_spinner="Scraping results from ProCyclingStats...")
def scrape_data(schedule_df):
    all_results = []
    for _, row in schedule_df.iterrows():
        try:
            # Connect to the race (e.g., race/tour-de-france/2025)
            race = Race(row['url'])
            stages = race.stages()
            
            # If multi-day, get all stages; if one-day, just get the main URL
            urls = [s['stage_url'] for s in stages] if stages else [row['url']]
            
            for s_url in urls:
                stage_data = Stage(s_url)
                results = stage_data.results()
                if results:
                    df = pd.DataFrame(results)
                    df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
                    df = df[df['rank'] <= 10].copy() # Only keep Top 10
                    
                    df['Race Name'] = row['race_name']
                    df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                    df['tier'] = row['tier']
                    df['Date'] = stage_data.date()
                    all_results.append(df)
        except Exception as e:
            st.sidebar.error(f"Error on {row['race_name']}: {e}")
            continue
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. THE APP INTERFACE ---
def main():
    # Sidebar for Controls
    with st.sidebar:
        st.header("Admin Controls")
        if st.button("🔄 Sync 2025 Results", use_container_width=True):
            st.cache_data.clear() # Clears the saved data so it fetches fresh
            st.rerun()
        st.info("Syncing 2025 data will pull results for all races in your schedule.")
        st.divider()
        page = st.radio("Navigation", ["Leaderboard", "Detailed Points", "Rosters"])

    # Load your CSV files from GitHub
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except Exception as e:
        st.error(f"Could not find CSV files! Make sure riders.csv and schedule.csv are in your GitHub. Error: {e}")
        return

    # Run Scraper
    results_raw = scrape_data(schedule_df)

    if results_raw is not None:
        # Match riders to owners
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        final_df = results_raw.merge(riders_df, on='match_name', how='inner')
        final_df['pts'] = final_df.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title("🏆 2025 Fantasy Standings")
            standings = final_df.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            
            # Show a bar chart
            fig = px.bar(standings, x='owner', y='pts', color='owner', title="Points by Team Owner")
            st.plotly_chart(fig, use_container_width=True)
            
            st.table(standings.rename(columns={'owner': 'Owner', 'pts': 'Total Points'}))

        elif page == "Detailed Points":
            st.title("📊 Points Breakdown")
            st.dataframe(final_df[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False), hide_index=True)

        else:
            st.title("📋 Team Rosters")
            for owner in riders_df['owner'].unique():
                with st.expander(f"Team {owner}"):
                    riders = riders_df[riders_df['owner'] == owner]['rider_name'].tolist()
                    st.write(", ".join(riders))
    else:
        st.warning("No data found! Click the 'Sync' button in the sidebar to fetch 2025 results.")

if __name__ == "__main__":
    main()
