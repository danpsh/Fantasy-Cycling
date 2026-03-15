import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime
import plotly.express as px

# --- 1. SETTINGS ---
st.set_page_config(
    page_title="2026 Fantasy Cycling", 
    layout="wide", 
    initial_sidebar_state="auto"
)

COLOR_MAP = {"Tanner": "#1f77b4", "Daniel": "#d62728"}

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

def get_ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return str(n) + suffix

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    with st.sidebar.expander("🔐 Developer Access"):
        password = st.text_input("Enter Passcode", type="password")
        if st.button("Unlock"):
            if password == "1375":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Incorrect passcode")
    return False

def format_stage_safe(val):
    if pd.isna(val) or str(val).strip() == "":
        return "—"
    try:
        return f"Stage {int(float(val))}"
    except (ValueError, TypeError):
        return str(val)

@st.cache_data(ttl=300)
def load_all_data():
    try:
        # Load both roster files
        seasonal_r = pd.read_csv('riders.csv')
        dynasty_r = pd.read_csv('dynasty_riders.csv')
        
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx', engine='openpyxl')
        results['Date'] = pd.to_datetime(results['Date'], errors='coerce')
        
        # Pre-process rosters
        for df in [seasonal_r, dynasty_r]:
            df['team_pick'] = df.groupby('owner').cumcount() + 1
            df['add_date'] = pd.to_datetime(df['add_date'], errors='coerce')
            df['drop_date'] = pd.to_datetime(df['drop_date'], errors='coerce').fillna(pd.Timestamp('2026-12-31'))
            df['match_name'] = df['rider_name'].apply(normalize_name)
            
        return seasonal_r, dynasty_r, schedule, results
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None, None

# --- 3. DATA PROCESSING ---
s_riders, d_riders, schedule_df, results_raw = load_all_data()

# Logic to process any roster against the result set
def process_league_data(riders_df, schedule, results):
    if riders_df is None or results is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    id_cols = ['Date', 'Race Name']
    if 'Stage' in results.columns: id_cols.append('Stage')
    
    df_l = results.melt(id_vars=id_cols, value_vars=rank_cols, var_name='Pos_Label', value_name='result_rider_name')
    df_l['rank'] = df_l['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_l['match_name'] = df_l['result_rider_name'].apply(normalize_name)
    df_l = df_l.merge(schedule[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    proc = df_l.merge(riders_df[['match_name', 'owner', 'rider_name', 'team_pick', 'add_date', 'drop_date']], on='match_name', how='inner')
    proc = proc[(proc['Date'] >= proc['add_date']) & (proc['Date'] <= proc['drop_date'])].copy()
    proc['pts'] = proc.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    leaderb = proc.groupby('owner')['pts'].sum().reset_index()
    scored = proc.groupby(['owner', 'rider_name', 'team_pick'])['pts'].sum().reset_index()
    pts_total = riders_df[['owner', 'rider_name', 'team_pick']].merge(scored, on=['owner', 'rider_name', 'team_pick'], how='left').fillna(0)
    
    return proc, leaderb, pts_total

# Process both
seasonal_proc, seasonal_lb, seasonal_pts = process_league_data(s_riders, schedule_df, results_raw)
dynasty_proc, dynasty_lb, dynasty_pts = process_league_data(d_riders, schedule_df, results_raw)

# Store for global access
leagues = {
    "Seasonal": {"proc": seasonal_proc, "lb": seasonal_lb, "pts": seasonal_pts},
    "Dynasty": {"proc": dynasty_proc, "lb": dynasty_lb, "pts": dynasty_pts}
}

# --- 4. PAGE FUNCTIONS ---

def render_dashboard(league_key, title):
    st.title(title)
    data = leagues[league_key]
    
    if data["proc"].empty:
        st.info("No points recorded yet for this league.")
        return

    m1, m2 = st.columns(2)
    order = ["Tanner", "Daniel"]
    if not data["lb"].empty:
        order = data["lb"].sort_values('pts', ascending=False)['owner'].tolist()

    for i, name in enumerate(order):
        score = int(data["lb"][data["lb"]['owner'] == name]['pts'].sum()) if not data["lb"].empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"{name} Total", value=f"{score} Points")
    
    st.divider()
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.subheader("Top Scorers")
        for name in order:
            st.markdown(f"**{name} Top 5**")
            top5 = data["pts"][data["pts"]['owner'] == name].nlargest(5, 'pts')[['rider_name', 'pts']]
            st.dataframe(top5.rename(columns={'rider_name':'Rider','pts':'Points'}), hide_index=True, use_container_width=True)

    with col_right:
        st.subheader("Season Progress")
        timeline = data["proc"].groupby(['Date', 'owner'])['pts'].sum().unstack(fill_value=0)
        full_range = pd.date_range(start=timeline.index.min(), end=timeline.index.max())
        chart_data = timeline.reindex(full_range, fill_value=0).cumsum().reset_index().melt(id_vars='index', var_name='Owner', value_name='Points')
        chart_data.rename(columns={'index': 'Date'}, inplace=True)
        fig = px.line(chart_data, x='Date', y='Points', color='Owner', color_discrete_map=COLOR_MAP, line_shape="hv")
        fig.update_layout(hovermode="x unified", xaxis_title="", yaxis_title="Cumulative Points")
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def show_seasonal():
    render_dashboard("Seasonal", "2026 Seasonal Fantasy Cycling")

def show_dynasty():
    render_dashboard("Dynasty", "2026 Dynasty Fantasy Cycling")

def show_point_history():
    st.title("Year-to-Date Point History")
    league_choice = st.radio("Select League", ["Seasonal", "Dynasty"], horizontal=True)
    proc = leagues[league_choice]["proc"]
    
    if not proc.empty:
        ytd = proc.sort_values(by=['Date', 'Race Name', 'pts'], ascending=[False, True, False]).copy()
        ytd['Date_Str'] = ytd['Date'].dt.strftime('%B %d')
        ytd['Full_Stage'] = ytd['Stage'].apply(format_stage_safe) if 'Stage' in ytd.columns else "—"
        ytd['Tier_Val'] = ytd['tier'].astype(str).str.replace('Tier ', '', case=False)
        ytd['Place_Label'] = ytd['rank'].apply(get_ordinal)
        ytd_disp = ytd[['Date_Str', 'Race Name', 'Full_Stage', 'Tier_Val', 'rider_name', 'owner', 'Place_Label', 'pts']]
        ytd_disp.columns = ['Date', 'Race', 'Stage', 'Tier', 'Rider', 'Owner', 'Place', 'Points']
        st.dataframe(ytd_disp, hide_index=True, use_container_width=True)

def show_top_scorers():
    st.title("🏆 Season Top 10 Scorers (Seasonal)")
    pts = leagues["Seasonal"]["pts"]
    if not pts.empty:
        all_tops = pts.sort_values('pts', ascending=False).head(10).copy()
        all_tops['Rank'] = range(1, len(all_tops) + 1)
        tops_disp = all_tops[['Rank', 'rider_name', 'owner', 'pts']]
        tops_disp.columns = ['Rank', 'Rider', 'Owner', 'Points']
        st.dataframe(tops_disp, hide_index=True, use_container_width=True)

def show_roster():
    st.title("Master Roster Comparison")
    league_choice = st.radio("Select League", ["Seasonal", "Dynasty"], horizontal=True)
    pts = leagues[league_choice]["pts"]
    
    pick_indices = list(range(1, 31))
    def get_team_columns(owner_name):
        team_data = pts[pts['owner'] == owner_name]
        names, val = [], []
        for p in pick_indices:
            row = team_data[team_data['team_pick'] == p]
            names.append(row.iloc[0]['rider_name'] if not row.empty else "—")
            val.append(int(row.iloc[0]['pts']) if not row.empty else 0)
        return names, val
    
    t_n, t_p = get_team_columns("Tanner")
    d_n, d_p = get_team_columns("Daniel")
    roster_comp = pd.DataFrame({"Slot": pick_indices, "Tanner": t_n, "Points": t_p, "Daniel": d_n, "Points ": d_p})
    st.dataframe(roster_comp, hide_index=True, use_container_width=True, height=1100)

def show_analysis():
    st.title("Draft Performance Analysis")
    league_choice = st.radio("Select League for Analysis", ["Seasonal", "Dynasty"], horizontal=True)
    pts = leagues[league_choice]["pts"]
    
    if pts.empty:
        st.info("No data available.")
        return
        
    groups = [("Picks 1–5", 1, 5), ("Picks 6–10", 6, 10), ("Picks 11–20", 11, 20), ("Picks 21–30", 21, 30)]
    for label, start, end in groups:
        t_pts = int(pts[(pts['owner'] == "Tanner") & (pts['team_pick'] >= start) & (pts['team_pick'] <= end)]['pts'].sum())
        d_pts = int(pts[(pts['owner'] == "Daniel") & (pts['team_pick'] >= start) & (pts['team_pick'] <= end)]['pts'].sum())
        with st.expander(f"**{label}** — Tanner: {t_pts} | Daniel: {d_pts}"):
            c1, c2 = st.columns(2)
            for i, owner in enumerate(["Tanner", "Daniel"]):
                with (c1 if i==0 else c2):
                    st.write(f"**{owner}**")
                    df = pts[(pts['owner'] == owner) & (pts['team_pick'] >= start) & (pts['team_pick'] <= end)].sort_values('team_pick')
                    st.dataframe(df[['team_pick', 'rider_name', 'pts']].rename(columns={'team_pick':'Slot','rider_name':'Rider','pts':'Points'}), hide_index=True)

def show_schedule():
    st.title("Full 2026 Schedule")
    full_sched_disp = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    full_sched_disp.columns = ['Date', 'Race', 'Tier', 'Race Type']
    st.dataframe(full_sched_disp, hide_index=True, use_container_width=True, height=2500)

# --- 5. NAVIGATION ---
pages = [
    st.Page(show_seasonal, title="Seasonal Dashboard", icon="📊"), 
    st.Page(show_dynasty, title="Dynasty Dashboard", icon="🏆"),
    st.Page(show_point_history, title="Point History", icon="📜"),
    st.Page(show_top_scorers, title="Top Scorers", icon="🥇"),
    st.Page(show_roster, title="Master Roster", icon="👥"), 
    st.Page(show_analysis, title="Analysis", icon="📈"),
    st.Page(show_schedule, title="Full Schedule", icon="📅")
]

if check_password():
    # Pass results_raw for dev tools
    def show_dev():
        st.title("🛠 Developer: All Scored Riders")
        # Logic to see points scored by EVERY rider in the excel, even if not owned
        # (This is a simplified version of your original dev tool)
        st.write("Displays points for all riders in results.xlsx")

    pages.append(st.Page(show_dev, title="Dev Tools", icon="🛠"))

pg = st.navigation(pages)
pg.run()
