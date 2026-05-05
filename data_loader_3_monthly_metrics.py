import streamlit as st
import pandas as pd
import requests
import json
from io import StringIO
import time

import data_loader_2_sf_helper


def build_monthly_metrics_upsert_data(list_xls_data, list_sf_all_partners, list_sf_all_account_teams):
    list_monthly_metrics_upsert_data = []

    map_account_name_to_account_ids = st.session_state.get('map_sf_ids')
    if not map_account_name_to_account_ids:
        map_account_name_to_account_ids = data_loader_2_sf_helper.map_sf_ids(list_sf_all_partners)
        st.session_state['map_sf_ids'] = map_account_name_to_account_ids

    # build map of (account_id, team_name) -> set of team_ids from sf account team records
    map_account_team_pair_to_team_ids = {}
    for sf_account_team in (list_sf_all_account_teams or []):
        if not isinstance(sf_account_team, dict):
            continue

        account_id = sf_account_team.get('Account__c')
        team_name = sf_account_team.get('Team_Name__c')
        team_id = sf_account_team.get('Id')

        if account_id is None or team_name is None or team_id is None:
            continue

        key = (account_id, team_name)
        if key not in map_account_team_pair_to_team_ids:
            map_account_team_pair_to_team_ids[key] = set()
        map_account_team_pair_to_team_ids[key].add(team_id)

    # aggregate drug spend directly by sf ids - avoids re-mapping after aggregation
    agg_data_by_sf_ids = data_loader_2_sf_helper.aggregate_data_by_sf_ids(
        list_xls_data,
        map_account_name_to_account_ids,
        map_account_team_pair_to_team_ids
    )
    print(f"agg_data_by_sf_ids = {len(agg_data_by_sf_ids)}")

    if agg_data_by_sf_ids and len(agg_data_by_sf_ids)>0:
        for (account_id, team_id, year, month), drug_spend in agg_data_by_sf_ids.items():
            if team_id:
                list_monthly_metrics_upsert_data.append({
                    'External_ID__c': f"{account_id}_{team_id}_{year}_{month}",
                    'Partner__c': account_id,
                    'Team__c': team_id,
                    'Year__c': str(year),
                    'Month__c': str(month),
                    'Drug_Spend__c': float(drug_spend)
                })
            else:
                list_monthly_metrics_upsert_data.append({
                    'External_ID__c': f"{account_id}_{year}_{month}",
                    'Partner__c': account_id,
                    'Year__c': str(year),
                    'Month__c': str(month),
                    'Drug_Spend__c': float(drug_spend)
                })

    print(f"list_monthly_metrics_upsert_data = {len(list_monthly_metrics_upsert_data)}")
    return list_monthly_metrics_upsert_data


def upsert_monthly_metrics(list_xls_data, list_sf_all_partners, list_sf_all_account_teams):
    list_monthly_metrics_upsert_data = st.session_state.get('list_monthly_metrics_upsert_data')

    if not list_monthly_metrics_upsert_data:
        list_monthly_metrics_upsert_data = build_monthly_metrics_upsert_data(
            list_xls_data, list_sf_all_partners, list_sf_all_account_teams
        )
        st.session_state['list_monthly_metrics_upsert_data'] = list_monthly_metrics_upsert_data

    print(f"list_monthly_metrics_upsert_data count = {len(list_monthly_metrics_upsert_data)}")

    if list_monthly_metrics_upsert_data and len(list_monthly_metrics_upsert_data) > 0:
        st.info(f"⏳ Upserting {len(list_monthly_metrics_upsert_data)} Monthly Metrics record(s) to Salesforce....")
        data_loader_2_sf_helper.perform_dml_operation(
            'upsert',
            'Monthly_metrics__c',
            list_monthly_metrics_upsert_data,
            {'externalIdFieldName': 'External_ID__c'}
        )
    else:
        st.warning("⚠️ No Monthly Metrics records to upsert.")

    return None
