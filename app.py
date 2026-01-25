import streamlit as st
import pandas as pd
import unicodedata
import plotly.express as px

# --- 1. SETTINGS & SCORING ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide")

# Scoring logic (Remains the same)
SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return " ".join(sorted(name.lower().replace('-', ' ').split()))

# --- 2. UI & DATA LOADING ---
st.title("🏆 2026 Fantasy Cycling Leaderboard")

# Side panel for uploads
with st.sidebar:
    st.header("Data Upload")
    uploaded_file = st.file_uploader("Upload 'results.xlsx'", type=["xlsx"])
    st.info("Ensure your Excel has columns: 'rider_name', 'rank', and 'tier'")

# Load your local rider list from GitHub automatically
try:
    riders_df = pd.read_csv('riders.csv')
    riders_df['match_name'] = riders_df['rider_name'].apply(normalize)
except:
    st.error("Riders.csv missing from GitHub!")
    st.stop()

if uploaded_file:
    # Read the uploaded Excel file
    results_df = pd.read_excel(uploaded_file, engine='openpyxl')
    
    # Process Points
    results_df['match_name'] = results_df['rider_name'].apply(normalize)
    
    # Merge with owners
    merged = results_df.merge(riders_df, on='match_name', how='inner')
    
    # Calculate Points based on Rank and Tier
    def calc_pts(row):
        try:
            rank = int(row['rank'])
            return SCORING.get(row['tier'], {}).get(rank, 0)
        except:
            return 0

    merged['pts'] = merged.apply(calc_pts, axis=1)

    # --- 3. DISPLAY ---
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Current Standings")
        standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
        st.table(standings)

    with col2:
        st.subheader("Points Visualization")
        fig = px.bar(standings, x='owner', y='pts', color='owner', text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Detailed Points Breakdown")
    st.dataframe(merged[['rider_name_x', 'owner', 'rank', 'tier', 'pts']], use_container_width=True)

else:
    st.warning("Please upload your 'results.xlsx' file in the sidebar to see the leaderboard.")
