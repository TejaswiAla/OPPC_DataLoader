import streamlit as st
import pandas as pd
import data_loader_2_sf_helper
import data_loader_3_monthly_metrics

def process_metrics_data():
    if 'list_data' in st.session_state and st.session_state['list_data'] and len(st.session_state['list_data'])>0:
        import data_loader_2_sf_helper
        
        data_loader_2_sf_helper.get_sf_access_token()
        list_sf_all_partners = data_loader_2_sf_helper.get_sf_list_partners(st.session_state['list_data'])
        list_sf_all_account_teams = data_loader_2_sf_helper.get_sf_account_teams(
            st.session_state['list_data'],
            list_sf_all_partners
        )
        data_loader_3_monthly_metrics.upsert_monthly_metrics(
            st.session_state['list_data'],
            list_sf_all_partners,
            list_sf_all_account_teams
        )

    