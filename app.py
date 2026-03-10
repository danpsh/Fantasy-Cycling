import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime
import re

# --- 1. SETTINGS ---
st.set_page_config(page_title="2026 Fantasy Standings", layout="wide", initial_sidebar_state="expanded")

SCORING = {
    "Tier 1": {1: 40, 2: 36, 3: 32, 4: 28, 5: 24, 6: 20, 7: 16, 8: 12, 9: 8, 10: 4},
    "Tier 2": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 3": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 4": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. HELPERS ---
def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        
        # Identifies the order within the CSV for each owner specifically
        riders['team_pick'] = riders.groupby('owner').cumcount() + 1
        
        riders['add_date'] = pd.to_datetime(riders['add_date'], errors='coerce')
        riders['drop_date'] = pd.to_datetime(riders['drop_date'], errors='coerce').fillna(pd.Timestamp('2026-12-31'))
        
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
        
        return riders, schedule, results
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None

# --- 3. DATA PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

processed = pd.DataFrame()
leaderboard = pd.DataFrame()
rider_points = pd.DataFrame()
display_order = ["Tanner", "Daniel"]

if all(v is not None for v in [riders_df, schedule_df, results_raw]):
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    id_cols = ['Date', 'Race Name']
    if 'Stage' in results_raw.columns:
        id_cols.append('Stage')
        
    df_long = results_raw.melt(id_vars=id_cols, value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    # Merge using rider_name from the riders_df to keep full names consistent
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name', 'team_pick', 'add_date', 'drop_date']], on='match_name', how='inner')
    processed = processed[(processed['Date'] >= processed['add_date']) & (processed['Date'] <= processed['drop_date'])].copy()
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    if not leaderboard.empty:
        display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist()
        
    rider_points = processed.groupby(['owner', 'rider_name'])['pts'].sum().reset_index()

# --- 4. PAGE FUNCTIONS ---

def show_dashboard():
    st.title("2026 Fantasy Standings")
    m1, m2 = st.columns(2)
    for i, name in enumerate(display_order):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"{name} Total", value=f"{score} Pts")

    st.divider()
    st.subheader("Top Scorers")
    t1, t2 = st.columns(2)
    for i, name in enumerate(display_order):
        with (t1 if i == 0 else t2):
            st.markdown(f"**{name} Top 3**")
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name', 'pts']]
            if not top3.empty:
                top3.columns = ['Rider', 'Points']
                st.dataframe(top3, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Season Progress")
    if not processed.empty:
        timeline = processed.groupby(['Date', 'owner'])['pts'].sum().unstack(fill_value=0)
        full_range = pd.date_range(start=timeline.index.min(), end=timeline.index.max())
        st.line_chart(timeline.reindex(full_range, fill_value=0).cumsum(), use_container_width=True)

def show_roster():
    st.title("Master Roster")
    st.caption("Sorted by individual team draft order (Pick 1-30)")
    
    # Merge riders with points earned
    master = riders_df.merge(rider_points, on=['rider_name', 'owner'], how='left').fillna(0)
    
    # Create a range of possible picks (usually 1-30)
    max_picks = int(master['team_pick'].max()) if not master.empty else 30
    pick_indices = list(range(1, max_picks + 1))
    
    # Helper to build column data aligned by pick number
    def get_team_columns(owner_name):
        team_data = master[master['owner'] == owner_name]
        names, pts = [], []
        for p in pick_indices:
            row = team_data[team_data['team_pick'] == p]
            if not row.empty:
                names.append(row.iloc[0]['rider_name'])
                pts.append(int(row.iloc[0]['pts']))
            else:
                names.append("—")
                pts.append(0)
        return names, pts

    tan_names, tan_pts = get_team_columns("Tanner")
    dan_names, dan_pts = get_team_columns("Daniel")

    roster_comp = pd.DataFrame({
        "Pick #": pick_indices,
        "Tanner": tan_names,
        "Pts ": tan_pts,
        "Daniel": dan_names,
        "Pts": dan_pts
    })
    
    st.dataframe(roster_comp, hide_index=True, use_container_width=True)

def show_point_history():
    st.title("YTD Point History")
    if not processed.empty:
        ytd = processed.sort_values(['Date', 'pts'], ascending=[False, False]).copy()
        ytd['Date_Str'] = ytd['Date'].dt.strftime('%b %d')
        
        def format_stage(val):
            if pd.isna(val) or val == "": return "—"
            try: return f"S{int(float(val))}"
            except: return str(val)
        
        ytd['Stg'] = ytd['Stage'].apply(format_stage) if 'Stage' in ytd.columns else "—"
        ytd['Tier_Val'] = ytd['tier'].astype(str).str.replace('Tier ', '', case=False)
        
        ytd_disp = ytd[['Date_Str', 'Race Name', 'Stg', 'Tier_Val', 'rider_name', 'owner', 'rank', 'pts']].copy()
        ytd_disp.columns = ['Date', 'Race', 'Stg', 'Tier', 'Rider', 'Owner', 'Pos', 'Points']
        st.dataframe(ytd_disp, hide_index=True, use_container_width=True)
    else:
        st.info("No scoring data available yet.")

def show_schedule():
    st.title("Full 2026 Schedule")
    full_sched = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    full_sched['tier'] = full_sched['tier'].str.replace('Tier ', '', case=False)
    full_sched.columns = ['Date', 'Race', 'Tier', 'Type']
    st.dataframe(full_sched, hide_index=True, use_container_width=True)

# --- 5. NAVIGATION ---
pg = st.navigation([
    st.Page(show_dashboard, title="Dashboard", icon="📊"), 
    st.Page(show_roster, title="Master Roster", icon="👥"), 
    st.Page(show_point_history, title="Point History", icon="📜"),
    st.Page(show_schedule, title="Full Schedule", icon="📅")
])

with st.sidebar:
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

pg.run()
