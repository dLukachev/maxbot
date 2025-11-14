import configparser

config = configparser.ConfigParser()

def get_points_config(config_path="config.ini"):
    config.read(config_path, encoding='utf-8-sig')
    return dict(config["points"])

def get_levels_config(config_path="config.ini"):
    config.read(config_path, encoding='utf-8-sig')
    return dict(config["levels"])

# TODO: написать рассчеты поинтов