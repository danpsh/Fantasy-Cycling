import streamlit as st

import pandas as pd

import plotly.express as px



# --- 1. SETTINGS & SCORING ---

# layout="wide" is critical here to ensure columns stay side-by-side

st.set_page_config(page_title="Fantasy Cycling", layout="wide", initial_sidebar_state="collapsed")



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



# --- 3. NAVIGATION LOGIC ---

if 'page' not in st.session_state:

    st.session_state.page = "Dashboard"



def set_page(page_name):

    st.session_state.page = page_name



with st.sidebar:

    st.title("Navigation")

    st.button("Dashboard", use_container_width=True, on_click=set_page, args=("Dashboard",))

    st.button("Team Rosters", use_container_width=True, on_click=set_page, args=("Team Rosters",))



page = st.session_state.page



if results_raw is not None:

    # --- 4. DATA PROCESSING ---

    riders_df['match_name'] = riders_df['rider_name'].str.split('-').str[0].str.strip().str.lower()

    results_raw['Race_Num'] = range(1, len(results_raw) + 1)

    results_raw['Date'] = pd.to_datetime(results_raw['Date'])



    df_long = results_raw.melt(id_vars=['Date', 'Race Name', 'Stage', 'Race_Num'], var_name='Pos', value_name='rider_name')

    df_long['match_name'] = df_long['rider_name'].astype(str).str.strip().str.lower()

    df_long['rank'] = df_long.groupby(['Race_Num']).cumcount() + 1

    

    processed = df_long.merge(riders_df, on='match_name', how='inner')

    processed = processed.merge(schedule_df, left_on='Race Name', right_on='race_name')

    processed['pts'] = processed.apply(lambda r: SCORING.get(r['tier'], {}).get(r['rank'], 0), axis=1)

    leaderboard = processed.groupby('owner')['pts'].sum().sort_values(ascending=False).reset_index()



    # --- 5. PAGE 1: DASHBOARD ---

    if page == "Dashboard":

        st.title("Fantasy Cycling")

        h1, h2 = st.columns(2)

        for i, owner in enumerate(leaderboard['owner']):

            points = leaderboard[leaderboard['owner'] == owner]['pts'].values[0]

            with (h1 if i == 0 else h2):

                st.subheader(f"{owner}: {points} pts")

        st.write("---")

        st.subheader("Top Scorers")

        m1, m2 = st.columns(2)

        for i, owner in enumerate(leaderboard['owner']):

            owner_data = processed[processed['owner'] == owner]

            if not owner_data.empty:

                top_3 = owner_data.groupby('rider_name_x')['pts'].sum().sort_values(ascending=False).head(3).reset_index()

                with (m1 if i == 0 else m2):

                    st.write(f"**Team {owner}**")

                    for _, row in top_3.iterrows():

                        st.write(f"- {row['rider_name_x']}: {row['pts']} pts")

        

        tab1, tab2, tab3 = st.tabs(["Standings Graph", "Rider Leaderboard", "Full History"])

        with tab1:

            chart_data = processed.groupby(['Race_Num', 'owner'])['pts'].sum().reset_index()

            chart_data['Total Points'] = chart_data.groupby('owner')['pts'].cumsum()

            race_info = results_raw[['Race_Num', 'Race Name', 'Stage']]

            chart_data = chart_data.merge(race_info, on='Race_Num')

            fig = px.line(chart_data, x="Race_Num", y="Total Points", color="owner", markers=True,

                         hover_data={'Race Name': True, 'Stage': True, 'Total Points': True})

            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        with tab2:

            rider_pts = processed.groupby(['rider_name_x', 'owner'])['pts'].sum().sort_values(ascending=False).reset_index()

            st.dataframe(rider_pts.rename(columns={'rider_name_x': 'Rider', 'owner': 'Team Owner', 'pts': 'Season Total'}), use_container_width=True, hide_index=True)

        with tab3:

            history_view = processed.sort_values(by=['Date', 'Race_Num'], ascending=True)

            history_view['Formatted Date'] = history_view['Date'].dt.strftime('%b %d, %Y')

            history_view = history_view[['Formatted Date', 'Race Name', 'Stage', 'rider_name_x', 'owner', 'pts']]

            history_view.columns = ['Race Date', 'Event Name', 'Stage/Race', 'Scoring Rider', 'Team Owner', 'Points Earned']

            st.dataframe(history_view, use_container_width=True, hide_index=True)



    # --- 6. PAGE 2: TEAM ROSTERS (FORCED DUAL COLUMN) ---

    elif page == "Team Rosters":

        st.title("Team Rosters")

        

        # We define a 2-column layout for the whole page

        col1, col2 = st.columns(2)

        

        # Get unique owners

        owners = sorted(riders_df['owner'].unique())

        

        # Assign each owner to a specific column

        for i, owner in enumerate(owners):

            with (col1 if i == 0 else col2):

                st.header(f"Team {owner}")

                # Filter riders for this owner

                team_data = riders_df[riders_df['owner'] == owner][['rider_name']].reset_index(drop=True)

                team_data.index = team_data.index + 1

                # st.table forces a clean, static side-by-side view

                st.table(team_data.rename(columns={'rider_name': 'Drafted Rider'}))
