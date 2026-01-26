import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime
import difflib  # Built-in library for fuzzy matching

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy Standings", layout="wide", initial_sidebar_state="collapsed")

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

# --- 2. 2026 UCI WORLD TOUR CALENDAR REFERENCE ---
UCI_2026_CALENDAR = {
    "Tour Down Under": "2026-01-20",
    "Cadel Evans Great Ocean Road Race": "2026-02-01",
    "UAE Tour": "2026-02-16",
    "Omloop Het Nieuwsblad": "2026-02-28",
    "Strade Bianche": "2026-03-07",
    "Paris-Nice": "2026-03-08",
    "Tirreno-Adriatico": "2026-03-09",
    "Milano-Sanremo": "2026-03-21",
    "Volta a Catalunya": "2026-03-23",
    "E3 Saxo Classic": "2026-03-27",
    "Gent-Wevelgem": "2026-03-29",
    "Dwars door Vlaanderen": "2026-04-01",
    "Tour of Flanders": "2026-04-05",
    "Tour of the Basque Country": "2026-04-06",
    "Paris-Roubaix": "2026-04-12",
    "Amstel Gold Race": "2026-04-19",
    "La Fleche Wallonne": "2026-04-22",
    "Liege-Bastogne-Liege": "2026-04-26",
    "Tour de Romandie": "2026-04-28",
    "Eschborn-Frankfurt": "2026-05-01",
    "Giro d'Italia": "2026-05-09",
    "Criterium du Dauphine": "2026-06-07",
    "Tour de Suisse": "2026-06-14",
    "Tour de France": "2026-07-04",
    "Donostia San Sebastian Klasikoa": "2026-08-01",
    "Tour of Poland": "2026-08-03",
    "BEMER Cyclassics": "2026-08-16",
    "Vuelta a Espana": "2026-08-22",
    "Bretagne Classic": "2026-08-30",
    "GP de Quebec": "2026-09-11",
    "GP de Montreal": "2026-09-13",
    "World Championships Road Race": "2026-09-27",
    "Il Lombardia": "2026-10-10",
    "Tour of Guangxi": "2026-10-13"
}

def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

def get_closest_date(race_name):
    """Finds the date for a race even if spelling isn't perfect."""
    official_names = list(UCI_2026_CALENDAR.keys())
    match = difflib.get_close_matches(race_name, official_names, n=1, cutoff=0.6)
    if match:
        return UCI_2026_CALENDAR[match[0]]
    return None

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        return riders, schedule, results
    except Exception:
        return None, None, None

# --- 3. DATA PROCESSING ---
riders_df, schedule_df, results_raw = load_all_data()

if results_raw is not None and riders_df is not None and schedule_df is not None:
    # AUTO-ASSIGN DATES to your schedule.csv
    schedule_df['date_assigned'] = schedule_df['race_name'].apply(get_closest_date)
    schedule_df['date_dt'] = pd.to_datetime(schedule_df['date_assigned'])
    
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    # Process Results
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    df_long = results_raw.melt(id_vars=['Date', 'Race Name', 'Stage'], value_vars=rank_cols, var_name='Pos_Label', value_name='rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['rider_name'].apply(normalize_name)
    
    # Merge and Points
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    processed = df_long.merge(riders_df[['match_name', 'owner', 'rider_name']], on='match_name', how='inner')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    # Aggregates
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    rider_points = processed.groupby(['owner', 'rider_name_y'])['pts'].sum().reset_index()

    # --- 4. MAIN DASHBOARD ---
    st.title("🏆 2026 Fantasy Standings")
    
    # Total Score Metrics
    m1, m2 = st.columns(2)
    for i, name in enumerate(["Tanner", "Daniel"]):
        score = leaderboard[leaderboard['owner'] == name]['pts'].sum() if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"Team {name} Total", value=f"{score} Pts")

    st.divider()

    # UPCOMING RACES SECTION
    st.subheader("🗓️ Next 3 Upcoming Races")
    today = pd.Timestamp(datetime.now().date())
    
    # Filter for future races that actually have an assigned date
    upcoming = schedule_df[schedule_df['date_dt'] >= today].sort_values('date_dt').head(3)
    
    if not upcoming.empty:
        upcoming_display = upcoming[['date_assigned', 'race_name', 'tier']].copy()
        upcoming_display.columns = ['Date', 'Race Name', 'Tier']
        st.table(upcoming_display)
    else:
        st.info("No upcoming races found in your schedule list for the rest of 2026.")

    st.divider()

    # TOP 3 SCORERS SECTION
    st.subheader("⭐ Top 3 Scorers")
    t1, t2 = st.columns(2)
    for i, name in enumerate(["Tanner", "Daniel"]):
        with (t1 if i == 0 else t2):
            st.markdown(f"**Team {name}**")
            top3 = rider_points[rider_points['owner'] == name].nlargest(3, 'pts')[['rider_name_y', 'pts']]
            if not top3.empty:
                top3.columns = ['Rider', 'Points']
                top3.index = range(1, len(top3) + 1)
                st.table(top3)
            else:
                st.write("No points scored yet.")

    st.divider()

    # RECENT RESULTS SECTION
    st.subheader("🏁 Recent Results")
    if not processed.empty:
        history_df = processed[['Date', 'Race Name', 'Stage', 'rider_name_y', 'owner', 'pts']].sort_values('Date', ascending=False)
        history_df['Date'] = pd.to_datetime(history_df['Date']).dt.strftime('%m-%d')
        history_df.columns = ['Date', 'Race', 'Stage', 'Rider', 'Owner', 'Points']
        st.dataframe(history_df, hide_index=True, use_container_width=True)
    else:
        st.info("No race results recorded yet.")

    st.divider()

    # --- 5. MASTER ROSTER ---
    st.subheader("📋 Master Roster")
    
    # Process for side-by-side display
    master_roster = riders_df.merge(rider_points, left_on=['rider_name', 'owner'], right_on=['rider_name_y', 'owner'], how='left').fillna(0)
    
    tan_roster = master_roster[master_roster['owner'] == 'Tanner'].sort_values('pts', ascending=False)
    dan_roster = master_roster[master_roster['owner'] == 'Daniel'].sort_values('pts', ascending=False)

    max_len = max(len(dan_roster), len(tan_roster))
    
    final_df = pd.DataFrame({
        "Tanner's Rider": tan_roster['rider_name'].tolist() + [""] * (max_len - len(tan_roster)),
        "Pts ": tan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(tan_roster)),
        "Daniel's Rider": dan_roster['rider_name'].tolist() + [""] * (max_len - len(dan_roster)),
        "Pts": dan_roster['pts'].astype(int).tolist() + [0] * (max_len - len(dan_roster))
    })
    st.dataframe(final_df, use_container_width=True, hide_index=True)

    if st.button("Refresh Results"):
        st.cache_data.clear()
        st.rerun()
else:
    st.error("Missing data files. Check that riders.csv, schedule.csv, and results.xlsx exist.")
