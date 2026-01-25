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

# --- 2. HELPER FUNCTIONS ---
def normalize_name(name):
    """Removes accents, dashes, and extra spaces for perfect matching."""
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

@st.cache_data(ttl=600)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception as e:
        st.error(f"Critical Error: Make sure results.xlsx, riders.csv, and schedule.csv are in GitHub. Details: {e}")
        return None, None, None

# --- 3. DATA PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if results_raw is not None:
    # A. Normalize Roster
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # B. Melt Excel (Wide to Long)
    # This turns your 10 columns (1st, 2nd...) into individual rows
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    
    # Create a unique ID for each race entry to calculate ranks correctly
    results_raw['Race_ID'] = range(len(results_raw)) 
    
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name', 'Stage', 'Race_ID'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', 
        value_name='rider_name'
    )
    
    # Extract rank number from label (e.g., '1st' -> 1)
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # C. Merge Tiers from Schedule
    # Ensure schedule.csv has a 'race_name' column that matches Excel's 'Race Name'
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    # D. Merge Owners from Roster
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    
    # E. Calculate Points
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()

# --- 4. NAVIGATION & UI ---
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"

with st.sidebar:
    st.title("🏆 Fantasy Cycling")
    if st.button("📊 Dashboard", use_container_width=True): st.session_state.page = "Dashboard"
    if st.button("🚴 Team Rosters", use_container_width=True): st.session_state.page = "Rosters"
    st.divider()
    if st.button("🔄 Sync New Excel Data"):
        st.cache_data.clear()
        st.rerun()

# --- 5. PAGE VIEWS ---
if st.session_state.page == "Dashboard":
    st.title("Season Standings")
    
    # Total Score Metrics
    cols = st.columns(len(leaderboard))
    for i, row in leaderboard.iterrows():
        cols[i].metric(row['owner'], f"{row['pts']} pts")
    
    st.divider()
    
    # Charts and Tables
    tab1, tab2 = st.tabs(["Performance Chart", "Detailed Results"])
    with tab1:
        # Cumulative score plot
        chart_data = processed.groupby(['Date', 'owner'])['pts'].sum().reset_index()
        chart_data = chart_data.sort_values('Date')
        chart_data['Total'] = chart_data.groupby('owner')['pts'].cumsum()
        fig = px.line(chart_data, x='Date', y='Total', color='owner', markers=True)
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        # Show what each rider actually scored
        st.dataframe(processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False), hide_index=True)

elif st.session_state.page == "Rosters":
    st.title("Official Team Rosters")
    roster_cols = st.columns(2)
    for i, owner in enumerate(riders_df['owner'].unique()):
        with roster_cols[i % 2]:
            st.subheader(f"Team {owner}")
            st.table(riders_df[riders_df['owner'] == owner][['rider_name']])
