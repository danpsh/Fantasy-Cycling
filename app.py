import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px

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

# --- 2. DATA SCRAPER ---
@st.cache_data(show_spinner="Fetching Results from PCS...")
def scrape_data(schedule_df, year):
    all_results = []
    for _, row in schedule_df.iterrows():
        try:
            # Construct the 2025 or 2026 URL
            base_url = row['url'].rsplit('/', 1)[0]
            target_url = f"{base_url}/{year}"
            
            race = Race(target_url)
            stages = race.stages()
            urls = [s['stage_url'] for s in stages] if stages else [target_url]
            
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

# --- 3. MAIN APP ---
def main():
    with st.sidebar:
        st.header("App Controls")
        # Toggle between 2025 (Test) and 2026 (Live)
        target_year = st.selectbox("Select Season", [2025, 2026], index=0)
        
        if st.button("🔄 Sync Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        page = st.radio("View", ["Leaderboard", "Race Results", "Rosters"])

    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
        results_raw = scrape_data(schedule_df, target_year)
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title(f"🏆 {target_year} Standings")
            standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner'), use_container_width=True)
            st.table(standings)

        elif page == "Race Results":
            st.title(f"📊 {target_year} Detailed Points")
            st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False))

        else:
            st.title("📋 Rosters")
            for owner in riders_df['owner'].unique():
                st.subheader(f"Team {owner}")
                st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.warning(f"No results found for {target_year}. Click Sync Results!")

if __name__ == "__main__":
    main()
