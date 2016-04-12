# (c) Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
# This file is under the BSD license
#
# Helper script for adding and removing entries in the
# Windows system path from the NSIS installer.

from __future__ import unicode_literals

__all__ = ['remove_from_system_path', 'add_to_system_path', 'broadcast_environment_settings_change']

import sys
import os
import ctypes
from ctypes import wintypes
if sys.version_info[0] >= 3:
    import winreg as reg
else:
    import _winreg as reg

HWND_BROADCAST = 0xffff
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002
SendMessageTimeout = ctypes.windll.user32.SendMessageTimeoutW
SendMessageTimeout.restype = None #wintypes.LRESULT
SendMessageTimeout.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)]

DEFAULT_PATH_VAR='ANACONDA_PATH'


def broadcast_environment_settings_change():
    """Broadcasts to the system indicating that master environment variables have changed.

    This must be called after using the other functions in this module to
    manipulate environment variables.
    """
    SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, u'Environment',
                SMTO_ABORTIFHUNG, 5000, ctypes.pointer(wintypes.DWORD()))


reg_paths = {"allusers": (reg.HKEY_LOCAL_MACHINE,
                          r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
             "userlocal": (reg.HKEY_CURRENT_USER, r'Environment')}


def set_env_var(path_env_var, env_path_value, allusers, value_type=reg.REG_EXPAND_SZ):
    root, keyname = reg_paths["allusers" if allusers else "userlocal"]
    key = reg.OpenKey(root, keyname, 0,
            reg.KEY_QUERY_VALUE|reg.KEY_SET_VALUE)

    if env_path_value:
        reg.SetValueEx(key, path_env_var, 0, value_type, env_path_value)
    else:
        try:
            reg.DeleteValue(key, path_env_var)
        except WindowsError:
            # do nothing here - value already does not exist
            pass
    reg.CloseKey(key)
    broadcast_environment_settings_change()


def get_env_var_from_registry(path_env_var, allusers):
    env_path_value = ""
    root, keyname = reg_paths["allusers" if allusers else "userlocal"]
    key = reg.OpenKey(root, keyname, 0,
                reg.KEY_QUERY_VALUE|reg.KEY_SET_VALUE)
    try:
        env_path_value = reg.QueryValueEx(key, path_env_var)[0]
    except WindowsError:
        print("Requested registry value (%s %s) does not exist.  Returning empty string." % \
              ("All users" if allusers else "local",
               path_env_var))
    return env_path_value


def remove_from_system_path(paths, allusers=True, path_env_var=DEFAULT_PATH_VAR):
    """Removes all entries from the path which match the value in 'pathname'

       You must call broadcast_environment_settings_change() after you are finished
       manipulating the environment with this and other functions.

       For example,
         # Remove Anaconda from PATH
         remove_from_system_path(r'C:\Anaconda')
         broadcast_environment_settings_change()
    """
    # Make sure it's a list
    if not issubclass(type(paths), list):
        paths=[paths]

    env_path_value = get_env_var_from_registry(path_env_var, allusers)
    PATH_value = get_env_var_from_registry("PATH", allusers)

    if path_env_var != "PATH":
        reg_value = env_path_value
    else:
        reg_value = PATH_value

    any_change = False
    results = []

    pathnames = [os.path.normpath(p).lower().decode("utf-8") for p in paths]
    for v in reg_value.split(os.pathsep):
        vexp = reg.ExpandEnvironmentStrings(v)
        # requested path in a normalized way
        if os.path.normpath(vexp).lower() in pathnames:
            # implicitly omit adding matching paths to the new path we build below
            any_change = True
        else:
            # Append the original unexpanded version to the results
            results.append(v)

    if any_change:
        modified_path = os.pathsep.join(results)
        # this takes care of the case when path_env_var is 'PATH'
        set_env_var(path_env_var, modified_path, allusers)
        if path_env_var != "PATH":
            cleaned_path = PATH_value.replace("%{}%".format(path_env_var), "").\
                            replace(";;", ";").rstrip(";")
            set_env_var("PATH", cleaned_path, allusers)


def add_to_system_path(paths, allusers=True, path_env_var=DEFAULT_PATH_VAR):
    """Adds the requested paths to the system PATH variable.

       You must call broadcast_environment_settings_change() after you are finished
       manipulating the environment with this and other functions.

       If path_env_var is not PATH, then any values in `paths` are stored in the
       `path_env_var` variable, and the `path_env_var` is added to PATH.

    """
    # Make sure it's a list
    if not issubclass(type(paths), list):
        paths = [paths]

    # Ensure all the paths are valid before we start messing with the
    # registry.
    new_paths = None
    for p in paths:
        p = os.path.abspath(p)
        if not os.path.isdir(p):
            raise RuntimeError(
                'Directory "%s" does not exist, '
                'cannot add it to the path' % p
            )
        if new_paths:
            new_paths = os.pathsep.join([new_paths, p])
        else:
            new_paths = p

    env_path_value = get_env_var_from_registry(path_env_var, allusers)
    PATH_value = get_env_var_from_registry("PATH", allusers)

    # either insert the variable name to be expanded, or the value of the PATH
    #  to be added
    if path_env_var != "PATH":
        new_part = "%{}%".format(path_env_var)
        env_path_value = os.pathsep.join([new_paths, env_path_value])
    else:
        new_part = new_paths

    # If we're an admin install, put us at the end of PATH.  If we're
    # a user install, throw caution to the wind and put us at the
    # start.  (This ensures we're picked up as the default python out
    # of the box, regardless of whether or not the user has other
    # pythons lying around on their PATH, which would complicate
    # things.  It's also the same behavior used on *NIX.)
    if allusers and new_part not in PATH_value:
        PATH_value = os.pathsep.join([PATH_value, new_part]).replace(";;",";").rstrip(";")
    elif new_part not in PATH_value:
        PATH_value = os.pathsep.join([new_part, PATH_value]).replace(";;",";").rstrip(";")

    set_env_var("PATH", PATH_value, allusers)
    if path_env_var != "PATH":
        set_env_var(path_env_var, env_path_value, allusers)
