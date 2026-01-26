import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime

# --- 1. SETTINGS ---
st.set_page_config(page_title="2026 Fantasy Standings", layout="wide", initial_sidebar_state="expanded")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. HELPERS ---
def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

def shorten_name(name):
    if not isinstance(name, str) or not name.strip(): return ""
    parts = name.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else name

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception:
        return None, None, None

# --- 3. DATA LOGIC ---
riders_df, schedule_df, results_raw = load_all_data()

if all(v is not None for v in [riders_df, schedule_df, results_raw]):
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    df_long = results_raw.melt(id_vars=['Date', 'Race Name'], value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist() if not leaderboard.empty else ["Tanner", "Daniel"]
    rider_points = processed.groupby(['owner', 'rider_name_y'])['pts'].sum().reset_index()

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
    owners = ["Tanner", "Daniel"]
    for i, name in enumerate(owners):
        with (t1 if i == 0 else t2):
            st.markdown(f"**{name} Top 3**")
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name_y', 'pts']]
            if not top3.empty:
                top3['rider_name_y'] = top3['rider_name_y'].apply(shorten_name)
                top3.columns = ['Rider', 'Pts']
                st.table(top3) # Table is already compact
            else:
                st.write("No points yet.")

    st.divider()

    # SECTION 2: RECENT RESULTS (Shrunk Columns)
    st.subheader("Recent Results")
    if not processed.empty:
        recent = processed.sort_values('Date', ascending=False).head(10).copy()
        recent['Date'] = pd.to_datetime(recent['Date']).dt.strftime('%b %d')
        recent_disp = recent[['Date', 'Race Name', 'rider_name_y', 'pts']].copy()
        recent_disp['rider_name_y'] = recent_disp['rider_name_y'].apply(shorten_name)
        recent_disp.columns = ['Date', 'Race', 'Rider', 'Pts']
        
        st.dataframe(
            recent_disp, 
            hide_index=True, 
            use_container_width=False, # This stops the stretching
            column_config={
                "Date": st.column_config.TextColumn(width=70),
                "Pts": st.column_config.NumberColumn(width=50),
                "Race": st.column_config.TextColumn(width=200),
                "Rider": st.column_config.TextColumn(width=150),
            }
        )

    st.divider()

    # SECTION 3: NEXT 5 RACES (Shrunk Columns)
    st.subheader("Next 5 Upcoming Races")
    next_5 = schedule_df[['race_name', 'date', 'tier']].head(5).copy()
    next_5['tier'] = next_5['tier'].str.replace('Tier ', '', case=False)
    next_5.columns = ['Race', 'Date', 'T']
    st.dataframe(
        next_5, 
        hide_index=True, 
        use_container_width=False, 
        column_config={
            "Date": st.column_config.TextColumn(width=120),
            "T": st.column_config.TextColumn(width=40),
            "Race": st.column_config.TextColumn(width=250),
        }
    )

def show_roster():
    st.title("Master Roster")
    master_roster = riders_df.merge(rider_points, left_on=['rider_name', 'owner'], right_on=['rider_name_y', 'owner'], how='left').fillna(0)
    master_roster['short_name'] = master_roster['rider_name'].apply(shorten_name)
    tan_roster = master_roster[master_roster['owner'] == 'Tanner']
    dan_roster = master_roster[master_roster['owner'] == 'Daniel']
    max_len = max(len(tan_roster), len(dan_roster))
    roster_comp = pd.DataFrame({
        "Tanner": tan_roster['short_name'].tolist() + [""] * (max_len - len(tan_roster)),
        "Pts ": tan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(tan_roster)),
        "Daniel": dan_roster['short_name'].tolist() + [""] * (max_len - len(dan_roster)),
        "Pts": dan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(dan_roster))
    })
    st.dataframe(
        roster_comp, 
        hide_index=True, 
        use_container_width=False, 
        height=(max_len + 1) * 36,
        column_config={
            "Tanner": st.column_config.TextColumn(width=150),
            "Pts ": st.column_config.NumberColumn(width=50),
            "Daniel": st.column_config.TextColumn(width=150),
            "Pts": st.column_config.NumberColumn(width=50),
        }
    )

def show_schedule():
    st.title("Full 2026 Schedule")
    full_sched = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    full_sched['tier'] = full_sched['tier'].str.replace('Tier ', '', case=False)
    full_sched.columns = ['Date', 'Race', 'T', 'Type']
    st.dataframe(
        full_sched, 
        hide_index=True, 
        use_container_width=False,
        column_config={
            "Date": st.column_config.TextColumn(width=120),
            "Race": st.column_config.TextColumn(width=250),
            "T": st.column_config.TextColumn(width=40),
            "Type": st.column_config.TextColumn(width=150),
        }
    )

# --- 5. NAVIGATION ---
pg = st.navigation([
    st.Page(show_dashboard, title="Dashboard"),
    st.Page(show_roster, title="Master Roster"),
    st.Page(show_schedule, title="Full Schedule")
])

with st.sidebar:
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

pg.run()
