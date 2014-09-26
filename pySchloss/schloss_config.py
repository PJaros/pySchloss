#!/usr/bin/python2
# -*- coding: utf-8 -*-

__schloss_data_directory__ = '../data/'

import os

class ProjectPathNotFound(Exception):
    """Raised when we can't find the project directory."""

def get_data_file(*path_segments):
    """Get the full path to a data file.

    Returns the path to a file underneath the data directory (as defined by
    `get_data_path`). Equivalent to os.path.join(get_data_path(),
    *path_segments).
    """
    return os.path.join(get_data_path(), *path_segments)


def get_data_path():
    """Retrieve hat-wrap data path

    This path is by default <hat_wrap_lib_path>/../data/ in trunk
    and /usr/share/hat-wrap in an installed version but this path
    is specified at installation time.
    """

    # Get pathname absolute or relative.
    path = os.path.join(
        os.path.dirname(__file__), __schloss_data_directory__)

    abs_data_path = os.path.abspath(path)
    if not os.path.exists(abs_data_path):
        raise ProjectPathNotFound

    return abs_data_path