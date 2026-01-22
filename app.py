import streamlit as st
import pandas as pd

# --- 1. CONFIG & SCORING ---
st.set_page_config(page_title="2026 World Tour Draft", layout="wide")

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
    except Exception as e:
        return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # --- 3. DATA PROCESSING ---
    riders_df['match_name'] = riders_df['rider_name'].str.split('-').str[0].str.strip().str.lower()
    df_long = results_raw.melt(id_vars=['Race Name', 'Stage'], var_name='Pos', value_name='rider_name')
    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()
    df_long['rank'] = df_long.groupby(['Race Name', 'Stage']).cumcount() + 1

    processed = df_long.merge(riders_df, on='match_name', how='inner')
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)

    # --- 4. HEADER METRICS ---
    st.title("🚴 2026 Cycling Draft: Daniel vs Tanner")
    
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    
    m1, m2 = st.columns(2)
    with m1:
        score1 = leaderboard.iloc[0]['pts']
        st.metric(label=f"🏆 LEADER: {leaderboard.iloc[0]['owner']}", value=f"{score1} pts")
    with m2:
        if len(leaderboard) > 1:
            score2 = leaderboard.iloc[1]['pts']
            gap = int(score2 - score1)
            st.metric(label=f"CHALLENGER: {leaderboard.iloc[1]['owner']}", value=f"{score2} pts", delta=gap)

    # --- 5. TABS FOR ORGANIZATION ---
    tab1, tab2, tab3 = st.tabs(["📊 Standings", "🚴 Roster Stats", "📄 Raw Results"])

    with tab1:
        st.subheader("Season Progression")
        # Create cumulative points over time
        processed['Race_Stage'] = processed['Race Name'] + " - " + processed['Stage']
        chart_data = processed.groupby(['Race_Stage', 'owner'])['pts'].sum().groupby(level=1).cumsum().reset_index()
        st.line_chart(chart_data, x="Race_Stage", y="pts", color="owner")

    with tab2:
        st.subheader("Rider Contribution")
        rider_pts = processed.groupby(['rider_name_x', 'owner'])['pts'].sum().sort_values(ascending=False).reset_index()
        st.dataframe(rider_pts, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("All Race Data")
        st.dataframe(processed[['Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']], use_container_width=True)

else:
    st.error("Please ensure your CSV and Excel files are uploaded correctly.")
