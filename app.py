import streamlit as st
import pandas as pd

# --- 1. CONFIGURATION & SCORING ---
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
        results_raw = pd.read_excel('results.xlsx')
        return riders, schedule, results_raw
    except Exception as e:
        st.error(f"⚠️ File Loading Error: {e}")
        return None, None, None

riders_df, schedule_df, results_raw = load_data()

if results_raw is not None:
    # --- 3. TRANSFORM DATA ---
    df_long = results_raw.melt(
        id_vars=['Race Name', 'Stage'], 
        var_name='Position_Label', 
        value_name='rider_name'
    )
    
    # CRITICAL: Clean up names (removes hidden spaces)
    df_long['rider_name'] = df_long['rider_name'].astype(str).str.strip()
    riders_df['rider_name'] = riders_df['rider_name'].astype(str).str.strip()
    
    # Assign ranks 1-10
    df_long['rank'] = df_long.groupby(['Race Name', 'Stage']).cumcount() + 1
    
    # --- 4. MERGING (The Crash Point) ---
    # Merge with riders to get Owners
    processed = df_long.merge(riders_df, on='rider_name', how='inner')
    
    # Merge with schedule to get Tiers
    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')

    # --- CHECKPOINT: Is the table empty? ---
    if processed.empty:
        st.warning("⚠️ No drafted riders found in the results!")
        st.info("Check if the rider names in your Excel match your riders.csv exactly.")
        st.write("Names detected in your Excel:", df_long['rider_name'].unique())
    else:
        # 5. CALCULATE POINTS
        def get_points(row):
            return SCORING.get(row['tier'], {}).get(row['rank'], 0)
        
        processed['points_earned'] = processed.apply(get_points, axis=1)

        # --- 6. DASHBOARD UI ---
        st.title("🚴 2026 Cycling Draft: Daniel vs Tanner")
        
        # Leaderboard
        leaderboard = processed.groupby('owner')['points_earned'].sum().sort_values(ascending=False).reset_index()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label=f"🥇 {leaderboard.iloc[0]['owner']}", value=f"{leaderboard.iloc[0]['points_earned']} pts")
        with col2:
            if len(leaderboard) > 1:
                gap = int(leaderboard.iloc[1]['points_earned'] - leaderboard.iloc[0]['points_earned'])
                st.metric(label=f"🥈 {leaderboard.iloc[1]['owner']}", value=f"{leaderboard.iloc[1]['points_earned']} pts", delta=gap)

        st.divider()
        st.subheader("Race Breakdown")
        st.dataframe(processed[['Race Name', 'Stage', 'rider_name', 'owner', 'points_earned']], use_container_width=True, hide_index=True)
