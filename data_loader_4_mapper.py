
import json
import yaml

# Use mapping.yaml (Excel column to variable name mapping, simple key-value)
_MAPPING_FILE_PATH = "mapping.yaml"
with open(_MAPPING_FILE_PATH, "r") as _file:
    _MAPPING_ACC_DATA = yaml.safe_load(_file)

def map_xls_data_to_acc_data(xls_record, sf_record):
    if _MAPPING_ACC_DATA and len(_MAPPING_ACC_DATA.keys()) > 0:
        for xls_field in xls_record:
            if xls_field in _MAPPING_ACC_DATA:
                sf_record[_MAPPING_ACC_DATA[xls_field]] = xls_record[xls_field]
    return sf_record