import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime
import plotly.express as px  # For the stable mobile chart

# --- 1. SETTINGS ---
st.set_page_config(
    page_title="2026 Fantasy Cycling", 
    layout="wide", 
    initial_sidebar_state="auto"
)

# Color mapping for the chart - Tanner (Blue) and Daniel (Red)
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

@st.cache_data(ttl=300)
def load_all_data():
    try:
        riders = pd.read_csv('riders.csv')
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
rider_points_total = pd.DataFrame()
display_order = ["Tanner", "Daniel"]

if all(v is not None for v in [riders_df, schedule_df, results_raw]):
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize_name)
    
    rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
    id_cols = ['Date', 'Race Name']
    if 'Stage' in results_raw.columns:
        id_cols.append('Stage')
        
    df_long = results_raw.melt(id_vars=id_cols, value_vars=rank_cols, var_name='Pos_Label', value_name='result_rider_name')
    df_long['rank'] = df_long['Pos_Label'].str.extract(r'(\d+)').astype(int)
    df_long['match_name'] = df_long['result_rider_name'].apply(normalize_name)
    
    df_long = df_long.merge(schedule_df[['race_name', 'tier']], left_on='Race Name', right_on='race_name', how='left')
    
    processed = df_long.merge(
        riders_df[['match_name', 'owner', 'rider_name', 'team_pick', 'add_date', 'drop_date']], 
        on='match_name', 
        how='inner'
    )
    
    processed = processed[(processed['Date'] >= processed['add_date']) & (processed['Date'] <= processed['drop_date'])].copy()
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)
    
    leaderboard = processed.groupby('owner')['pts'].sum().reset_index()
    if not leaderboard.empty:
        display_order = leaderboard.sort_values('pts', ascending=False)['owner'].tolist()
    
    scored = processed.groupby(['owner', 'rider_name', 'team_pick'])['pts'].sum().reset_index()
    rider_points_total = riders_df[['owner', 'rider_name', 'team_pick']].merge(
        scored, on=['owner', 'rider_name', 'team_pick'], how='left'
    ).fillna(0)

# --- 4. PAGE FUNCTIONS ---

def show_dashboard():
    st.title("2026 Fantasy Cycling")
    m1, m2 = st.columns(2)
    for i, name in enumerate(display_order):
        score = int(leaderboard[leaderboard['owner'] == name]['pts'].sum()) if not leaderboard.empty else 0
        with (m1 if i == 0 else m2):
            st.metric(label=f"{name} Total", value=f"{score} Points")
    st.divider()
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.subheader("Top Scorers")
        for name in display_order:
            st.markdown(f"**{name} Top 5**")
            top5 = rider_points_total[rider_points_total['owner'] == name].nlargest(5, 'pts')[['rider_name', 'pts']]
            if not top5.empty:
                top5.columns = ['Rider', 'Points']
                st.dataframe(top5, hide_index=True, use_container_width=True)
    
    with col_right:
        st.subheader("Season Progress")
        if not processed.empty:
            timeline = processed.groupby(['Date', 'owner'])['pts'].sum().unstack(fill_value=0)
            full_range = pd.date_range(start=timeline.index.min(), end=timeline.index.max())
            chart_data = timeline.reindex(full_range, fill_value=0).cumsum().reset_index()
            chart_data = chart_data.melt(id_vars='index', var_name='Owner', value_name='Points')
            chart_data.rename(columns={'index': 'Date'}, inplace=True)

            fig = px.line(chart_data, x='Date', y='Points', color='Owner', 
                          color_discrete_map=COLOR_MAP, line_shape="hv")
            
            fig.update_layout(
                dragmode=False,
                xaxis=dict(fixedrange=True, title=""),
                yaxis=dict(fixedrange=True, title="Cumulative Points"),
                hovermode="x unified",
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.divider()
    st.subheader("Recent Activity")
    if not processed.empty:
        recent = processed.sort_values(by=['Date', 'Race Name', 'pts'], ascending=[False, True, False]).head(15).copy()
        recent['Date_Str'] = recent['Date'].dt.strftime('%B %d')
        recent['Place_Label'] = recent['rank'].apply(get_ordinal)
        recent_display = recent[['Date_Str', 'Race Name', 'rider_name', 'owner', 'Place_Label', 'pts']]
        recent_display.columns = ['Date', 'Race', 'Rider', 'Owner', 'Place', 'Points']
        st.dataframe(recent_display, hide_index=True, use_container_width=True)

def show_analysis():
    st.title("Draft Performance Analysis")
    
    if rider_points_total.empty:
        st.info("No data available for analysis yet.")
        return

    groups = [
        ("Picks 1–5", 1, 5), ("Picks 6–10", 6, 10), ("Picks 11–15", 11, 15),
        ("Picks 16–20", 16, 20), ("Picks 21–25", 21, 25), ("Picks 26–30", 26, 30),
        ("TOP 10 Total", 1, 10), ("TOP 20 Total", 1, 20),
        ("MIDDLE 10 Total (11–20)", 11, 20), ("BOTTOM 10 Total (21–30)", 21, 30)
    ]

    t_wins, d_wins = 0, 0
    
    for label, start, end in groups:
        t_pts = int(rider_points_total[(rider_points_total['owner'] == "Tanner") & (rider_points_total['team_pick'] >= start) & (rider_points_total['team_pick'] <= end)]['pts'].sum())
        d_pts = int(rider_points_total[(rider_points_total['owner'] == "Daniel") & (rider_points_total['team_pick'] >= start) & (rider_points_total['team_pick'] <= end)]['pts'].sum())
        
        t_check = "✅" if t_pts > d_pts else ""
        d_check = "✅" if d_pts > t_pts else ""
        if t_pts > d_pts: t_wins += 1
        elif d_pts > t_pts: d_wins += 1

        with st.expander(f"**{label}** — Tanner: {t_pts} {t_check} | Daniel: {d_pts} {d_check}"):
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Tanner's Riders**")
                t_df = rider_points_total[(rider_points_total['owner'] == "Tanner") & (rider_points_total['team_pick'] >= start) & (rider_points_total['team_pick'] <= end)].sort_values('team_pick')
                st.dataframe(t_df[['team_pick', 'rider_name', 'pts']].rename(columns={'team_pick':'Slot','rider_name':'Rider','pts':'Points'}), hide_index=True, use_container_width=True)
            with c2:
                st.write("**Daniel's Riders**")
                d_df = rider_points_total[(rider_points_total['owner'] == "Daniel") & (rider_points_total['team_pick'] >= start) & (rider_points_total['team_pick'] <= end)].sort_values('team_pick')
                st.dataframe(d_df[['team_pick', 'rider_name', 'pts']].rename(columns={'team_pick':'Slot','rider_name':'Rider','pts':'Points'}), hide_index=True, use_container_width=True)

    st.sidebar.markdown("---")
    st.sidebar.write("**Segment Wins**")
    st.sidebar.write(f"Tanner: {t_wins}")
    st.sidebar.write(f"Daniel: {d_wins}")

def show_roster():
    st.title("Master Roster")
    st.caption("All 30 draft slots")
    pick_indices = list(range(1, 31))
    def get_team_columns(owner_name):
        team_data = rider_points_total[rider_points_total['owner'] == owner_name]
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
    roster_comp = pd.DataFrame({"Slot": pick_indices, "Tanner": tan_names, "T Pts": tan_pts, "Daniel": dan_names, "D Pts": dan_pts})
    
    # height set to 1100 to remove internal scroll bar for 30 rows
    st.dataframe(roster_comp, hide_index=True, use_container_width=True, height=1100)

def show_point_history():
    st.title("Year-to-Date Point History")
    if not processed.empty:
        ytd = processed.sort_values(by=['Date', 'Race Name', 'pts'], ascending=[False, True, False]).copy()
        ytd['Date_Str'] = ytd['Date'].dt.strftime('%B %d')
        def format_stage(val):
            if pd.isna(val) or val == "": return "—"
            try: return f"Stage {int(float(val))}"
            except: return str(val)
        ytd['Full_Stage'] = ytd['Stage'].apply(format_stage) if 'Stage' in ytd.columns else "—"
        ytd['Tier_Val'] = ytd['tier'].astype(str).str.replace('Tier ', '', case=False)
        ytd['Place_Label'] = ytd['rank'].apply(get_ordinal)
        ytd_disp = ytd[['Date_Str', 'Race Name', 'Full_Stage', 'Tier_Val', 'rider_name', 'owner', 'Place_Label', 'pts']].copy()
        ytd_disp.columns = ['Date', 'Race', 'Stage', 'Tier', 'Rider', 'Owner', 'Place', 'Points']
        st.dataframe(ytd_disp, hide_index=True, use_container_width=True)

def show_top_scorers():
    st.title("🏆 Season Top 10 Scorers")
    if not rider_points_total.empty:
        # Limited to top 10 as requested
        all_tops = rider_points_total.sort_values('pts', ascending=False).head(10).copy()
        all_tops['Rank'] = range(1, len(all_tops) + 1)
        
        tops_disp = all_tops[['Rank', 'rider_name', 'owner', 'pts']]
        tops_disp.columns = ['Rank', 'Rider', 'Owner', 'Points']
        tops_disp['Points'] = tops_disp['Points'].astype(int)
        
        st.dataframe(tops_disp, hide_index=True, use_container_width=True)
    else:
        st.info("No point data available yet.")

def show_schedule():
    st.title("Full 2026 Schedule")
    full_sched_disp = schedule_df[['date', 'race_name', 'tier', 'race_type']].copy()
    full_sched_disp['tier'] = full_sched_disp['tier'].astype(str).str.replace('Tier ', '', case=False)
    full_sched_disp.columns = ['Date', 'Race', 'Tier', 'Race Type']
    st.dataframe(full_sched_disp, hide_index=True, use_container_width=True)

# --- 5. NAVIGATION ---
pg = st.navigation([
    st.Page(show_dashboard, title="Dashboard", icon="📊"), 
    st.Page(show_analysis, title="Analysis", icon="📈"),
    st.Page(show_roster, title="Master Roster", icon="👥"), 
    st.Page(show_point_history, title="Point History", icon="📜"),
    st.Page(show_top_scorers, title="Top Scorers", icon="🏆"),
    st.Page(show_schedule, title="Full Schedule", icon="📅")
])

pg.run()
