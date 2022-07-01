"""Module interacting with the config.ini file, for dynamically import repositories and branches"""
import configparser
from pathlib import Path
import os

# Example datas :
# conf_var = "Pull_server"
# address = "http://yourport:yoururl/"
# repository = ["role_base"]
# authorized_branches = ["master", "r2d2"]
# config_dictionnary = {"address": address, "repository": repository, "authorized_branches": authorized_branches}
#
# config_write(conf_var, config_dictionnary)


class ConfigReader:
    """Class to check the config files"""
    def __init__(self, config_org):
        self.cwd = os.getcwd()
        self.config = configparser.ConfigParser(delimiters=':')
        self.organization = config_org
        self.config_file = None
        self.find_config(self.organization)
        self.sections = None

    def find_config(self, config_org):
        """Find every config file in the present directory"""
        try:
            assert os.path.isfile(config_org + ".ini")
        except AssertionError as e:
            print("no config file for {}, \n {}".format(config_org, e))
            raise FileNotFoundError
        else:
            self.config_file = config_org + ".ini"

    def config_read(self):
        """Retrieve parameters within files"""
        self.config.read(self.config_file)
        self.sections = self.config.sections()

    def config_get(self, section):
        """check if section is in config file"""
        self.config.read(self.config_file)
        branches = self.config[section]
        return branches
