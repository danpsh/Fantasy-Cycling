import streamlit as st
import pandas as pd
import unicodedata
import requests
from io import BytesIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="2026 Fantasy League", layout="wide")

# REPLACE THIS URL with your actual GitHub Raw link!
# To get this: Go to your excel file on GitHub -> click "Download" or "View Raw" -> copy that URL
GITHUB_RAW_URL = "https://github.com/YOUR_USERNAME/YOUR_REPO/raw/main/results.xlsx"

SCORING = {
    "Tier 1": {1: 30, 2: 27, 3: 24, 4: 21, 5: 18, 6: 15, 7: 12, 8: 9, 9: 6, 10: 3},
    "Tier 2": {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 8, 8: 6, 9: 4, 10: 2},
    "Tier 3": {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
}

def normalize(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return " ".join(sorted(name.lower().replace('-', ' ').split()))

# --- 2. DATA LOADING ---
@st.cache_data(ttl=600) # Refreshes every 10 minutes
def load_data():
    try:
        # Load Riders from local GitHub folder
        riders = pd.read_csv('riders.csv')
        riders['match_name'] = riders['rider_name'].apply(normalize)
        
        # Load Results from GitHub URL
        response = requests.get(GITHUB_RAW_URL)
        results = pd.read_excel(BytesIO(response.content), engine='openpyxl')
        results['match_name'] = results['rider_name'].apply(normalize)
        
        return riders, results
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return None, None

# --- 3. DISPLAY ---
st.title("🏆 2026 Fantasy League Standings")

riders_df, results_df = load_data()

if riders_df is not None and results_df is not None:
    # Merge and Calculate
    merged = results_df.merge(riders_df, on='match_name', how='inner')
    
    def get_pts(row):
        return SCORING.get(row['tier'], {}).get(int(row['rank']), 0)
    
    merged['pts'] = merged.apply(get_pts, axis=1)

    # Standings Table
    standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Leaderboard")
        st.table(standings.rename(columns={'owner': 'Team', 'pts': 'Total Points'}))
    
    with col2:
        st.subheader("Recent Points")
        st.dataframe(merged[['rider_name_x', 'owner', 'pts']].tail(10), hide_index=True)

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
