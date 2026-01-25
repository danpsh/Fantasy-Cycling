import streamlit as st
import pandas as pd
from procyclingstats import Race, Stage
import unicodedata
import plotly.express as px
import os

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="Cycling Fantasy Diagnostic", layout="wide")

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

# --- 2. THE DIAGNOSTIC SCRAPER ---
@st.cache_data(show_spinner="Attempting to reach ProCyclingStats...")
def scrape_data(schedule_df):
    all_results = []
    
    # Check if schedule_df is empty
    if schedule_df is None or schedule_df.empty:
        st.sidebar.error("Scraper received an empty schedule!")
        return None

    for _, row in schedule_df.iterrows():
        try:
            url = row['url'].strip()
            # Safety: Remove leading slashes if they exist
            if url.startswith('/'): url = url[1:]
            
            race = Race(url)
            try:
                stages = race.stages()
            except:
                stages = []
            
            # If no stages (one day race), use result subpage
            target_urls = [s['stage_url'] for s in stages] if stages else [f"{url}/result"]
            
            for s_url in target_urls:
                try:
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
            st.sidebar.warning(f"Failed race {row['race_name']}: {e}")
            continue
            
    return pd.concat(all_results, ignore_index=True) if all_results else None

# --- 3. UI & FOLDER CHECK ---
def main():
    st.title("🚴‍♂️ Fantasy Cycling: 2025 Test Mode")
    
    with st.sidebar:
        st.header("App Admin")
        if st.button("🔄 Force Refresh & Sync", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        page = st.radio("Navigation", ["Leaderboard", "Detailed Results", "System Health"])

    # SYSTEM HEALTH CHECK
    files_in_dir = os.listdir('.')
    riders_exists = 'riders.csv' in files_in_dir
    schedule_exists = 'schedule.csv' in files_in_dir
    reqs_exists = 'requirements.txt' in files_in_dir

    if page == "System Health":
        st.header("📂 Folder & File Check")
        st.write(f"**Files found in GitHub:** {files_in_dir}")
        st.write(f"**riders.csv exists?** {'✅' if riders_exists else '❌'}")
        st.write(f"**schedule.csv exists?** {'✅' if schedule_exists else '❌'}")
        st.write(f"**requirements.txt exists?** {'✅' if reqs_exists else '❌'}")
        
        if schedule_exists:
            st.write("---")
            st.write("**Current Schedule Content:**")
            st.dataframe(pd.read_csv('schedule.csv'))
        return

    # LOAD DATA
    if not (riders_exists and schedule_exists):
        st.error("Cannot run. Check 'System Health' tab to see which files are missing.")
        return

    riders_df = pd.read_csv('riders.csv')
    schedule_df = pd.read_csv('schedule.csv')
    
    results_raw = scrape_data(schedule_df)

    if results_raw is not None:
        riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
        results_raw['match_name'] = results_raw['rider_name'].apply(normalize)
        
        merged = results_raw.merge(riders_df, on='match_name', how='inner')
        merged['pts'] = merged.apply(lambda r: SCORING.get(r['tier'], {}).get(int(r['rank']), 0), axis=1)

        if page == "Leaderboard":
            if not merged.empty:
                standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
                st.plotly_chart(px.bar(standings, x='owner', y='pts', color='owner', text_auto=True))
                st.table(standings)
            else:
                st.warning("Scraper found results, but no riders matched. Check your riders.csv names vs PCS names.")
                st.write("First few names found by scraper:")
                st.write(results_raw['rider_name'].head(5).tolist())

        elif page == "Detailed Results":
            st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']])
            
    else:
        st.warning("No data returned from ProCyclingStats. Ensure your schedule.csv URLs look like 'race/tour-down-under/2025'.")

if __name__ == "__main__":
    main()
