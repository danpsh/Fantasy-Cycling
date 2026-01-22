import streamlit as st
import pandas as pd
import plotly.express as px

# --- DATA LOADING & PROCESSING ---
@st.cache_data
def load_data():
    try:
        r = pd.read_csv('riders.csv')
        s = pd.read_csv('schedule.csv')
        x = pd.read_excel('results.xlsx')
        return r, s, x
    except: return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # 1. Clean Rider Names
    riders_df['match_name'] = riders_df['rider_name'].str.split('-').str[0].str.strip().str.lower()
    
    # 2. Pivot Results and add "Race Number"
    # We sort by the order they appear in your Excel to assign 1, 2, 3...
    results_raw['Race_Num'] = range(1, len(results_raw) + 1)
    
    df_long = results_raw.melt(id_vars=['Race Name', 'Stage', 'Race_Num'], var_name='Pos', value_name='rider_name')
    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()
    df_long['rank'] = df_long.groupby(['Race_Num']).cumcount() + 1

    # 3. Merge & Score
    processed = df_long.merge(riders_df, on='match_name', how='inner')
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')
    
    SCORING = {"Tier 1": {1:30,2:27,3:24,4:21,5:18,6:15,7:12,8:9,9:6,10:3},
               "Tier 2": {1:20,2:18,3:16,4:14,5:12,6:10,7:8,8:6,9:4,10:2},
               "Tier 3": {1:10,2:9,3:8,4:7,5:6,6:5,7:4,8:3,9:2,10:1}}
    
    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)

    # 4. Create Cumulative Chart Data
    # Group by race number so the dots line up 1, 2, 3...
    chart_data = processed.groupby(['Race_Num', 'owner'])['pts'].sum().reset_index()
    chart_data['Total Points'] = chart_data.groupby('owner')['pts'].cumsum()

    # --- UI DISPLAY ---
    st.title("🚴 2026 Cycling Draft")
    
    # Leaderboard Metrics
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    c1, c2 = st.columns(2)
    c1.metric(leaderboard.iloc[0]['owner'], f"{leaderboard.iloc[0]['pts']} pts")
    if len(leaderboard) > 1:
        c2.metric(leaderboard.iloc[1]['owner'], f"{leaderboard.iloc[1]['pts']} pts", 
                  delta=int(leaderboard.iloc[1]['pts'] - leaderboard.iloc[0]['pts']))

    # The Dot Graph
    st.subheader("📈 Season Progress")
    fig = px.line(chart_data, x="Race_Num", y="Total Points", color="owner", markers=True)
    
    # This makes the x-axis show every whole number (1, 2, 3...) without decimals
    fig.update_layout(xaxis=dict(tickmode='linear', tick0=1, dtick=1))
    st.plotly_chart(fig, use_container_width=True)

    # Performance Breakdown
    st.subheader("Rider Totals")
    rider_table = processed.groupby(['rider_name_x', 'owner'])['pts'].sum().sort_values(ascending=False)
    st.dataframe(rider_table, use_container_width=True)
