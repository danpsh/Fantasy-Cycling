import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="2026 Fantasy Standings", layout="wide", initial_sidebar_state="collapsed")

# Simple CSS to remove sidebar space and make it look cleaner
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stHeader"] {background: rgba(0,0,0,0);}
        .main .block-container {padding-top: 2rem;}
    </style>
""", unsafe_allow_html=True)

# Points Scoring Definition
SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. HELPER FUNCTIONS ---
def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

def shorten_name(name):
    """Converts 'Jonas Vingegaard' to 'J. Vingegaard'"""
    if not isinstance(name, str) or not name.strip(): return ""
    parts = name.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else name

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        # Expecting columns: Date, Race Name, 1st, 2nd, ... 10th
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return None, None, None

# --- 3. DATA PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if all(v is not None for v in [riders_df, schedule_df, results_raw]):
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Transform results from wide to long (one row per result)
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    df_long = results_raw.melt(
        id_vars=['Date', 'Race Name'], 
        value_vars=rank_cols, 
        var_name='Pos_Label', 
        value_name='rider_name'
    )
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # Map Tiers and Owners
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    # Totals for metrics (sorted for leader-first display)
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    if not leaderboard.empty:
        display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist()
    else:
        display_order = ["Tanner", "Daniel"] # Fallback

    # Individual Rider totals
    rider_points = processed.groupby(['owner', 'rider_name_y'])['pts'].sum().reset_index()

    # --- 4. DASHBOARD UI ---
    st.title("🏆 2026 Fantasy Standings")
    
    # LEADER METRICS (Whoever is winning shows first)
    m1, m2 = st.columns(2)
    for i, name in enumerate(display_order):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"{name} Total", value=f"{score} Pts")

    st.divider()

    # RACE SCHEDULE
    st.subheader("🗓️ Race Schedule")
    schedule_display = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    schedule_display.columns = ['Date', 'Race', 'Tier', 'Type']
    st.dataframe(schedule_display, hide_index=True, use_container_width=True)

    st.divider()

    # TOP SCORERS (Leader first)
    st.subheader("⭐ Top 3 Scorers")
    t1, t2 = st.columns(2)
    for i, name in enumerate(display_order):
        with (t1 if i == 0 else t2):
            st.markdown(f"**{name}**")
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name_y', 'pts']]
            if not top3.empty:
                top3['rider_name_y'] = top3['rider_name_y'].apply(shorten_name)
                top3.columns = ['Rider', 'Pts']
                top3.index = range(1, len(top3) + 1)
                st.table(top3)
            else:
                st.write("No points yet.")

    st.divider()

    # MASTER ROSTER (Tanner fixed on Left, Shortened Names)
    st.subheader("📋 Master Roster")
    
    master_roster = riders_df.merge(
        rider_points, 
        left_on=['rider_name', 'owner'], 
        right_on=['rider_name_y', 'owner'], 
        how='left'
    ).fillna(0)
    
    master_roster['short_name'] = master_roster['rider_name'].apply(shorten_name)
    
    # Sort by points within each owner's list
    tan_roster = master_roster[master_roster['owner'] == 'Tanner'].sort_values('pts', ascending=False)
    dan_roster = master_roster[master_roster['owner'] == 'Daniel'].sort_values('pts', ascending=False)
    
    max_len = max(len(tan_roster), len(dan_roster))
    
    # Create the comparison table
    final_df = pd.DataFrame({
        "Tanner": tan_roster['short_name'].tolist() + [""] * (max_len - len(tan_roster)),
        "Pts ": tan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(tan_roster)),
        "Daniel": dan_roster['short_name'].tolist() + [""] * (max_len - len(dan_roster)),
        "Pts": dan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(dan_roster))
    })
    
    # Set height based on number of rows to avoid scrollbar
    st.dataframe(
        final_df, 
        use_container_width=True, 
        hide_index=True, 
        height=(max_len + 1) * 36
    )

    if st.button("Refresh Results"):
        st.cache_data.clear()
        st.rerun()
else:
    st.warning("Please ensure riders.csv, schedule.csv, and results.xlsx are in the same folder.")
