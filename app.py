import streamlit as st
import pandas as pd

# --- 1. CONFIGURATION & SCORING ---
st.set_page_config(page_title="2026 World Tour Draft", layout="wide")

# Scoring points based on Rank (1-10) and Race Tier
SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    try:
        # Looking directly in the root directory (no data/ folder)
        riders = pd.read_csv('riders.csv')
        schedule = pd.read_csv('schedule.csv')
        results_raw = pd.read_excel('results.xlsx')
        return riders, schedule, results_raw
    except Exception as e:
        st.error(f"⚠️ Error loading files: {e}")
        st.info("Make sure riders.csv, schedule.csv, and results.xlsx are in your main GitHub folder.")
        return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # --- 3. TRANSFORM DATA (Wide to Long) ---
    # Pivot the 1st, 2nd... columns into a vertical list
    df_long = results_raw.melt(
        id_vars=['Race Name', 'Stage'], 
        var_name='Position_Label', 
        value_name='rider_name'
    )
    
    # Clean up names and assign ranks 1-10
    df_long['rider_name'] = df_long['rider_name'].str.strip()
    df_long['rank'] = df_long.groupby(['Race Name', 'Stage']).cumcount() + 1
    
    # --- 4. CALCULATION ENGINE ---
    # Merge to get Owners (from riders) and Tiers (from schedule)
    processed = df_long.merge(riders_df, on='rider_name', how='inner')
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')
    
    # Apply the point system
    def get_points(row):
        return SCORING[row['tier']].get(row['rank'], 0)
    
    processed['points_earned'] = processed.apply(get_points, axis=1)

    # --- 5. DASHBOARD UI ---
    st.title("🚴 2026 Cycling Draft: Daniel vs Tanner")
    
    # Leaderboard Metrics
    st.header("🏆 Current Standings")
    leaderboard = processed.groupby('owner')['points_earned'].sum().sort_values(ascending=False).reset_index()
    
    col1, col2 = st.columns(2)
    with col1:
        name1 = leaderboard.iloc[0]['owner']
        pts1 = leaderboard.iloc[0]['points_earned']
        st.metric(label=f"🥇 {name1}", value=f"{pts1} pts")
    
    with col2:
        if len(leaderboard) > 1:
            name2 = leaderboard.iloc[1]['owner']
            pts2 = leaderboard.iloc[1]['points_earned']
            # delta shows the gap between leader and 2nd place
            st.metric(label=f"🥈 {name2}", value=f"{pts2} pts", delta=int(pts2 - pts1))

    # Detailed Table
    st.divider()
    st.subheader("Individual Result Breakdown")
    st.dataframe(
        processed[['Race Name', 'Stage', 'rider_name', 'owner', 'points_earned']],
        use_container_width=True,
        hide_index=True
    )
