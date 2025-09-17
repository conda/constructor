# (c) Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
# This file is under the BSD license

# Helper script which is called from within the nsis install process
# on Windows.  The fact that we put this file into the standard library
# directory is merely a convenience.  This way, functionally can easily
# be tested in an installation.

import os
import re
import sys
import traceback
from os.path import exists, isfile, join

try:
    import winreg
except ImportError:
    import _winreg as winreg

ROOT_PREFIX = sys.prefix

# Install an exception hook which pops up a message box.
# Ideally, exceptions will get returned to NSIS and logged there,
# etc, but this is a stopgap solution for now.
old_excepthook = sys.excepthook


def gui_excepthook(exctype, value, tb):
    try:
        import ctypes
        import traceback
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
    import ctypes
    OutputDebugString = ctypes.windll.kernel32.OutputDebugStringW
    OutputDebugString.argtypes = [ctypes.c_wchar_p]

    def out(x):
        OutputDebugString('_nsis.py: ' + x)

    def err(x):
        OutputDebugString('_nsis.py: Error: ' + x)


class NSISReg:
    def __init__(self, reg_path):
        self.reg_path = reg_path
        if exists(join(ROOT_PREFIX, '.nonadmin')):
            self.main_key = winreg.HKEY_CURRENT_USER
        else:
            self.main_key = winreg.HKEY_LOCAL_MACHINE

    def set(self, name, value):
        try:
            winreg.CreateKey(self.main_key, self.reg_path)
            registry_key = winreg.OpenKey(self.main_key, self.reg_path, 0,
                                          winreg.KEY_WRITE)
            winreg.SetValueEx(registry_key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(registry_key)
            return True
        except WindowsError:
            return False

    def get(self, name):
        try:
            registry_key = winreg.OpenKey(self.main_key, self.reg_path, 0,
                                          winreg.KEY_READ)
            value, regtype = winreg.QueryValueEx(registry_key, name)
            winreg.CloseKey(registry_key)
            return value
        except WindowsError:
            return None


def mk_dirs():
    envs_dir = join(ROOT_PREFIX, 'envs')
    if not exists(envs_dir):
        os.mkdir(envs_dir)


def get_conda_envs_from_python_api():
    try:
        from conda.cli.python_api import Commands, run_command
    except (ImportError, OSError):
        return
    from json import loads
    c_stdout, c_stderr, return_code = run_command(Commands.INFO, "--json")
    json_conda_info = loads(c_stdout)
    return json_conda_info["envs"]


get_conda_envs = get_conda_envs_from_python_api


def run_post_install():
    """
    call the post install script, if the file exists
    """
    path = join(ROOT_PREFIX, 'pkgs', 'post_install.bat')
    if not isfile(path):
        return
    env = os.environ.copy()
    env.setdefault('PREFIX', str(ROOT_PREFIX))
    cmd_exe = os.path.join(os.environ['SystemRoot'], 'System32', 'cmd.exe')
    if not os.path.isfile(cmd_exe):
        cmd_exe = os.path.join(os.environ['windir'], 'System32', 'cmd.exe')
    if not os.path.isfile(cmd_exe):
        err("Error: running %s failed.  cmd.exe could not be found.  "
            "Looked in SystemRoot and windir env vars.\n" % path)
        if os.environ.get("NSIS_SCRIPTS_RAISE_ERRORS"):
            sys.exit(1)
    args = [cmd_exe, '/d', '/c', path]
    import subprocess
    try:
        subprocess.check_call(args, env=env)
    except subprocess.CalledProcessError:
        err("Error: running %s failed\n" % path)
        if os.environ.get("NSIS_SCRIPTS_RAISE_ERRORS"):
            sys.exit(1)


def run_pre_uninstall():
    """
    call the pre uninstall script, if the file exists
    """
    path = join(ROOT_PREFIX, 'pre_uninstall.bat')
    if not isfile(path):
        return
    env = os.environ.copy()
    env.setdefault('PREFIX', str(ROOT_PREFIX))
    cmd_exe = os.path.join(os.environ['SystemRoot'], 'System32', 'cmd.exe')
    if not os.path.isfile(cmd_exe):
        cmd_exe = os.path.join(os.environ['windir'], 'System32', 'cmd.exe')
    if not os.path.isfile(cmd_exe):
        err("Error: running %s failed.  cmd.exe could not be found.  "
            "Looked in SystemRoot and windir env vars.\n" % path)
        if os.environ.get("NSIS_SCRIPTS_RAISE_ERRORS"):
            sys.exit(1)
    args = [cmd_exe, '/d', '/c', path]
    import subprocess
    try:
        subprocess.check_call(args, env=env)
    except subprocess.CalledProcessError:
        err("Error: running %s failed\n" % path)
        if os.environ.get("NSIS_SCRIPTS_RAISE_ERRORS"):
            sys.exit(1)


allusers = (not exists(join(ROOT_PREFIX, '.nonadmin')))
# out('allusers is %s\n' % allusers)

# This must be the same as conda's binpath_from_arg() in conda/cli/activate.py
PATH_SUFFIXES = ('',
                 os.path.join('Library', 'mingw-w64', 'bin'),
                 os.path.join('Library', 'usr', 'bin'),
                 os.path.join('Library', 'bin'),
                 'Scripts')


def remove_from_path(root_prefix=None):
    from _system_path import broadcast_environment_settings_change, remove_from_system_path

    if root_prefix is None:
        root_prefix = ROOT_PREFIX
    for path in [os.path.normpath(os.path.join(root_prefix, path_suffix))
                 for path_suffix in PATH_SUFFIXES]:
        remove_from_system_path(path, allusers)
    broadcast_environment_settings_change()


def add_to_path(pyversion, arch):
    if allusers:
        # To address CVE-2022-26526.
        # In AllUsers install mode, do not allow PATH manipulation.
        print("PATH manipulation is disabled in All Users mode.", file=sys.stderr)
        return

    from _system_path import (
        add_to_system_path,
        broadcast_environment_settings_change,
        get_previous_install_prefixes,
    )

    # If a previous Anaconda install attempt to this location left remnants,
    # remove those.
    remove_from_path(ROOT_PREFIX)

    # If a previously registered Anaconda install left remnants, remove those.
    try:
        old_prefixes = get_previous_install_prefixes(pyversion, arch, allusers)
    except IOError:
        old_prefixes = []
    for prefix in old_prefixes:
        out('Removing old installation at %s from PATH (if any entries get found)\n' % (prefix))
        remove_from_path(prefix)

    # add Anaconda to the path
    add_to_system_path([os.path.normpath(os.path.join(ROOT_PREFIX, path_suffix))
                        for path_suffix in PATH_SUFFIXES], allusers)
    broadcast_environment_settings_change()


def add_condabin_to_path():
    if allusers:
        # To address CVE-2022-26526.
        # In AllUsers install mode, do not allow PATH manipulation.
        print("PATH manipulation is disabled in All Users mode.", file=sys.stderr)
        return

    from _system_path import (
        add_to_system_path,
        broadcast_environment_settings_change,
    )

    add_to_system_path(os.path.normpath(os.path.join(ROOT_PREFIX, "condabin")), allusers)
    broadcast_environment_settings_change()


def rm_regkeys():
    cmdproc_reg_entry = NSISReg(r'Software\Microsoft\Command Processor')
    cmdproc_autorun_val = cmdproc_reg_entry.get('AutoRun')
    conda_hook_regex_pat = r'((\s+&\s+)?(if +exist)?(\s*?\"[^\"]*?conda[-_]hook\.bat\"))'
    if join(ROOT_PREFIX, 'condabin') in (cmdproc_autorun_val or ''):
        cmdproc_autorun_newval = re.sub(conda_hook_regex_pat, '',
                                        cmdproc_autorun_val)
        try:
            cmdproc_reg_entry.set('AutoRun', cmdproc_autorun_newval)
        except Exception:
            # Hey, at least we made an attempt to cleanup
            pass


def main():
    cmd = sys.argv[1].strip()
    if cmd == 'post_install':
        run_post_install()
    elif cmd == 'rmreg':
        rm_regkeys()
    elif cmd == 'mkdirs':
        mk_dirs()
    elif cmd == 'addpath':
        # These checks are probably overkill, but could be useful
        # if I forget to update something that uses this code.
        if len(sys.argv) > 2:
            pyver = sys.argv[2]
        else:
            pyver = '%s.%s.%s' % (sys.version_info.major,
                                  sys.version_info.minor,
                                  sys.version_info.micro)
        if len(sys.argv) > 3:
            arch = sys.argv[2]
        else:
            arch = '32-bit' if tuple.__itemsize__ == 4 else '64-bit'
        add_to_path(pyver, arch)
    elif cmd == 'addcondabinpath':
        add_condabin_to_path()
    elif cmd == 'rmpath':
        remove_from_path()
    elif cmd == 'pre_uninstall':
        run_pre_uninstall()
    else:
        sys.exit("ERROR: did not expect %r" % cmd)


if __name__ == '__main__':
    main()
