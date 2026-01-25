import streamlit as st
import pandas as pd
import unicodedata

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy Standings", layout="wide", initial_sidebar_state="collapsed")

# CSS to hide sidebar and header
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    </style>
""", unsafe_allow_html=True)

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
    
    # Process Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    df_long = results_raw.melt(id_vars=['Date', 'Race Name', 'Stage'], value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract('(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # Merge and Points
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    # Aggregates
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    rider_points = processed.groupby(['owner', 'rider_name_y'])['pts'].sum().reset_index()

    # --- 3. MAIN DASHBOARD ---
    st.title("2026 Fantasy Standings")
    
    # Total Score Metrics
    m1, m2 = st.columns(2)
    for i, name in enumerate(["Tanner", "Daniel"]):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"Team {name} Total", value=f"{score} Pts")

    st.divider()

    # TOP 3 SCORERS SECTION
    st.subheader("Top 3 Scorers")
    t1, t2 = st.columns(2)
    for i, name in enumerate(["Tanner", "Daniel"]):
        with (t1 if i == 0 else t2):
            st.markdown(f"**Team {name}**") # Removed "MVPs"
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name_y', 'pts']]
            top3.columns = ['Rider', 'Points']
            top3.index = range(1, len(top3) + 1)
            st.table(top3)

    st.divider()

    # RECENT RESULTS SECTION
    st.subheader("Recent Results")
    if not processed.empty:
        history_df = processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False)
        history_df['Date'] = pd.to_datetime(history_df['Date']).dt.strftime('%m-%d')
        history_df.columns = ['Date', 'Race', 'Stage', 'Rider', 'Owner', 'Points']
        st.dataframe(history_df, hide_index=True, use_container_width=True)
    else:
        st.info("No race results recorded yet.")

    st.divider()

    # --- 4. MASTER ROSTER ---
    st.subheader("Master Roster")
    tan_df = riders_df[riders_df['owner'] == 'Tanner'].copy().reset_index(drop=True)
    tan_df = tan_df.merge(rider_points, left_on='rider_name', right_on='rider_name_y', how='left').fillna(0)

    dan_df = riders_df[riders_df['owner'] == 'Daniel'].copy().reset_index(drop=True)
    dan_df = dan_df.merge(rider_points, left_on='rider_name', right_on='rider_name_y', how='left').fillna(0)

    max_len = max(len(dan_df), len(tan_df))
    master_table = pd.DataFrame({
        "#": range(1, max_len + 1),
        "Team Tanner": tan_df['rider_name'],
        "Points ": tan_df['pts'].astype(int), 
        "Team Daniel": dan_df['rider_name'],
        "Points": dan_df['pts'].astype(int)
    })

    st.dataframe(master_table, hide_index=True, use_container_width=True, height=(max_len + 1) * 36)

    if st.button("Refresh Results"):
        st.cache_data.clear()
        st.rerun()
else:
    st.error("Missing data files.")
