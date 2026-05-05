import toml

def get_param(group, item):
    config = toml.load("./.solomo/secrets.toml")
    
    params = config[group]
    return params[item]

def get_params(group):
    config = toml.load("./.solomo/secrets.toml")
    
    params = config[group]
    return params
