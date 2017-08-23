# (c) Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
# This file is under the BSD license

# Helper script which is called from within the nsis install process
# on Windows.  The fact that we put this file into the standard library
# directory is merely a convenience.  This way, functionally can easily
# be tested in an installation.

import os
import sys
import traceback
from os.path import isdir, isfile, join, exists

# Install an exception hook which pops up a message box.
# Ideally, exceptions will get returned to NSIS and logged there,
# etc, but this is a stopgap solution for now.
old_excepthook = sys.excepthook

def gui_excepthook(exctype, value, tb):
    try:
        import ctypes, traceback
        MB_ICONERROR = 0x00000010
        title = u'Installation Error'
        msg = u''.join(traceback.format_exception(exctype, value, tb))
        ctypes.windll.user32.MessageBoxW(0, msg, title, MB_ICONERROR)
    finally:
        # Also call the old exception hook to let it do
        # its thing too.
        old_excepthook(exctype, value, tb)
sys.excepthook = gui_excepthook

# If pythonw is being run, there may be no write function
if sys.stdout and sys.stdout.write:
    out = sys.stdout.write
    err = sys.stderr.write
else:
    def write(x):
        pass
    out = write
    err = write


def mk_menus(remove=False, prefix=None):
    try:
        import menuinst
    except (ImportError, OSError):
        return
    if prefix is None:
        prefix = sys.prefix
    menu_dir = join(prefix, 'Menu')
    if not os.path.isdir(menu_dir):
        return
    pkg_names = [s.strip() for s in sys.argv[2:]]
    for fn in os.listdir(menu_dir):
        if not fn.endswith('.json'):
            continue
        if pkg_names and fn[:-5] not in pkg_names:
            continue
        shortcut = join(menu_dir, fn)
        try:
            menuinst.install(shortcut, remove, prefix=prefix)
        except Exception as e:
            out("Failed to process %s...\n" % shortcut)
            err("Error: %s\n" % str(e))
            err("Traceback:\n%s\n" % traceback.format_exc(20))
        else:
            out("Processed %s successfully.\n" % shortcut)


def get_conda_envs_from_python_api():
    try:
        from conda.cli.python_api import run_command, Commands
    except (ImportError, OSError):
        return
    from json import loads
    c_stdout, c_stderr, return_code = run_command(Commands.INFO, "--json")
    json_conda_info = loads(c_stdout)
    return json_conda_info["envs"]


def get_conda_envs_from_libconda():
    # alternative implementation using libconda
    # adapted from conda.misc.list_prefixes
    try:
        from libconda.config import envs_dirs
    except (ImportError, OSError):
        return
    # Lists all the prefixes that conda knows about.
    for envs_dir in envs_dirs:
        if not isdir(envs_dir):
            continue
        for dn in sorted(os.listdir(envs_dir)):
            if dn.startswith('.'):
                continue
            prefix = join(envs_dir, dn)
            if isdir(prefix):
                prefix = join(envs_dir, dn)
                yield prefix


get_conda_envs = get_conda_envs_from_python_api


def rm_menus():
    mk_menus(remove=True)
    try:
        import menuinst
        menuinst
    except (ImportError, OSError):
        return
    try:
        envs = get_conda_envs()
        envs = list(envs)  # make sure `envs` is iterable
    except Exception as e:
        out("Failed to get conda environments list\n")
        err("Error: %s\n" % str(e))
        err("Traceback:\n%s\n" % traceback.format_exc(20))
        return
    for env in envs:
        env = str(env)  # force `str` so that `os.path.join` doesn't fail
        mk_menus(remove=True, prefix=env)


def run_post_install():
    """
    call the post install script, if the file exists
    """
    path = join(sys.prefix, 'pkgs', 'post_install.bat')
    if not isfile(path):
        return
    env = os.environ
    env['PREFIX'] = str(sys.prefix)
    try:
        args = [env['COMSPEC'], '/c', path]
    except KeyError:
        err("Error: COMSPEC undefined\n")
        return
    import subprocess
    try:
        subprocess.check_call(args, env=env)
    except subprocess.CalledProcessError:
        err("Error: running %s failed\n" % path)


allusers = (not exists(join(sys.prefix, '.nonadmin')))

def add_to_path():
    from _system_path import (add_to_system_path, remove_from_system_path,
                              broadcast_environment_settings_change)
    # if previous Anaconda installs left remnants, remove those
    remove_from_system_path(sys.prefix, allusers)
    remove_from_system_path(join(sys.prefix, 'Scripts'), allusers)
    # add Anaconda to the path
    add_to_system_path([sys.prefix, join(sys.prefix, 'Scripts')], allusers)
    broadcast_environment_settings_change()


def remove_from_path():
    from _system_path import (remove_from_system_path,
                              broadcast_environment_settings_change)
    remove_from_system_path(sys.prefix, allusers)
    remove_from_system_path(join(sys.prefix, 'Scripts'), allusers)
    broadcast_environment_settings_change()


def main():
    cmd = sys.argv[1].strip()
    if cmd == 'mkmenus':
        mk_menus(remove=False)
    elif cmd == 'post_install':
        run_post_install()
    elif cmd == 'rmmenus':
        rm_menus()
    elif cmd == 'addpath':
        add_to_path()
    elif cmd == 'rmpath':
        remove_from_path()
    else:
        sys.exit("ERROR: did not expect %r" % cmd)


if __name__ == '__main__':
    main()
