import streamlit as st
import pandas as pd
import unicodedata
import requests
from io import BytesIO

st.set_page_config(page_title="2026 Fantasy League", layout="wide")

# Raw URL for your results.xlsx
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

@st.cache_data(ttl=300)
def load_and_process():
    try:
        # 1. Load Riders
        riders = pd.read_csv('riders.csv')
        riders['match_name'] = riders['rider_name'].apply(normalize)
        
        # 2. Load Wide Results from GitHub
        response = requests.get(GITHUB_RAW_URL)
        wide_df = pd.read_excel(BytesIO(response.content), engine='openpyxl')
        
        # 3. MELT: Convert Wide to Long
        # We keep Date, Race Name, Stage, and Tier as fixed info
        # We turn 1st, 2nd, 3rd... into a 'rank' column
        rank_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
        
        long_df = pd.melt(
            wide_df, 
            id_vars=['Date', 'Race Name', 'Stage', 'Tier'], 
            value_vars=rank_cols,
            var_name='rank_str', 
            value_name='rider_name'
        )
        
        # Convert '1st' -> 1, '2nd' -> 2
        long_df['rank'] = long_df['rank_str'].str.extract('(\d+)').astype(int)
        long_df['match_name'] = long_df['rider_name'].apply(normalize)
        
        return riders, long_df
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None

# --- UI DISPLAY ---
st.title("🏆 2026 Fantasy League")

riders_df, results_df = load_and_process()

if riders_df is not None and results_df is not None:
    # Match riders to owners
    merged = results_df.merge(riders_df, on='match_name', how='inner')
    
    # Apply scoring
    merged['pts'] = merged.apply(lambda r: SCORING.get(r['Tier'], {}).get(r['rank'], 0), axis=1)
    
    standings = merged.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()
    
    st.subheader("Leaderboard")
    st.table(standings)
    
    with st.expander("View individual points scored"):
        st.dataframe(merged[['Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']])
