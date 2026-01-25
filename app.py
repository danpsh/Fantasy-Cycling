import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
from io import BytesIO

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy Cycling", layout="wide")

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
    except Exception:
        return None, None, None

# --- 2. DATA PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if results_raw is not None and riders_df is not None and schedule_df is not None:
    # Prepare Roster
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Process Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    results_raw['Race_ID'] = range(len(results_raw))
    
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name', 'Stage', 'Race_ID'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', value_name='rider_name'
    )
    
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # Merge Tier and Owner
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    
    # Calculate Points
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()

    # --- 3. SIDEBAR (TEAM ROSTERS) ---
    with st.sidebar:
        st.title("🏆 Teams & Rosters")
        owners = sorted(riders_df['owner'].unique())
        for owner in owners:
            with st.expander(f"Team {owner}", expanded=True):
                team_list = riders_df[riders_df['owner'] == owner]['rider_name'].tolist()
                for r in team_list:
                    st.write(f"• {r}")
        st.divider()
        if st.sidebar.button("🔄 Sync GitHub Data"):
            st.cache_data.clear()
            st.rerun()

    # --- 4. MAIN DASHBOARD ---
    st.title("📊 2026 Fantasy Leaderboard")
    
    if not leaderboard.empty:
        # Top Metrics
        m1, m2 = st.columns(2)
        for i, row in leaderboard.iterrows():
            with (m1 if i == 0 else m2):
                st.metric(label=f"Team {row['owner']}", value=f"{row['pts']} Pts")

        # History and Charts
        st.divider()
        tab1, tab2 = st.tabs(["Performance Chart", "Scoring History"])
        
        with tab1:
            chart_data = processed.groupby(['Date', 'owner'])['pts'].sum().reset_index().sort_values('Date')
            chart_data['Total'] = chart_data.groupby('owner')['pts'].cumsum()
            fig = px.line(chart_data, x='Date', y='Total', color='owner', markers=True, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.dataframe(processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False), hide_index=True, use_container_width=True)
    else:
        st.warning("Data loaded, but no points scored yet. Ensure Rider Names in Excel match your Roster exactly!")
else:
    st.error("Missing files on GitHub. Please ensure riders.csv, schedule.csv, and results.xlsx are present.")
