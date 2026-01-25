import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
from io import BytesIO

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception as e:
        st.error(f"File Loading Error: {e}")
        return None, None, None

# --- 2. PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if results_raw is not None:
    # A. Prepare Roster
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # B. Melt Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    results_raw['Race_ID'] = range(len(results_raw))
    
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name', 'Stage', 'Race_ID'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', value_name='rider_name'
    )
    
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # C. Merge Tier (CRITICAL STEP)
    # This matches your Excel "Race Name" to Schedule "race_name"
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    # D. Merge Owner
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    
    # E. Score calculation
    def calculate_points(row):
        tier_data = SCORING.get(row['tier'], {})
        return tier_data.get(row['rank'], 0)

    processed['pts'] = processed.apply(calculate_points, axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()

# --- 3. UI ---
st.title("🏆 2026 Fantasy Leaderboard")

if results_raw is not None:
    # Display Leaderboard
    if not leaderboard.empty:
        st.table(leaderboard.rename(columns={'owner': 'Team', 'pts': 'Total Points'}))
        
        # Plotly Chart
        fig = px.bar(leaderboard, x='owner', y='pts', text_auto=True, color='owner')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No matches found between Results and Roster. Check rider names!")

    # --- DEBUG SECTION ---
    with st.expander("🛠️ Debugger: Why am I seeing 0 points?"):
        st.write("### 1. Check Schedule Connection")
        missing_tiers = df_long[df_long['tier'].isna()]['Race Name'].unique()
        if len(missing_tiers) > 0:
            st.error(f"These races in Excel don't match your schedule.csv: {missing_tiers}")
        else:
            st.success("All races matched the schedule successfully!")

        st.write("### 2. Check Rider Matching")
        st.write("Names in your Excel that are NOT in your Roster:")
        excel_names = set(df_long['match_name'].unique())
        roster_names = set(riders_df['match_name'].unique())
        unmatched = excel_names - roster_names
        st.write(list(unmatched)[:10]) # Show first 10
