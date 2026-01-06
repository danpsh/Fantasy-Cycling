import streamlit as st
import pandas as pd
import os
from io import BytesIO

# --- SCORING CONFIGURATION ---
SCORING_TIERS = {
    "Tier 1": [30, 27, 24, 21, 18, 15, 12, 9, 6, 3],
    "Tier 2": [20, 18, 16, 14, 12, 10, 8, 6, 4, 2],
    "Tier 3": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
}

st.set_page_config(page_title="Cycling League Manager", layout="wide")
st.title("🚴‍♂️ Fantasy Cycling League")

# --- DATA LOADING ---
# Load your schedule
if os.path.exists("races.csv"):
    races_df = pd.read_csv("races.csv")
else:
    st.error("Please upload a races.csv file to your GitHub!")
    st.stop()

# Load/Initialize results
if os.path.exists("results.csv"):
    results_df = pd.read_csv("results.csv")
else:
    results_df = pd.DataFrame(columns=["Race", "Tier", "Stage", "Type", "Rider", "Rank", "Points"])

# --- SIDEBAR: INPUT DATA ---
with st.sidebar:
    st.header("Add New Results")
    
    selected_race = st.selectbox("Select Race", races_df["Race"].unique())
    current_tier = races_df[races_df["Race"] == selected_race]["Tier"].values[0]
    st.info(f"Scoring: {current_tier}")
    
    stage_val = st.number_input("Stage Number", min_value=1, step=1)
    stage_type = st.selectbox("Stage Type", ["Flat", "Hilly", "Mountain", "TT", "One-Day"])
    
    st.write("---")
    st.write("Enter Top 10 Riders:")
    
    temp_riders = []
    for i in range(1, 11):
        name = st.text_input(f"Place {i}", key=f"p{i}")
        temp_riders.append(name)
        
    if st.button("💾 Save to Database"):
        points_scale = SCORING_TIERS[current_tier]
        new_rows = []
        
        for i, rider in enumerate(temp_riders):
            if rider: # Only save if name isn't blank
                new_rows.append({
                    "Race": selected_race,
                    "Tier": current_tier,
                    "Stage": stage_val,
                    "Type": stage_type,
                    "Rider": rider,
                    "Rank": i + 1,
                    "Points": points_scale[i]
                })
        
        # Add to current data and save to CSV
        new_df = pd.DataFrame(new_rows)
        results_df = pd.concat([results_df, new_df], ignore_index=True)
        results_df.to_csv("results.csv", index=False)
        st.success(f"Saved Stage {stage_val} of {selected_race}!")
        st.rerun()

# --- MAIN DISPLAY ---
tab1, tab2, tab3 = st.tabs(["📊 Leaderboard", "📝 Raw Data", "📥 Export"])

with tab1:
    st.subheader("Total Points per Rider")
    if not results_df.empty:
        leaderboard = results_df.groupby("Rider")["Points"].sum().sort_values(ascending=False)
        st.bar_chart(leaderboard)
        st.table(leaderboard)
    else:
        st.info("No data entered yet.")

with tab2:
    st.subheader("All Results")
    st.dataframe(results_df, use_container_width=True)

with tab3:
    st.subheader("Export to Excel")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        results_df.to_excel(writer, index=False, sheet_name='FantasyResults')
    
    st.download_button(
        label="Download Excel File",
        data=output.getvalue(),
        file_name="cycling_league_results.xlsx",
        mime="application/vnd.ms-excel"
    )
