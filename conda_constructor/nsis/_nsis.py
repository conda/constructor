# (c) Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
# This file is under the BSD license

# Helper script which is called from within the nsis install process
# on Windows.  The fact that we put this file into the standard library
# directory is merely a convenience.  This way, functionally can easily
# easily be tested in an installation.

import os
import sys
import json
import traceback
from os.path import isdir, join, exists

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

def create_conda_meta():
    meta_dir = join(sys.prefix, 'conda-meta')
    info_dir = join(sys.prefix, 'info')

    with open(join(info_dir, 'index.json')) as fi:
        meta = json.load(fi)

    if meta['name'] == '_cache':
        return

    meta['files'] = []
    for line in open(join(info_dir, 'files')):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        meta['files'].append(line)

    if not isdir(meta_dir):
        os.mkdir(meta_dir)

    fn = '%(name)s-%(version)s-%(build)s.json' % meta
    with open(join(meta_dir, fn), 'w') as fo:
        json.dump(meta, fo, indent=2, sort_keys=True)


def mk_menus(remove=False):
    try:
        import menuinst
    except ImportError:
        return
    menu_dir = join(sys.prefix, 'Menu')
    if os.path.exists(menu_dir):
        for fn in os.listdir(menu_dir):
            if fn.endswith('.json'):
                shortcut = join(menu_dir, fn)
                try:
                    menuinst.install(shortcut, remove)
                except Exception as e:
                    out("Failed to process %s...\n" % shortcut)
                    err("Error: %s\n" % str(e))
                    err("Traceback:\n%s\n" % traceback.format_exc(20))
                else:
                    out("Processed %s successfully.\n" % shortcut)


def mk_dirs():
    os.mkdir(join(sys.prefix, 'envs'))
    try:
        from _license import get_license_dirs
    except ImportError:
        return
    # try creating all license directories
    for path in get_license_dirs():
        if os.path.isdir(path):
            out("%s already exists, skipping...\n" % path)
            continue
        try:
            os.mkdir(path)
        except Exception as e:
            err("Failed to create %s.\n" % path)
            err("Error: %s\n" % str(e))
            err("Traceback: %s\n" % traceback.format_exc(20))
        else:
            out("Created %s.\n" % path)


allusers = (not exists(join(sys.prefix, '.nonadmin')))

def add_anaconda_to_path():
    from _system_path import (add_to_system_path, remove_from_system_path,
                              broadcast_environment_settings_change)
    # if previous Anaconda installs left remnants, remove those
    remove_from_system_path(sys.prefix, allusers)
    remove_from_system_path(join(sys.prefix, 'Scripts'), allusers)
    # add Anaconda to the path
    add_to_system_path([sys.prefix, join(sys.prefix, 'Scripts')], allusers)
    broadcast_environment_settings_change()


def remove_anaconda_from_path():
    from _system_path import (remove_from_system_path,
                              broadcast_environment_settings_change)
    remove_from_system_path(sys.prefix, allusers)
    remove_from_system_path(join(sys.prefix, 'Scripts'), allusers)
    broadcast_environment_settings_change()


def main():
    cmd = sys.argv[1].strip()
    if cmd == 'postpkg':
        create_conda_meta()
    elif cmd == 'mkmenus':
        mk_menus(remove=False)
    elif cmd == 'rmmenus':
        mk_menus(remove=True)
    elif cmd == 'mkdirs':
        mk_dirs()
    elif cmd == 'addpath':
        add_anaconda_to_path()
    elif cmd == 'rmpath':
        remove_anaconda_from_path()
    else:
        sys.exit("ERROR: did not expect %r" % cmd)


if __name__ == '__main__':
    main()
