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

# --- 2. DATA LOADING & PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if results_raw is not None and riders_df is not None and schedule_df is not None:
    # Prepare Roster
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Process Results (Melt Wide to Long)
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

    # --- 3. SIDEBAR (SINGLE ROSTER TAB) ---
    with st.sidebar:
        st.title("🏆 League Info")
        with st.expander("👤 View Team Rosters", expanded=False):
            owners = sorted(riders_df['owner'].unique())
            # Split rosters into two small columns inside the expander
            col_a, col_b = st.columns(2)
            for i, owner in enumerate(owners):
                target_col = col_a if i % 2 == 0 else col_b
                with target_col:
                    st.markdown(f"**{owner}**")
                    team_list = riders_df[riders_df['owner'] == owner]['rider_name'].tolist()
                    for r in team_list:
                        st.caption(f"• {r}")
        
        st.divider()
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # --- 4. MAIN DASHBOARD ---
    st.title("🥇 2026 Fantasy Standings")
    
    if not leaderboard.empty:
        # Top Metrics
        m1, m2 = st.columns(2)
        for i, row in leaderboard.iterrows():
            with (m1 if i == 0 else m2):
                st.metric(label=f"Team {row['owner']}", value=f"{row['pts']} Pts")

        st.write("---")
        
        # Scoring History Table
        st.subheader("Recent Scoring Events")
        history_df = processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False)
        history_df.columns = ['Date', 'Race', 'Stage', 'Rider', 'Owner', 'Points']
        st.dataframe(history_df, hide_index=True, use_container_width=True)
        
    else:
        st.info("No points recorded yet. Check your results.xlsx and ensure names match the rosters.")
else:
    st.error("Missing data files. Ensure riders.csv, schedule.csv, and results.xlsx are in your GitHub repository.")
