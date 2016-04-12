from constructor.nsis import _system_path as sp
from constructor.nsis._nsis import paths

import os
import shutil
import sys

import pytest

def count_path_entries(path_env_var, allusers):
    env_path_value = sp.get_env_var_from_registry(path_env_var, allusers)
    count_paths = {path: env_path_value.count(path) for path in paths}
    return count_paths

@pytest.mark.parametrize("allusers", [True, False])
@pytest.mark.parametrize("path_env_var", ['PATH',
                                          'ANACONDA_PATH'])
def test_add_remove_path(allusers, path_env_var):
    backup_value = sp.get_env_var_from_registry(path_env_var, allusers)
    PATH_backup = sp.get_env_var_from_registry("PATH", allusers)
    try:
        initial_counts = count_path_entries(path_env_var, allusers)
        sp.add_to_system_path(paths, allusers, path_env_var)
        added_counts = count_path_entries(path_env_var, allusers)
        assert all([added_counts[key] >= initial_counts[key] for key in initial_counts])
        sp.remove_from_system_path(paths, allusers, path_env_var)
        final_counts = count_path_entries(path_env_var, allusers)
        assert all([final_counts[key] <= initial_counts[key] for key in initial_counts])
        if path_env_var != 'PATH':
            assert path_env_var not in os.getenv("PATH")
    finally:
        # restore any environment variables we might have touched
        sp.set_env_var(path_env_var, backup_value, allusers)
        sp.set_env_var("PATH", PATH_backup, allusers)

