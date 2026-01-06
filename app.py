import streamlit as st
import pandas as pd
from io import BytesIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Fantasy Cycling League", layout="wide")

# Define your Scoring Tiers
# Tier 1 (Grand Tours), Tier 2 (Classics), Tier 3 (Week-long)
SCORING_SYSTEM = {
    "Tier 1": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1],
    "Tier 2": [15, 12, 10, 8, 6, 5, 4, 3, 2, 1],
    "Tier 3": [10, 8, 6, 5, 4, 3, 2, 1, 0, 0]
}

st.title("🚴‍♂️ Fantasy Cycling League Manager")

# --- DATA LOADING ---
# In a real "vibe," we'd upload these or link them from GitHub
try:
    results_df = pd.read_csv("results.csv")
except:
    # Create empty starter data if file doesn't exist
    results_df = pd.DataFrame(columns=["Race", "Stage", "Tier", "Rider", "Rank"])

# --- SIDEBAR: Input New Results ---
with st.sidebar:
    st.header("Add Stage Results")
    race_name = st.text_input("Race Name")
    stage_num = st.number_input("Stage #", min_value=1)
    tier = st.selectbox("Race Tier", ["Tier 1", "Tier 2", "Tier 3"])
    
    st.write("Enter Top 10 Riders (Comma Separated):")
    riders_input = st.text_area("1st through 10th", "Rider A, Rider B, Rider C...")

    if st.button("Save Results"):
        rider_list = [r.strip() for r in riders_input.split(",")]
        new_data = []
        for i, rider in enumerate(rider_list[:10]):
            points = SCORING_SYSTEM[tier][i]
            new_data.append([race_name, stage_num, tier, rider, i+1, points])
        
        # Add to our database
        new_df = pd.DataFrame(new_data, columns=["Race", "Stage", "Tier", "Rider", "Rank", "Points"])
        results_df = pd.concat([results_df, new_df], ignore_index=True)
        results_df.to_csv("results.csv", index=False)
        st.success("Results Updated!")

# --- MAIN DISPLAY ---
st.subheader("Current Standings")
st.dataframe(results_df, use_container_width=True)

# --- EXCEL EXPORT ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='FantasyStats')
    return output.getvalue()

st.download_button(
    label="📥 Export to Excel",
    data=to_excel(results_df),
    file_name="fantasy_cycling_export.xlsx",
    mime="application/vnd.ms-excel"
)