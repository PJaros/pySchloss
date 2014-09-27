#!/usr/bin/python2
# -*- coding: utf-8 -*-

__schloss_data_directory__ = '../data/'
schloss_pickle_file = 'pySchloss.pkl'

import os
import os.path
import pickle

class ProjectPathNotFound(Exception):
    """Raised when we can't find the project directory."""

def load_config():
    data_file = get_data_file(schloss_pickle_file)
    if not os.path.isfile(data_file):
        return {"alias":{}}
    else:
        with open(data_file,'rb') as f:
            return pickle.load(f)

def save_config(config):
    with open(get_data_file(schloss_pickle_file),'wb') as f:
        pickle.dump(config, f)
        f.close()

def get_data_file(*path_segments):
    """Get the full path to a data file.

    Returns the path to a file underneath the data directory (as defined by
    `get_data_path`). Equivalent to os.path.join(get_data_path(),
    *path_segments).
    """
    return os.path.join(get_data_path(), *path_segments)


def get_data_path():
    """Retrieve pySchloss data path

    This path is by default <hat_wrap_lib_path>/../data/ in trunk
    and /usr/share/pySchloss in an installed version but this path
    is specified at installation time.
    """

    # Get pathname absolute or relative.
    path = os.path.join(
        os.path.dirname(__file__), __schloss_data_directory__)

    abs_data_path = os.path.abspath(path)
    if not os.path.exists(abs_data_path):
        raise ProjectPathNotFound

    return abs_data_path