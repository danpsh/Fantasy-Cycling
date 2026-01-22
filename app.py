import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIG & SCORING ---
st.set_page_config(page_title="Fantasy Cycling", layout="wide")

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    try:
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results = pd.read_excel('results.xlsx')
        return riders, schedule, results
    except: return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # --- 3. PROCESSING ---
    riders_df['match_name'] = riders_df['rider_name'].str.split('-').str[0].str.strip().str.lower()
    results_raw['Race_Num'] = range(1, len(results_raw) + 1)
    
    df_long = results_raw.melt(id_vars=['Race Name', 'Stage', 'Race_Num'], var_name='Pos', value_name='rider_name')
    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()
    df_long['rank'] = df_long.groupby(['Race_Num']).cumcount() + 1

    processed = df_long.merge(riders_df, on='match_name', how='inner')
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)

    # --- 4. HEADER: TITLE & MVP STATS ---
    st.title("🚴 Fantasy Cycling")
    
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    
    # Hero Metrics
    c1, c2 = st.columns(2)
    with c1:
        score1 = leaderboard.iloc[0]['pts']
        st.metric(label=f"🥇 CHAMPION: {leaderboard.iloc[0]['owner']}", value=f"{score1} pts")
    with c2:
        if len(leaderboard) > 1:
            score2 = leaderboard.iloc[1]['pts']
            gap = int(score2 - score1)
            st.metric(label=f"🥈 CHALLENGER: {leaderboard.iloc[1]['owner']}", value=f"{score2} pts", delta=gap)

    # MVP Spotlight
    st.write("---")
    m1, m2 = st.columns(2)
    for i, owner in enumerate(leaderboard['owner']):
        best_rider = processed[processed['owner'] == owner].groupby('rider_name_x')['pts'].sum().idxmax()
        rider_pts = processed[processed['owner'] == owner].groupby('rider_name_x')['pts'].sum().max()
        with (m1 if i == 0 else m2):
            st.write(f"🌟 **{owner}'s MVP:** {best_rider} ({rider_pts} pts)")

    # --- 5. TABS: GRAPH, ROSTERS, HISTORY ---
    tab1, tab2, tab3 = st.tabs(["📊 Standings", "🚴 Roster Stats", "📄 Full History"])

    with tab1:
        chart_data = processed.groupby(['Race_Num', 'owner'])['pts'].sum().reset_index()
        chart_data['Total Points'] = chart_data.groupby('owner')['pts'].cumsum()
        
        # Adding Race info to hover
        race_info = results_raw[['Race_Num', 'Race Name', 'Stage']]
        chart_data = chart_data.merge(race_info, on='Race_Num')

        fig = px.line(chart_data, x="Race_Num", y="Total Points", color="owner", markers=True,
                     hover_data={'Race Name': True, 'Stage': True, 'Total Points': True})
        
        # LOCKING THE GRAPH (No jumping!)
        fig.update_layout(xaxis=dict(fixedrange=True, tickmode='linear', dtick=1), 
                          yaxis=dict(fixedrange=True), dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        st.subheader("Rider Performance")
        rider_pts = processed.groupby(['rider_name_x', 'owner'])['pts'].sum().sort_values(ascending=False).reset_index()
        st.dataframe(rider_pts.rename(columns={'rider_name_x': 'Rider', 'pts': 'Total Points'}), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("All Results")
        st.dataframe(processed[['Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']], use_container_width=True, hide_index=True)
