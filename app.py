import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="Fantasy Cycling 2026", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return " ".join(sorted(name.lower().replace('-', ' ').split()))

# --- 2. DATA SCRAPER ---
@st.cache_data(show_spinner="Syncing 2026 Race Results...")
def scrape_data(schedule_df):
    all_results = []
    for _, row in schedule_df.iterrows():
        try:
            race = Race(row['url'])
            stages = race.stages()
            # If multi-day, get all stages; if one-day, get the result URL
            urls = [s['stage_url'] for s in stages] if stages else [row['url']]
            
            for s_url in urls:
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
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. APP LOGIC ---
def main():
    # Sidebar Controls
    with st.sidebar:
        st.title("Settings")
        if st.button("🔄 Sync Results (Manual)", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.info("Results are stored in cache. Sync only when a race finishes.")
        
        page = st.radio("Navigation", ["Leaderboard", "Rosters"])

    # Load Files
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
        results_raw = scrape_data(schedule_df)
    except Exception as e:
        st.error(f"Please ensure riders.csv and schedule.csv are in your GitHub folder. Error: {e}")
        return

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        # Merge Scraped Results with Owners
        final_df = results_raw.merge(riders_df, on='match_name', how='inner')
        final_df['pts'] = final_df.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title("🏆 2026 Fantasy Leaderboard")
            standings = final_df.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            st.table(standings)
            
            st.subheader("Recent Points Earned")
            st.dataframe(final_df[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False), hide_index=True)

        else:
            st.title("📋 Team Rosters")
            for owner in riders_df['owner'].unique():
                st.subheader(f"Team {owner}")
                st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.warning("Click 'Sync Results' to pull data for the first time.")

if __name__ == "__main__":
    main()
