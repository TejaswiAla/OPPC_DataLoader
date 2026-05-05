import streamlit as st
import requests
#from simple_salesforce import Salesforce
#from util import params
from auth.util import params
import toml
import json

version_number = '62.0'
def get_sf_instance():
    params = st.query_params.to_dict()
    st.session_state['prod'] = params.get('prod')
    st.session_state['session_id'] = params.get('session_id')
    st.session_state['username'] = params.get('username')
    st.session_state['record_id'] = params.get('recordId')
    
    return_results = verify_user()
    if return_results and 'urls' in return_results and 'custom_domain' in return_results['urls'] and return_results['urls']['custom_domain'] and return_results['urls']['custom_domain']!='':
        st.session_state['sf_instance_url'] = return_results['urls']['custom_domain']
    return None


def verify_user():
    headers = {
            "Authorization":"Bearer {}".format(st.session_state['session_id']),
            "Content-Type": "application/json"
    }

    try:
        if st.session_state['prod'] == '0':
            results = requests.get('https://test.salesforce.com/services/oauth2/userinfo', headers=headers)
        else:
            # print(st.session_state['prod'])
            results = requests.get('https://login.salesforce.com/services/oauth2/userinfo', headers=headers)
        #print(results.status_code)
        if results.status_code == 200:
            if st.session_state['username'] == results.json()['preferred_username']:
                return results.json()
            else:
                print("Failed: Invalid Username {} - {}".format(st.session_state['username'], results.json()['preferred_username'] ))
                return None
        else:
            print("Failed: Invalid Session ID")
            st.markdown("<h1 style='text-align: center;'>🔒 Secure Access</h1>",unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>User not verified</h3>", unsafe_allow_html=True)
            st.stop()
            return None
    except Exception as exc:
        st.markdown("<h1 style='text-align: center;'>🔒 Secure Access</h1>",unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>User not verified</h3>", unsafe_allow_html=True)
        st.stop()

def get_sf_rest_base() -> str:
    inst = st.session_state.get('sf_instance_url')
    if inst:
        return f"{inst}/services/data/v{version_number}/"
    try:
        cfg = toml.load('./.solomo/connections.toml')
        # Decide env based on session 'prod' flag; default to UAT if not truthy
        prod_flag = st.session_state.get('prod')
        use_prod = False
        if isinstance(prod_flag, bool):
            use_prod = prod_flag
        elif isinstance(prod_flag, str):
            use_prod = prod_flag not in ('0', 'false', 'False', '')
        else:
            use_prod = bool(prod_flag)

        section = (cfg.get('salesforce_prod') if use_prod else None) or cfg.get('salesforce_uat')
        if section:
            domain = section.get('DOMAIN') or section.get('domain')
            if domain:
                if domain.startswith('http'):
                    return f"{domain}/services/data/v{version_number}/"
                return f"https://{domain}/services/data/v{version_number}/"
            # Fallback to standard login/test domains when DOMAIN not provided
            sb = section.get('SANDBOX')
            if sb is None:
                sb = section.get('sandbox')
            base = 'https://test.salesforce.com' if (sb is True) else 'https://login.salesforce.com'
            return f"{base}/services/data/v{version_number}/"
    except Exception:
        pass

    userinfo = st.session_state.get('sf_userinfo')
    if userinfo and 'urls' in userinfo and 'rest' in userinfo['urls']:
        return userinfo['urls']['rest'].replace('{version}', version_number)
    return f'https://test.salesforce.com/services/data/v{version_number}/'

def get_sf_access_token() -> str:
    cfg = toml.load('./.solomo/secrets.toml')
    # Choose correct section based on prod flag; default to UAT
    prod_flag = st.session_state.get('prod')
    use_prod = False
    if isinstance(prod_flag, bool):
        use_prod = prod_flag
    elif isinstance(prod_flag, str):
        use_prod = prod_flag not in ('0', 'false', 'False', '')
    else:
        use_prod = bool(prod_flag)

    section = (cfg.get('salesforce_prod') if use_prod else None) or cfg.get('salesforce_dev') or {}
    client_id = section.get('CLIENT_ID')
    client_secret = section.get('CLIENT_SECRET')
    token_url = section.get('TOKEN_URL')
    if not token_url:
        sb = section.get('SANDBOX')
        if sb is None:
            sb = section.get('sandbox')
        token_url = 'https://test.salesforce.com/services/oauth2/token' if (sb is True) else 'https://login.salesforce.com/services/oauth2/token'
    if not (client_id and client_secret):
        raise Exception('Missing CLIENT_ID/CLIENT_SECRET')
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    resp = requests.post(token_url, data=data, headers=headers)
    if resp.status_code not in (200, 201):
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        raise Exception(f'Token request failed: {resp.status_code} {err}')
    token_payload = resp.json()
    if 'instance_url' in token_payload:
        st.session_state['sf_instance_url'] = token_payload['instance_url']
    return token_payload.get('access_token')