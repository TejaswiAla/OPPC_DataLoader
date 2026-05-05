import streamlit as st
import pandas as pd
import time

import auth.salesforce_oauth as sf_auth
import data_loader_1_helper

#sf_auth.get_sf_instance()

if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'list_data' not in st.session_state:
    st.session_state.list_data = None
        

# Building layout
st.set_page_config(layout='wide')

st.set_page_config(
    page_title='Data Loader', 
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded'
)


with st.expander('📁 **Drop Your Excel Here**', expanded=True):
    uploaded_file = st.file_uploader(
        'Choose Excel file', 
        type=['xls', 'xlsx'],
        help='Drag & drop supported! ✨',
        label_visibility='collapsed'
    )

    if uploaded_file is not None:
        st.session_state.file_uploaded = True
        
       
        if "OnePoint Rx Dispense Detail".casefold() in uploaded_file.name.casefold():
                st.session_state['uploaded_file_name'] = 'OnePoint Rx Dispense Detail'
                xls_file = pd.ExcelFile(uploaded_file, engine='openpyxl')
                sheet_name_for_data = ''
                if xls_file.sheet_names and len(xls_file.sheet_names)>0:
                    for sheet_name in xls_file.sheet_names:
                        if 'Rx Dispense Detail'.casefold() in sheet_name.casefold():
                            sheet_name_for_data = sheet_name
                            break
                    if 'Rx Dispense Detail'.casefold() in sheet_name_for_data.casefold():
                        st.success(f"✅ Sheet name check completed!")
                    else:
                        st.error(f"❌ Sorry!!! The sheet name should contain 'Rx Dispense Detail' keyword for OnePoint Rx Dispense Detail file to be processed")

                # st.write(f"sheet_name_for_data = {sheet_name_for_data}")
                df = pd.read_excel(uploaded_file, sheet_name=sheet_name_for_data, engine='openpyxl')
                # Drop the first column => has blank merged cells
                #df = df.iloc[:, 1:]
                df = df.where(pd.notnull(df), None)
                list_data = df.to_dict(orient='records')
                st.session_state.list_data = list_data
                st.success(f"✅ {uploaded_file.name} loaded!")
            
        else:
            st.error(f"❌ Sorry!!! Uploaded file name should contain 'OnePoint Rx Dispense Detail' for it to be processed.")


if 'uploaded_file_name' in st.session_state and st.session_state['uploaded_file_name'] and st.session_state['uploaded_file_name']!='':
    if st.session_state['uploaded_file_name'] == 'OnePoint Rx Dispense Detail':
        #st.write("Column Headers:", df.columns.tolist())
        data_loader_1_helper.process_metrics_data()
    
        
        
            

    






