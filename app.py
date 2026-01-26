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
    
    # Process Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    id_cols = ['Date', 'Race Name']
    if 'Stage' in results_raw.columns:
        id_cols.append('Stage')
        
    df_long = results_raw.melt(id_vars=id_cols, value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    if not leaderboard.empty:
        display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist()
    else:
        display_order = ["Tanner", "Daniel"]
        
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
    for i, name in enumerate(display_order):
        with (t1 if i == 0 else t2):
            st.markdown(f"**{name} Top 3**")
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name_y', 'pts']]
            if not top3.empty:
                top3['rider_name_y'] = top3['rider_name_y'].apply(shorten_name)
                top3.columns = ['Rider', 'Points']
                st.dataframe(top3, hide_index=True, use_container_width=True)
            else:
                st.write("No points scored.")

    st.divider()

    st.subheader("Recent Results")
    if not processed.empty:
        recent = processed.sort_values(['Date', 'pts'], ascending=[False, False]).head(15).copy()
        recent['Date'] = pd.to_datetime(recent['Date']).dt.strftime('%b %d')
        
        def format_stage(val):
            if pd.isna(val) or val == "": return "—"
            try: return f"S{int(float(val))}"
            except: return str(val)

        recent['Stg'] = recent['Stage'].apply(format_stage) if 'Stage' in recent.columns else "—"
        
        recent_disp = recent[['Date', 'Race Name', 'Stg', 'rider_name_y', 'pts']].copy()
        recent_disp['rider_name_y'] = recent_disp['rider_name_y'].apply(shorten_name)
        recent_disp.columns = ['Date', 'Race', 'Stg', 'Rider', 'Points']
        
        st.dataframe(
            recent_disp, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Date": st.column_config.TextColumn(width="small"),
                "Race": st.column_config.TextColumn(width="medium"),
                "Stg": st.column_config.TextColumn(width="small"),
                "Rider": st.column_config.TextColumn(width="medium"),
                "Points": st.column_config.NumberColumn(width="small"),
            }
        )
    else:
        st.write("No results yet.")

    st.divider()

    st.subheader("Next 5 Upcoming Races")
    future_races = schedule_df[pd.to_datetime(schedule_df['date']) >= datetime.now()].head(5).copy()
    if future_races.empty:
        future_races = schedule_df.head(5).copy()
        
    next_5 = future_races[['race_name', 'date', 'tier']].copy()
    next_5['tier'] = next_5['tier'].str.replace('Tier ', '', case=False)
    next_5.columns = ['Race', 'Date', 'Tier']
    
    st.dataframe(
        next_5, 
        hide_index=True, 
        use_container_width=True, 
        column_config={
            "Date": st.column_config.TextColumn(width="medium"), # Expanded date
            "Tier": st.column_config.TextColumn(width="small"),
            "Race": st.column_config.TextColumn(width="large"),
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
        "Points ": tan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(tan_roster)),
        "Daniel": dan_roster['short_name'].tolist() + [""] * (max_len - len(dan_roster)),
        "Points": dan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(dan_roster))
    })
    
    # use_container_width=True expanded the table to the full screen width
    st.dataframe(roster_comp, hide_index=True, use_container_width=True,
        column_config={
            "Tanner": st.column_config.TextColumn(width="small"), 
            "Points ": st.column_config.NumberColumn(width="small"),
            "Daniel": st.column_config.TextColumn(width="small"), 
            "Points": st.column_config.NumberColumn(width="small")
        })

def show_schedule():
    st.title("Full 2026 Schedule")
    full_sched = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    full_sched['tier'] = full_sched['tier'].str.replace('Tier ', '', case=False)
    full_sched.columns = ['Date', 'Race', 'Tier', 'Type']
    
    st.dataframe(full_sched, hide_index=True, use_container_width=True,
        column_config={
            "Date": st.column_config.TextColumn(width="100"), # Expanded to fit full text
            "Race": st.column_config.TextColumn(width="300"),
            "Tier": st.column_config.TextColumn(width="small"), 
            "Type": st.column_config.TextColumn(width="medium")
        })

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








