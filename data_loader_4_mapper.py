import json
import yaml

def map_xls_data_to_acc_data(xls_record, sf_record):
    # Use mapping.yaml (Excel column to variable name mapping, simple key-value)
    file_path = "mapping.yaml"
    with open(file_path, "r") as file:
        mapping_acc_data = yaml.safe_load(file)

    if mapping_acc_data and len(mapping_acc_data.keys()) > 0:
        for xls_field in xls_record:
            if xls_field in mapping_acc_data:
                sf_record[mapping_acc_data[xls_field]] = xls_record[xls_field]
    return sf_record