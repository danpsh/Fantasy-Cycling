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
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    results_raw['Race_ID'] = range(len(results_raw))
    
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name', 'Stage', 'Race_ID'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', value_name='rider_name'
    )
    
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()

    # --- 3. SIDEBAR (CLEAN) ---
    with st.sidebar:
        st.header("Settings")
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # --- 4. MAIN DASHBOARD ---
    st.title("2026 Fantasy Standings")
    
    if not leaderboard.empty:
        # Leaderboard Metrics
        m1, m2 = st.columns(2)
        for i, row in leaderboard.iterrows():
            with (m1 if i == 0 else m2):
                st.metric(label=f"Team {row['owner']}", value=f"{row['pts']} Pts")

        st.divider()

        # Top 3 Scorers per Team
        st.subheader("Top 3 Scorers per Team")
        rider_totals = processed.groupby(['owner', 'rider_name_y'])['pts'].sum().reset_index()
        rider_totals = rider_totals.sort_values(['owner', 'pts'], ascending=[True, False])
        
        c1, c2 = st.columns(2)
        # We manually use Daniel and Tanner names here
        for i, name in enumerate(["Daniel", "Tanner"]):
            with (c1 if i == 0 else c2):
                st.write(f"**Team {name} Top Performers**")
                team_top = rider_totals[rider_totals['owner'] == name][['rider_name_y', 'pts']].head(3)
                team_top.columns = ['Rider', 'Points']
                team_top.index = range(1, len(team_top) + 1)
                st.table(team_top)

        st.divider()
        
        # Scoring History Table
        st.subheader("Recent Results")
        history_df = processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False)
        history_df.columns = ['Date', 'Race', 'Stage', 'Rider', 'Owner', 'Points']
        st.dataframe(history_df, hide_index=True, use_container_width=True)

        st.divider()

        # --- 5. FULL ROSTERS AT BOTTOM ---
        st.subheader("Full Team Rosters")
        r_col1, r_col2 = st.columns(2)
        
        with r_col1:
            st.markdown("### Team Daniel")
            dan_riders = riders_df[riders_df['owner'] == "Daniel"]['rider_name'].tolist()
            for r in sorted(dan_riders):
                st.text(f"• {r}")

        with r_col2:
            st.markdown("### Team Tanner")
            tan_riders = riders_df[riders_df['owner'] == "Tanner"]['rider_name'].tolist()
            for r in sorted(tan_riders):
                st.text(f"• {r}")
        
    else:
        st.info("No points recorded yet.")
else:
    st.error("Error: Check if results.xlsx, riders.csv, and schedule.csv are on GitHub.")
