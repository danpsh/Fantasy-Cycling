import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
from io import BytesIO

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide", initial_sidebar_state="expanded")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    try:
        # Loading local files from your repo
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return None, None, None

riders_df, schedule_df, results_raw = load_data()

# --- 3. NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"

def set_page(page_name):
    st.session_state.page = page_name

with st.sidebar:
    st.title("Navigation")
    st.button("📊 Dashboard", use_container_width=True, on_click=set_page, args=("Dashboard",))
    st.button("🚴 Team Rosters", use_container_width=True, on_click=set_page, args=("Team Rosters",))
    st.divider()
    if st.button("🔄 Sync GitHub Data"):
        st.cache_data.clear()
        st.rerun()

# --- 4. PROCESSING LOGIC ---
if results_raw is not None and riders_df is not None:
    # Cleanup rider names for matching
    riders_df['match_name'] = riders_df['rider_name'].str.strip().str.lower()
    
    # Process Wide Results to Long Format
    results_raw['Race_Num'] = range(1, len(results_raw) + 1)
    results_raw['Date'] = pd.to_datetime(results_raw['Date'])

    # Define the ranking columns (1st through 10th)
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    
    # Unpivot the Excel
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name', 'Stage', 'Race_Num'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', 
        value_name='rider_name'
    )
    
    # Calculate rank and clean rider names
    df_long['rank'] = df_long.groupby(['Race_Num']).cumcount() + 1
    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()
    
    # Merge with Owner info and Schedule Tiers
    processed = df_long.merge(riders_df, on='match_name', how='inner')
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')
    
    # Calculate points based on Tier and Rank
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()

    # --- PAGE 1: DASHBOARD ---
    if st.session_state.page == "Dashboard":
        st.title("🏆 2026 Fantasy Cycling Dashboard")
        
        # Top Metrics
        m1, m2 = st.columns(2)
        for i, owner in enumerate(leaderboard['owner']):
            pts = leaderboard[leaderboard['owner'] == owner]['pts'].values[0]
            with (m1 if i == 0 else m2):
                st.metric(label=f"Team {owner}", value=f"{pts} pts")

        st.divider()

        tab1, tab2, tab3 = st.tabs(["Standings Graph", "Top Riders", "Race History"])
        
        with tab1:
            # Cumulative points over time
            chart_data = processed.groupby(['Race_Num', 'owner'])['pts'].sum().reset_index()
            chart_data['Total Points'] = chart_data.groupby('owner')['pts'].cumsum()
            fig = px.line(chart_data, x="Race_Num", y="Total Points", color="owner", markers=True)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            rider_pts = processed.groupby(['rider_name_x', 'owner'])['pts'].sum().sort_values(ascending=False).reset_index()
            st.table(rider_pts.head(10).rename(columns={'rider_name_x': 'Rider', 'owner': 'Team', 'pts': 'Total'}))

        with tab3:
            history = processed.sort_values('Date', ascending=False)
            st.dataframe(history[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']], use_container_width=True, hide_index=True)

    # --- PAGE 2: TEAM ROSTERS ---
    elif st.session_state.page == "Team Rosters":
        st.title("🚴 Team Rosters")
        c1, c2 = st.columns(2)
        owners = sorted(riders_df['owner'].unique())
        for i, owner in enumerate(owners):
            with (c1 if i == 0 else c2):
                st.header(f"Team {owner}")
                team = riders_df[riders_df['owner'] == owner][['rider_name']].reset_index(drop=True)
                st.table(team)
