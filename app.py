import streamlit as st
import pandas as pd

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy Cycling", layout="wide")

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
        st.error(f"⚠️ Error loading files: {e}")
        return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # --- 3. CLEANING & MATCHING LOGIC ---
    # Prepare Draft List: Remove team names/spaces and make lowercase
    riders_df['match_name'] = riders_df['rider_name'].str.split('-').str[0].str.strip().str.lower()
    
    # Pivot Results: Turn "1st", "2nd" columns into one long list of riders
    df_long = results_raw.melt(
        id_vars=['Race Name', 'Stage'], 
        var_name='Position', 
        value_name='rider_name'
    )
    
    # Standardize result names for the cross-reference
    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()
    df_long['rank'] = df_long.groupby(['Race Name', 'Stage']).cumcount() + 1

    # --- 4. THE CROSS-REFERENCE (The Merge) ---
    # This connects your results to your owners
    processed = df_long.merge(riders_df, on='match_name', how='inner')
    
    # This connects the race to its Tier (for points)
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')

    # --- 5. POINT CALCULATION ---
    def calc_points(row):
        tier_scores = SCORING.get(row['tier'], {})
        return tier_scores.get(row['rank'], 0)

    processed['pts'] = processed.apply(calc_points, axis=1)

    # --- 6. DISPLAY DASHBOARD ---
    st.title("🚴 2026 Fantasy Cycling")
    
    # Leaderboard
    st.header("🏆 Leaderboard")
    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label=f"🥇 {leaderboard.iloc[0]['owner']}", value=f"{leaderboard.iloc[0]['pts']} pts")
    with c2:
        if len(leaderboard) > 1:
            diff = int(leaderboard.iloc[1]['pts'] - leaderboard.iloc[0]['pts'])
            st.metric(label=f"🥈 {leaderboard.iloc[1]['owner']}", value=f"{leaderboard.iloc[1]['pts']} pts", delta=diff)

    # Breakdown Table
    st.divider()
    st.subheader("Performance Breakdown")
    st.dataframe(
        processed[['Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']], 
        column_config={"rider_name_x": "Rider"},
        use_container_width=True, 
        hide_index=True
    )


