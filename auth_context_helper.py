import streamlit as st
import auth.salesforce_oauth as sf_auth


class AuthContextHelper:
    @staticmethod
    def get_context():
        sf_access_token = sf_auth.get_sf_access_token()
        print(f"sf_access_token = {sf_access_token}")
        st.session_state['sf_access_token'] = f"{sf_access_token}"
        print(f"SESSION TOKEN  = {st.session_state['sf_access_token']}")
        print(f"INSTANCE URL  = {st.session_state['sf_instance_url']}")

        if not sf_access_token or not st.session_state.get('sf_instance_url'):
            st.error("❌ Authentication missing. Please log in to Salesforce.")
            return None

        instance_url = st.session_state['sf_instance_url']
        headers = {
            'Authorization': f"Bearer {sf_access_token}",
            'Content-Type': 'application/json'
        }
        return instance_url, headers