import streamlit as st
import pandas as pd
import unicodedata

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
    # Add an 'original_index' to keep the CSV order
    riders_df['original_index'] = range(len(riders_df))
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Process Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    results_raw['Race_ID'] = range(len(results_raw))
    df_long = results_raw.melt(id_vars=['Date', 'Race Name', 'Stage', 'Race_ID'], value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # Merge Data
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    # Calculate Totals
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    rider_points = processed.groupby('rider_name_y')['pts'].sum().reset_index()

    # --- 3. DASHBOARD ---
    st.title("2026 Fantasy Standings")
    
    # Standings Metrics (Fixed Columns: Daniel Left, Tanner Right)
    m1, m2 = st.columns(2)
    for i, name in enumerate(["Daniel", "Tanner"]):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"Team {name}", value=f"{score} Pts")

    st.divider()

    # Recent Results Table
    st.subheader("Recent Results")
    if not processed.empty:
        history_df = processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False)
        history_df.columns = ['Date', 'Race', 'Stage', 'Rider', 'Owner', 'Points']
        st.dataframe(history_df, hide_index=True, use_container_width=True)

    st.divider()

    # --- 4. FULL ROSTERS AS TABLES (FIXED ORDER) ---
    st.subheader("Team Rosters")
    r_col1, r_col2 = st.columns(2)
    
    for i, owner_name in enumerate(["Daniel", "Tanner"]):
        with (r_col1 if i == 0 else r_col2):
            st.write(f"**Team {owner_name}**")
            
            # Filter riders and keep original CSV order
            team_riders = riders_df[riders_df['owner'] == owner_name].sort_values('original_index')
            
            # Merge with points (keeping the original_index order)
            team_table = team_riders.merge(rider_points, left_on='rider_name', right_on='rider_name_y', how='left').fillna(0)
            
            # Clean up the display table
            display_table = team_table[['rider_name', 'pts']].copy()
            display_table.columns = ['Rider', 'Total Pts']
            
            st.dataframe(display_table, hide_index=True, use_container_width=True)

    if st.sidebar.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

else:
    st.error("Missing data files on GitHub.")
