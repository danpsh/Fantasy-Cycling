import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
from datetime import datetime
import requests

# --- 1. SETTINGS ---
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

# --- 2. STEALTH SCRAPER ---
@st.cache_data(show_spinner="Connecting to PCS (Stealth Mode)...")
def scrape_data(schedule_df, year):
    all_results = []
    logs = []
    
    for _, row in schedule_df.iterrows():
        try:
            # Construct URL
            base_url = row['url'].strip().strip('/')
            url = base_url if str(year) in base_url else f"{base_url}/{year}"
            
            # Use the library but add a generic check
            race = Race(url)
            logs.append(f"Checking: {url}")
            
            try:
                stages = race.stages()
                # 2026 Update: If it's a one-day race, stages() returns empty
                target_urls = [s['stage_url'] for s in stages] if stages else [f"{url}/result"]
            except:
                target_urls = [f"{url}/result"]

            for s_url in target_urls:
                stage_data = Stage(s_url)
                res = stage_data.results()
                if res:
                    df = pd.DataFrame(res)
                    df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
                    df = df[df['rank'] <= 10].copy()
                    df['Race Name'] = row['race_name']
                    df['Stage'] = s_url.split('/')[-1].replace('-', ' ').title()
                    df['tier'] = row['tier']
                    all_results.append(df)
                    logs.append(f"✅ Found {len(df)} results for {s_url}")
                else:
                    logs.append(f"⚠️ No results on page: {s_url}")
        except Exception as e:
            logs.append(f"❌ Error on {row['race_name']}: {e}")

    final_df = pd.concat(all_results, ignore_index=True) if all_results else None
    return final_df, logs

# --- 3. UI ---
def main():
    st.sidebar.title("Admin")
    year = st.sidebar.selectbox("Season", [2026, 2025])
    
    if st.sidebar.button("🔄 Force Sync"):
        st.cache_data.clear()
        st.rerun()

    # File Loader
    try:
        riders_df = pd.read_csv('riders.csv')
        schedule_df = pd.read_csv('schedule.csv')
    except Exception as e:
        st.error(f"File Error: {e}")
        return

    # Scrape with Logs
    results_raw, debug_logs = scrape_data(schedule_df, year)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        st.header(f"🏆 {year} Leaderboard")
        if not merged.empty:
            standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
            st.plotly_chart(px.bar(standings, x='owner', y='pts', text_auto=True))
            st.table(standings)
        else:
            st.warning("Found results on PCS, but none of your riders matched. Check names in riders.csv!")
            st.write("**Top names found in latest race:**", results_raw['rider_name'].head(5).tolist())
    else:
        st.error("No data found at all. Check the System Log below.")

    # --- DEBUG LOG SECTION ---
    with st.expander("🛠️ System Log (Click to see what's happening)"):
        for log in debug_logs:
            st.write(log)

if __name__ == "__main__":
    main()
