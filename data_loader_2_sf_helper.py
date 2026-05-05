import streamlit as st
import pandas as pd
import requests
import json
from io import StringIO
import time
from data_loader_4_mapper import map_xls_data_to_acc_data

import auth.salesforce_oauth as sf_auth


def get_sf_access_token():
    sf_access_token = sf_auth.get_sf_access_token()
    print(f"sf_access_token = {sf_access_token}")
    st.session_state['sf_access_token'] = f"{sf_access_token}"
    return None

def get_sf_list_partners(list_xls_data):
    list_sf_all_partners = []
    sf_access_token = sf_auth.get_sf_access_token()
    print(f"sf_access_token = {sf_access_token}")
    st.session_state['sf_access_token'] = f"{sf_access_token}"

    # collect unique customer names from xls to query salesforce for matching partner accounts
    set_xls_all_customer_names = get_set_customer_names(list_xls_data)
    print(f"set_xls_all_customer_names = {len(list(set_xls_all_customer_names))}")
    list_of_list_customer_names = get_list_of_list_for_ids(set_xls_all_customer_names)

    if list_of_list_customer_names and len(list_of_list_customer_names)>0:
        for list_customer_names in list_of_list_customer_names:
            str_list_of_customer_names = get_querable_strs_for_list(list_customer_names)
            if str_list_of_customer_names and str_list_of_customer_names!='':
                query_sf_partners = get_query_sf_partners(str_list_of_customer_names)
                if query_sf_partners and query_sf_partners!='':
                    print(f"\nquery_sf_partners = {query_sf_partners}\n")
                    list_sf_partners = get_sf_records(query_sf_partners)
                    print(f"\nlist_sf_partners = {len(list_sf_partners)}\n")
                    if list_sf_partners and len(list_sf_partners)>0:
                        list_sf_all_partners.extend(list_sf_partners)

    if list_sf_all_partners and len(list_sf_all_partners)>0:
        map_unique_partners = {}
        for partner in list_sf_all_partners:
            if isinstance(partner, dict) and partner.get('Id'):
                map_unique_partners[partner['Id']] = partner
        list_sf_all_partners = list(map_unique_partners.values())

    account_name_to_account_ids = map_sf_ids(list_sf_all_partners)
    st.session_state['map_sf_ids'] = account_name_to_account_ids

    print(f"\nlist_sf_all_partners = {len(list_sf_all_partners)}")
    return list_sf_all_partners

def map_sf_ids(list_sf_all_partners):
    map_account_name_to_account_ids = {}
    for partner in (list_sf_all_partners or []):
        if not isinstance(partner, dict):
            continue

        account_id = partner.get('Id')
        account_name = partner.get('Name')
        if account_id is None or account_name is None:
            continue

        map_account_name_to_account_ids.setdefault(account_name, set()).add(account_id)
    return map_account_name_to_account_ids

def get_set_customer_names(list_xls_data):
    # extracts unique customer names using mapping for column names
    set_xls_all_customer_names = set()
    for row in (list_xls_data or []):
        if not isinstance(row, dict):
            continue
        mapped_row = map_xls_data_to_acc_data(row, {})
        customer_name = mapped_row.get('customer_name')
        if customer_name is None:
            continue
        set_xls_all_customer_names.add(customer_name)
    return set_xls_all_customer_names

def aggregate_data_by_sf_ids(list_xls_data, map_account_name_to_account_ids, map_account_team_pair_to_team_ids):
    
    agg_data_by_sf_ids = {}

    for row in (list_xls_data or []):
        if not isinstance(row, dict):
            continue
        mapped_row = map_xls_data_to_acc_data(row, {})
        customer_name = mapped_row.get('customer_name')
        team_name = mapped_row.get('team_name')
        dispense_date = mapped_row.get('dispense_date')
        drug_spend = mapped_row.get('drug_spend')

        if customer_name is None or dispense_date is None:
            continue

        # Normalize team name: treat None, NaN, blank, or 'unknown' as no team
        normalized_team_name = str(team_name).strip() if team_name is not None and not pd.isna(team_name) else ''
        if not normalized_team_name or normalized_team_name.casefold() == 'unknown':
            normalized_team_name = None

        parsed_dispense_date = pd.to_datetime(dispense_date, errors='coerce')
        if pd.isna(parsed_dispense_date):
            continue

        parsed_drug_spend = pd.to_numeric(drug_spend, errors='coerce')
        if pd.isna(parsed_drug_spend):
            continue

        set_account_ids = map_account_name_to_account_ids.get(customer_name)
        if not set_account_ids:
            continue

        dispense_year = str(parsed_dispense_date.year)
        dispense_month = parsed_dispense_date.strftime('%B')

        for account_id in set_account_ids:
            if normalized_team_name is not None:
                set_team_ids = map_account_team_pair_to_team_ids.get((account_id, normalized_team_name))
                if set_team_ids and len(set_team_ids) > 0:
                    for team_id in set_team_ids:
                        key = (account_id, team_id, dispense_year, dispense_month)
                        agg_data_by_sf_ids[key] = agg_data_by_sf_ids.get(key, 0) + float(parsed_drug_spend)
                else:
                    # Team name provided but not found in SF, treat as account-level
                    key = (account_id, None, dispense_year, dispense_month)
                    agg_data_by_sf_ids[key] = agg_data_by_sf_ids.get(key, 0) + float(parsed_drug_spend)
            else:
                # Team is unknown/blank, always aggregate as account-level
                key = (account_id, None, dispense_year, dispense_month)
                agg_data_by_sf_ids[key] = agg_data_by_sf_ids.get(key, 0) + float(parsed_drug_spend)

    return agg_data_by_sf_ids

def get_sf_account_teams(list_xls_data, list_sf_all_partners):
    list_sf_all_account_teams = []

    # map account names to account ids from the list of all sf partners
    map_account_name_to_account_ids = st.session_state.get('map_sf_ids')
    if not map_account_name_to_account_ids:
        map_account_name_to_account_ids = map_sf_ids(list_sf_all_partners)
        st.session_state['map_sf_ids'] = map_account_name_to_account_ids

    # map unique partner and team name pairs to avoid duplicate queries to salesforce
    set_partner_team_pairs = set()
    if list_xls_data and len(list_xls_data)>0:
        for row in list_xls_data:
            if not isinstance(row, dict):
                continue
            mapped_row = map_xls_data_to_acc_data(row, {})
            customer_name = mapped_row.get('customer_name')
            team_name = mapped_row.get('team_name')
            if customer_name is None or team_name is None:
                continue
            if pd.isna(team_name) or str(team_name).strip().casefold() == 'unknown':
                continue
            set_account_ids_for_customer = map_account_name_to_account_ids.get(customer_name)
            if not set_account_ids_for_customer:
                continue
            for account_id in set_account_ids_for_customer:
                set_partner_team_pairs.add((account_id, team_name))

    print(f"set_partner_team_pairs = {len(list(set_partner_team_pairs))}")

    # batch the partner and team name pairs to avoid hitting url length limits for salesforce queries and also to optimize the number of queries being made to salesforce
    list_of_list_partner_team_pairs = get_list_of_list_for_ids(set_partner_team_pairs)

    if list_of_list_partner_team_pairs and len(list_of_list_partner_team_pairs)>0:
        for list_partner_team_pairs in list_of_list_partner_team_pairs:
            query_sf_account_teams = get_query_sf_account_teams(list_partner_team_pairs)
            if not query_sf_account_teams or query_sf_account_teams=='':
                continue

            print(f"\nquery_sf_account_teams = {query_sf_account_teams}\n")
            list_sf_account_teams = get_sf_records(query_sf_account_teams)
            print(f"\nlist_sf_account_teams = {len(list_sf_account_teams)}\n")

            if list_sf_account_teams and len(list_sf_account_teams)>0:
                list_sf_all_account_teams.extend(list_sf_account_teams)

    if list_sf_all_account_teams and len(list_sf_all_account_teams)>0:
        map_unique_account_teams = {}
        for sf_account_team in list_sf_all_account_teams:
            if isinstance(sf_account_team, dict) and sf_account_team.get('Id'):
                map_unique_account_teams[sf_account_team['Id']] = sf_account_team
        list_sf_all_account_teams = list(map_unique_account_teams.values())

    print(f"\nlist_sf_all_account_teams = {len(list_sf_all_account_teams)}")
    return list_sf_all_account_teams

def get_sf_record_types():
    map_record_types = {}
    query_sf_record_types = get_query_sf_record_types()
    list_sf_record_types = get_sf_records(query_sf_record_types)
    if list_sf_record_types and len(list_sf_record_types)>0:
        for sf_record_type in list_sf_record_types:
            map_record_types[f"{sf_record_type['SobjectType']}-{sf_record_type['DeveloperName']}"] = sf_record_type['Id']
    return map_record_types

def get_list_of_list_for_ids(set_xls_all_ids):
    list_of_list_of_ids = []
    step_counter = 50

    if set_xls_all_ids and len(list(set_xls_all_ids))>0:
        list_xls_all_ids = list(set_xls_all_ids)
        for start_counter in range(0, len(list_xls_all_ids), step_counter):
            end_counter = start_counter + step_counter
            if end_counter>= len(list_xls_all_ids):
                end_counter = len(list_xls_all_ids)
            list_of_spliced_items = list_xls_all_ids[start_counter:end_counter]
            if list_of_spliced_items and len(list_of_spliced_items)>0:
                list_of_list_of_ids.append(list_of_spliced_items)
    return list_of_list_of_ids

def get_querable_strs_for_list(list_of_items):
    str_list_of_items = ''
    if list_of_items and len(list_of_items)>0:
        str_list_of_items = '('
        for item in list_of_items:
            if isinstance(item,str):
                str_list_of_items = str_list_of_items + f"'{item}',"
            else:
                str_list_of_items = str_list_of_items + f"'{str(item)}',"

    else:
        return '()'

    if str_list_of_items and str_list_of_items!='' and str_list_of_items.endswith(','):
        str_list_of_items = str_list_of_items[:-1]
        str_list_of_items = str_list_of_items + ')'
    return str_list_of_items

def get_query_sf_record_types():
    query = f"""
    Select Id, SobjectType, DeveloperName
    FROM RecordType
    WHERE SobjectType IN ('Account')
    AND isActive=True
    """
    return query

def get_query_sf_partners(str_list_of_customer_names):
    query_sf_partners = ''
    if str_list_of_customer_names and str_list_of_customer_names!='':
        query_sf_partners = f"""
        Select Id,Name
        FROM Account
        WHERE isDeleted=False
        AND Name IN {str_list_of_customer_names} AND RecordType.DeveloperName='Partner'
        """
    return query_sf_partners

def get_query_sf_account_teams(list_partner_team_pairs):
    query_sf_account_teams = ''
    if list_partner_team_pairs and len(list_partner_team_pairs)>0:
        list_pair_filters = []

        for partner_team_pair in list_partner_team_pairs:
            if not isinstance(partner_team_pair, tuple) or len(partner_team_pair) != 2:
                continue

            account_id, team_name = partner_team_pair
            if account_id is None or team_name is None:
                continue

            escaped_account_id = str(account_id).replace("\\", "\\\\").replace("'", "\\'")
            escaped_team_name = str(team_name).replace("\\", "\\\\").replace("'", "\\'")
            list_pair_filters.append(f"(Account__c = '{escaped_account_id}' AND Team_Name__c = '{escaped_team_name}')")

        if list_pair_filters and len(list_pair_filters)>0:
            str_pair_filters = ' OR '.join(list_pair_filters)
            query_sf_account_teams = f"""
            Select Id,Name,Account__c,Team_Name__c
            FROM Account_Team__c
            WHERE {str_pair_filters}
            """
    return query_sf_account_teams

def get_sf_records(query):
    print(f"SESSION TOKEN  = {st.session_state['sf_access_token']}")
    print(f"INSTANCE URL  = {st.session_state['sf_instance_url']}")
    list_sf_recs = []
    try:
        url = f"{st.session_state['sf_instance_url']}/services/data/v64.0/query?"
        url_params = {
            'q':query
        }
        request_headers = {
            'Authorization': f"Bearer {st.session_state['sf_access_token']}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        print(f"request_headers = {request_headers}")
        response = requests.get(url, params=url_params, headers=request_headers)
        print(f"list recs response 1 = {response}")
        print(f"list recs response 2 = {response.json()}")

        if response.status_code == 200:
            if 'records' in response.json() and response.json()['records'] and len(response.json()['records']) > 0:
                list_sf_recs = response.json()['records']
        else:
            st.error(f"❌ Sorry!!! Response status error {response.status_code}. Please contact system administrator.")
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured: {exc}. Please contact system administrator.")
    return list_sf_recs

def perform_dml_operation(operation_type, sobject_api_name, list_data_for_dml, special_additional_params):
    try:
        sf_access_token = st.session_state['sf_access_token']
        sf_instance_url = st.session_state['sf_instance_url']
        csv_data = pd.DataFrame(list_data_for_dml).to_csv(index=False, lineterminator='\n')
        st.info(f"⏳ Data for {operation_type} job is ready.....")

        create_bulkjob_info = create_bulkv2_job(
            sf_access_token,
            sf_instance_url,
            operation_type,
            sobject_api_name,
            special_additional_params
        )
        print(f"create_bulkjob_info = {create_bulkjob_info}")
        if not create_bulkjob_info:
            st.error(f"❌ Unable to create {operation_type} bulk job for {sobject_api_name}.")
            return None

        add_data_to_bulkjob_info = add_data_to_bulk_job(
            sf_access_token,
            sf_instance_url,
            create_bulkjob_info,
            csv_data
        )
        print(f"add_data_to_bulkjob_info = {add_data_to_bulkjob_info}")
        if not add_data_to_bulkjob_info:
            st.error(f"❌ Failed to upload data batches for {operation_type} on {sobject_api_name}.")
            return None
        st.info(f"⏳ Loading data in batches for {operation_type}.....")

        close_bulkjob_info = close_bulk_job(sf_access_token, sf_instance_url, create_bulkjob_info)
        print(f"close_bulkjob_info = {close_bulkjob_info}")
        if not close_bulkjob_info:
            st.error(f"❌ Failed to close bulk job for {operation_type} on {sobject_api_name}.")
            return None

        st.info(f"⏳ Bulk job {operation_type} operation is closed. Waiting for Salesforce processing.....")
        final_job_state = wait_for_bulk_job_completion(
            sf_access_token,
            sf_instance_url,
            create_bulkjob_info,
            operation_type,
            sobject_api_name
        )
        print(f"final_job_state = {final_job_state}")
        finalize_bulk_job_results(
            sf_access_token,
            sf_instance_url,
            create_bulkjob_info,
            final_job_state,
            operation_type,
            sobject_api_name
        )

    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured during {operation_type} on {sobject_api_name}: {exc}. Please contact system administrator.")

    return None

def finalize_bulk_job_results(sf_access_token, sf_instance_url, job_id, final_job_state, operation_type, sobject_api_name):
    if final_job_state in ('Failed', 'Aborted'):
        handle_errors(sf_access_token, sf_instance_url, job_id, sobject_api_name)
        handle_unprocessed_results(sf_access_token, sf_instance_url, job_id, sobject_api_name)
        return None

    if final_job_state != 'JobComplete':
        return None

    failed_results = handle_errors(sf_access_token, sf_instance_url, job_id, sobject_api_name)
    print(f"failed_results = {len(failed_results) if failed_results else 0}")

    if not failed_results:
        st.success(f"✅ {operation_type.capitalize()} completed for {sobject_api_name}.")

    return None

def wait_for_bulk_job_completion(sf_access_token, sf_instance_url, job_id, operation_type, sobject_api_name, timeout_seconds=600, poll_interval_seconds=5):
    start_time = time.time()
    terminal_success_states = {'JobComplete'}
    terminal_error_states = {'Failed', 'Aborted'}

    while time.time() - start_time < timeout_seconds:
        current_state = get_bulk_job_status(sf_access_token, sf_instance_url, job_id)
        print(f"current_state = {current_state}")

        if current_state in terminal_success_states:
            return current_state

        if current_state in terminal_error_states:
            job_info = get_bulk_job_info(sf_access_token, sf_instance_url, job_id)
            state_message = ''
            if job_info and isinstance(job_info, dict):
                state_message = job_info.get('errorMessage') or job_info.get('stateMessage') or ''
                number_records_failed = job_info.get('numberRecordsFailed')
                number_records_processed = job_info.get('numberRecordsProcessed')
                st.error(
                    f"❌ Bulk {operation_type} failed for {sobject_api_name}. "
                    f"Final status: {current_state}. "
                    f"Processed: {number_records_processed}, Failed: {number_records_failed}."
                )
            else:
                st.error(f"❌ Bulk {operation_type} failed for {sobject_api_name}. Final status: {current_state}.")

            if state_message:
                st.error(f"Salesforce message: {state_message}")
            return current_state

        st.info(f"⏳ Current Salesforce bulk job status: {current_state}")
        time.sleep(poll_interval_seconds)

    st.error(f"❌ Timed out waiting for bulk {operation_type} completion for {sobject_api_name}.")
    return None

def create_bulkv2_job(sf_access_token, sf_instance_url, operation_type, sobject_api_name, special_additional_params):
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        payload = {
            'operation': operation_type,
            'object': sobject_api_name,
            'contentType': 'CSV',
            'lineEnding': 'LF'
        }
        if special_additional_params and isinstance(special_additional_params, dict):
            payload.update(special_additional_params)

        response = requests.post(url, headers=request_headers, data=json.dumps(payload))
        print(f"create_bulkv2_job response = {response.status_code} {response.text}")
        if response.status_code in (200, 201):
            return response.json().get('id')
        else:
            st.error(f"❌ Sorry!!! Bulk job to {operation_type} not created. Please contact system administrator.")
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured during bulk job creation {exc}. Please contact system administrator.")
    return None

def add_data_to_bulk_job(sf_access_token, sf_instance_url, job_id, csv_data):
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/{job_id}/batches"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Content-Type': 'text/csv',
            'Accept': 'application/json'
        }
        response = requests.put(url, headers=request_headers, data=csv_data.encode('utf-8'))
        print(f"add_data_to_bulk_job response = {response.status_code} {response.text}")
        return response.status_code in (200, 201, 204)
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured while adding records to bulk job {exc}. Please contact system administrator.")
    return False

def close_bulk_job(sf_access_token, sf_instance_url, job_id):
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/{job_id}"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        payload = {'state': 'UploadComplete'}
        response = requests.patch(url, headers=request_headers, data=json.dumps(payload))
        print(f"close_bulk_job response = {response.status_code} {response.text}")
        return response.status_code in (200, 201, 204)
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured while closing the bulk job {exc}. Please contact system administrator.")
    return False

def get_bulk_job_status(sf_access_token, sf_instance_url, job_id):
    job_info = get_bulk_job_info(sf_access_token, sf_instance_url, job_id)
    if job_info and isinstance(job_info, dict):
        return job_info.get('state')
    return 'Failed'

def get_bulk_job_info(sf_access_token, sf_instance_url, job_id):
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/{job_id}"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=request_headers)
        print(f"get_bulk_job_info response = {response.status_code} {response.text}")
        if response.status_code == 200:
            return response.json()
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured while trying to retrieve job status {exc}. Please contact system administrator.")
    return None

def handle_errors(sf_access_token, sf_instance_url, job_id, sobject_api_name):
    try:
        failed_results = get_failed_results(sf_access_token, sf_instance_url, job_id)
        if failed_results and len(failed_results) > 0:
            st.warning(f"⚠️ {len(failed_results)} record(s) failed during {sobject_api_name} operation.")
            for failed in failed_results[:10]:  # show at most 10
                st.error(f"  sf__Error: {failed.get('sf__Error')} | sf__Id: {failed.get('sf__Id')}")
        return failed_results
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured in handle_errors: {exc}. Please contact system administrator.")
    return []

def handle_unprocessed_results(sf_access_token, sf_instance_url, job_id, sobject_api_name):
    try:
        unprocessed_results = get_unprocessed_results(sf_access_token, sf_instance_url, job_id)
        if unprocessed_results and len(unprocessed_results) > 0:
            st.warning(f"⚠️ {len(unprocessed_results)} record(s) were not processed during {sobject_api_name} operation.")
            for unprocessed in unprocessed_results[:10]:  # show at most 10
                st.error(f"  Unprocessed row: {unprocessed}")
        return unprocessed_results
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured in handle_unprocessed_results: {exc}. Please contact system administrator.")
    return []

def get_failed_results(sf_access_token, sf_instance_url, job_id):
    list_failed = []
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/{job_id}/failedResults/"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Accept': 'text/csv'
        }
        response = requests.get(url, headers=request_headers)
        print(f"get_failed_results response = {response.status_code}")
        if response.status_code == 200 and response.text:
            df_failed = pd.read_csv(StringIO(response.text))
            list_failed = df_failed.to_dict(orient='records')
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured in get_failed_results: {exc}. Please contact system administrator.")
    return list_failed

def get_unprocessed_results(sf_access_token, sf_instance_url, job_id):
    list_unprocessed = []
    try:
        url = f"{sf_instance_url}/services/data/v64.0/jobs/ingest/{job_id}/unprocessedrecords/"
        request_headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Accept': 'text/csv'
        }
        response = requests.get(url, headers=request_headers)
        print(f"get_unprocessed_results response = {response.status_code}")
        if response.status_code == 200 and response.text:
            df_unprocessed = pd.read_csv(StringIO(response.text))
            list_unprocessed = df_unprocessed.to_dict(orient='records')
    except Exception as exc:
        st.error(f"❌ Sorry!!! Exception occured in get_unprocessed_results: {exc}. Please contact system administrator.")
    return list_unprocessed
