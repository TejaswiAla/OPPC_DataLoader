FROM python:3.12-slim

WORKDIR /app

COPY data_loader_requirements.txt .

RUN pip install --no-cache-dir -r data_loader_requirements.txt

RUN mkdir -p auth
RUN mkdir -p util
RUN mkdir -p .solomo
RUN mkdir -p facility_roster
RUN mkdir -p provider_roster

COPY .solomo/secrets.toml ./.solomo/

COPY auth/salesforce_oauth.py ./auth/

COPY util/params.py ./util/



COPY data_loader.py .

COPY provider_roster/acc_loc_dataloader_mapping.yaml ./provider_roster/
COPY provider_roster/contact_dataloader_mapping.yaml ./provider_roster/

COPY provider_roster/data_loader_1_provider_roster.py ./provider_roster/
COPY provider_roster/data_loader_2_sf_helper.py ./provider_roster/
COPY provider_roster/data_loader_3_place_key_helper.py ./provider_roster/
COPY provider_roster/data_loader_4_acc_process_helper.py ./provider_roster/
COPY provider_roster/data_loader_5_mapper.py ./provider_roster/
COPY provider_roster/data_loader_6_con_process_helper.py ./provider_roster/
COPY provider_roster/data_loader_7_phys_loc_rel_process_helper.py ./provider_roster/

COPY facility_roster/acc_facility_dataloader_mapping.yaml ./facility_roster/

COPY facility_roster/data_loader_1_facility_roster.py ./facility_roster/
COPY facility_roster/data_loader_2_facility_sf_helper.py ./facility_roster/
COPY facility_roster/data_loader_3_facility_place_key_helper.py ./facility_roster/
COPY facility_roster/data_loader_4_facility_process_helper.py ./facility_roster/
COPY facility_roster/data_loader_5_facility_mapper.py ./facility_roster/



EXPOSE 8501

CMD ["streamlit", "run", "data_loader.py", "--server.port=8501", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--server.address=0.0.0.0"]