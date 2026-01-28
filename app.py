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

def parse_schedule_date(date_str):
    try:
        clean_date = str(date_str).replace('–', '|').replace('-', '|')
        start_part = clean_date.split('|')[0].strip()
        return pd.to_datetime(f"{start_part} 2026", format='%b %d %Y', errors='coerce')
    except:
        return pd.NaT

@st.cache_data(ttl=300)
def load_all_data():
    try:
        # Load Riders and fix date columns
        riders = pd.read_csv('riders.csv')
        riders['add_date'] = pd.to_datetime(riders['add_date'], errors='coerce')
        # If drop_date is missing, they are a current rider (set to far future)
        riders['drop_date'] = pd.to_datetime(riders['drop_date'], errors='coerce').fillna(pd.Timestamp('2026-12-31'))
        
        schedule = pd.read_csv('schedule.csv')
        
        # Load Results and fix date column
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
        
        return riders, schedule, results
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return None, None, None

# --- 3. DATA LOGIC ---
riders_df, schedule_df, results_raw = load_all_data()

if all(v is not None for v in [riders_df, schedule_df, results_raw]):
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Process Results into long format
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    id_cols = ['Date', 'Race Name']
    if 'Stage' in results_raw.columns:
        id_cols.append('Stage')
        
    df_long = results_raw.melt(id_vars=id_cols, value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name_res')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name_res'].apply(normalize_name)
    
    # Merge schedule for tier information
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    # Merge with riders list to identify owners
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name', 'add_date', 'drop_date']], on='match_name', how='inner')
    
    # --- TEMPORAL SCORING FILTER ---
    # Only keep results where Race Date is between Add and Drop dates
    processed = processed[(processed['Date'] >= processed['add_date']) & (processed['Date'] <= processed['drop_date'])].copy()
    
    # Assign points based on Tier and Rank
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    # Aggregations
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist() if not leaderboard.empty else ["Tanner", "Daniel"]
    rider_points = processed.groupby(['owner', 'rider_name'])['pts'].sum().reset_index()

# --- 4. PAGE VIEWS ---

def show_dashboard():
    st.title("2026 Fantasy Standings")
    
    # Score Metrics
    m1, m2 = st.columns(2)
    for i, name in enumerate(display_order):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"{name} Total Score", value=f"{score} Pts")

    st.divider()

    # Top Performers
    st.subheader("Top Scorers per Owner")
    t1, t2 = st.columns(2)
    for i, name in enumerate(display_order):
        with (t1 if i == 0 else t2):
            st.markdown(f"**{name}'s Best Assets**")
            top_scorers = rider_points[rider_points['owner'] == name].nlargest(5, 'pts')[['rider_name', 'pts']]
            if not top_scorers.empty:
                top_scorers['rider_name'] = top_scorers['rider_name'].apply(shorten_name)
                top_scorers.columns = ['Rider', 'Points']
                st.dataframe(top_scorers, hide_index=True, use_container_width=True)
            else:
                st.info("Waiting for points to be recorded.")

    st.divider()

    # Latest Results
    st.subheader("Recent Scoring Events")
    if not processed.empty:
        recent = processed.sort_values(['Date', 'pts'], ascending=[False, False]).head(10).copy()
        recent['Date'] = recent['Date'].dt.strftime('%b %d')
        
        def format_stg(val):
            return f"S{int(float(val))}" if pd.notna(val) and val != "" else "—"
            
        recent['Stg'] = recent['Stage'].apply(format_stg) if 'Stage' in recent.columns else "—"
        recent_disp = recent[['Date', 'Race Name', 'Stg', 'rider_name', 'pts']].copy()
        recent_disp['rider_name'] = recent_disp['rider_name'].apply(shorten_name)
        recent_disp.columns = ['Date', 'Race', 'Stg', 'Rider', 'Pts']
        st.dataframe(recent_disp, hide_index=True, use_container_width=True)
    else:
        st.write("No race results processed in your window yet.")

def show_roster():
    st.title("Master Roster & History")
    
    # Show active and historical riders
    roster_display = riders_df.copy()
    roster_display['Status'] = roster_display['drop_date'].apply(lambda x: "Current" if x >= pd.Timestamp('2026-12-30') else "Dropped")
    roster_display['Add'] = roster_display['add_date'].dt.strftime('%m/%d/%y')
    roster_display['Drop'] = roster_display['drop_date'].apply(lambda x: "—" if x >= pd.Timestamp('2026-12-30') else x.strftime('%m/%d/%y'))
    
    st.dataframe(roster_display[['rider_name', 'owner', 'Add', 'Drop', 'Status']], hide_index=True, use_container_width=True)

def show_schedule():
    st.title("2026 UCI Schedule")
    st.dataframe(schedule_df[['date', 'race_name', 'tier', 'race_type']], hide_index=True, use_container_width=True)

# --- 5. NAVIGATION ---
pg = st.navigation([
    st.Page(show_dashboard, title="Dashboard"), 
    st.Page(show_roster, title="Master Roster"), 
    st.Page(show_schedule, title="Full Schedule")
])

with st.sidebar:
    st.write(f"**Last Sync:** {datetime.now().strftime('%H:%M:%S')}")
    if st.button("Force Refresh"):
        st.cache_data.clear()
        st.rerun()

pg.run()
