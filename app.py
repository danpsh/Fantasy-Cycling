import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px

# --- SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return " ".join(sorted(name.lower().replace('-', ' ').split()))

# --- DATA SCRAPER ---
@st.cache_data(show_spinner="Updating 2026 Results...")
def scrape_data(schedule_df):
    all_results = []
    for _, row in schedule_df.iterrows():
        try:
            race = Race(row['url'])
            stages = race.stages()
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

# --- MAIN APP ---
def main():
    with st.sidebar:
        st.header("Admin")
        if st.button("🔄 Sync Results", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        page = st.radio("Go to", ["Leaderboard", "Detailed Results", "Rosters"])

    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
        results_raw = scrape_data(schedule_df)
    except Exception as e:
        st.error(f"Missing CSV files in GitHub! Error: {e}")
        return

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        final_df = results_raw.merge(riders_df, on='match_name', how='inner')
        final_df['pts'] = final_df.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            st.title("🏆 League Standings")
            standings = final_df.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            fig = px.bar(standings, x='owner', y='pts', color='owner', title="Total Points by Owner")
            st.plotly_chart(fig, use_container_width=True)
            st.table(standings)

        elif page == "Detailed Results":
            st.title("📊 All Stage Points")
            st.dataframe(final_df[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']].sort_values('Date', ascending=False))

        else:
            st.title("📋 Rosters")
            for owner in riders_df['owner'].unique():
                st.subheader(f"Team {owner}")
                st.write(", ".join(riders_df[riders_df['owner'] == owner]['rider_name'].tolist()))
    else:
        st.info("No data yet. Hit the Sync button in the sidebar to fetch 2026 results!")

if __name__ == "__main__":
    main()
