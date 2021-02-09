# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from functools import partial
from os.path import dirname
import re
import sys
from .utils import yaml

from constructor.exceptions import (UnableToParse, UnableToParseMissingJinja2,
                                    YamlParsingError)

# list of tuples (key name, required, type, description)
KEYS = [
    ('name',                   True,  str, '''
Name of the installer. Names may be composed of letters, numbers,
underscores, dashes, and periods, but may not begin or end with a
dash or period.
'''),

    ('version',                True,  str, '''
Version of the installer. Versions may be composed of letters, numbers,
underscores, dashes, and periods, but may not begin or end with a
dash or period.
'''),

    ('channels',               False, list, '''
The conda channels from which packages are retrieved. At least one channel must
be supplied, either in `channels` or `channels_remap`.
'''),

    ('channels_remap',         False, list, '''
A list of `src/dest` channel pairs. When retrieving the packages, conda will
use the `src` channels; but rename those channels to `dst` within the installer.
This allows an installer to be built against a different set of channels than
will be present when the installer is actually used. Example use:
```
channels_remap:
  -
      src: file:///tmp/a3/conda-bld
      dest: https://repo.anaconda.com/pkgs/main
  -
      src: file:///tmp/r/conda-bld
      dest: https://repo.anaconda.com/pkgs/r
```
At least one channel must be supplied, either in `channels` or `channels_remap`.
'''),

    ('specs',                  False, (list, str), '''
A list of package specifications; e.g. `python 2.7*`, `pyzmq` or `numpy >=1.8`.
The specifications are identical in form and purpose to those that would be
included in a `conda create --file` command. Packages may also be specified
by an exact URL; e.g.,
`https://repo.anaconda.com/pkgs/main/osx-64/openssl-1.0.2o-h26aff7b_0.tar.bz2`.
'''),

    ('user_requested_specs',                  False, (list, str), '''
A list of package specifications to be recorded as "user-requested" for the
initial environment in conda's history file. This information is used by newer
versions of conda to better filter its package choices on subsequent installs;
for example, if `python=3.6` is included, then conda will always seek versions
of packages compatible with Python 3.6. If this is option is not provided, it
will be set equal to the value of `specs`.
'''),

    ('exclude',                False, list, '''
A list of package names to be excluded after the `specs` have been resolved.
For example, you can say that `readline` should be excluded, even though it
is contained as a result of resolving the specs for `python 2.7`.
'''),

    ('menu_packages',           False, list, '''
A list of packages with menu items to be instsalled. The packages must have
necessary metadata in "Menu/<package name>.json").  Menu items are currently
only supported on Windows. By default, all menu items will be installed;
supplying this list allows a subset to be selected instead.
'''),

    ('ignore_duplicate_files',  False, bool, '''
By default, constructor will error out when adding packages with duplicate
files in them. Enable this option to warn instead and continue.
'''),

    ('install_in_dependency_order', False, (bool, str), '''
_Obsolete_. The current version of constructor relies on the standalone
conda executable for its installation behavior. This option is now
ignored with a warning.
'''),

    ('environment', False, str, '''
Name of the environment to construct from. If this option is present, the
`specs` argument will be ignored. Using this option allows the user to
curate the enviromment interactively using standard `conda` commands, and
run constructor with full confidence that the exact environment will be
reproduced.
'''),

    ('environment_file', False, str, '''
Path to an environment file to construct from. If this option is present, the
`specs` argument will be ignored. Instead, constructor will call conda to
create a temporary environment, constructor will build and installer from
that, and the temporary environment will be removed. This ensures that
constructor is using the precise local conda configuration to discover
and install the packages.
'''),

    ('transmute_file_type', False, str, '''
File type extension for the files to be transmuted into. Currently supports
only '.conda'. See conda-package-handling for supported extension names.
If left empty, no transumating is done.
'''),

    ('conda_default_channels', False, list, '''
If this value is provided as well as `write_condarc`, then the channels
in this list will be included as the value of the `default_channels:`
option in the environment's `.condarc` file. This will have an impact
only if `conda` is included in the environmnent.
'''),
    ('conda_channel_alias', False, str, '''
The channel alias that would be assumed for the created installer
(only useful if it includes conda).
'''),

    ('installer_filename',     False, str, '''
The filename of the installer being created. If not supplied, a reasonable
default will determined by the `name`, `version`, platform, and installer type.
'''),

    ('installer_type',     False, (str, list), '''
The type of the installer being created.  Possible values are:
- `sh`: shell-based installer for Linux or macOS;
- `pkg`: macOS GUI installer
- `exe`: Windows GUI installer

The default type is `sh` on Linux and macOS, and `exe` on Windows. A special
value of `all` builds _both_ `sh` and `pkg` installers on macOS, as well
as `sh` on Linux and `exe` on Windows.
'''),

    ('license_file',           False, str, '''
Path to the license file being displayed by the installer during the install
process.
'''),

    ('keep_pkgs',              False, bool, '''
If `False` (default), the package cache in the `pkgs` subdirectory is removed
when the installation process is complete. If `True`, this subdirectory and
its contents are preserved. If `keep_pkgs` is `False`, Unix `.sh` and Windows `.msi`
installers offer a command-line option (`-k` and `/KeepPkgCache`, respectively)
to preserve the package cache.
'''),

    ('signing_identity_name',  False, str, '''
By default, the MacOS pkg installer isn't signed. If an identity name is specified
using this option, it will be used to sign the installer. Note that you will need
to have a certificate and corresponding private key together called an 'identity'
in one of your accessible keychains.
'''),

    ('attempt_hardlinks',          False, (bool, str), '''
_Obsolete_. The current version of constructor relies on the standalone
conda executable for its installation behavior. This option is now
ignored with a warning.
'''),

    ('write_condarc',          False, bool, '''
By default, no `.condarc` file is written. If set, a `.condarc` file is written to
the base environment if there are any channels or conda_default_channels is set.
'''),

    ('condarc',          False, (dict, str), '''
If set, a `.condarc` file is written to the base environment containing the contents
of this value. The value can either be a string (likely a multi-line string) or
a dictionary, which will be converted to a YAML string for writing. _Note:_ if this
option is used, then all other options related to the construction of a `.condarc`
file&mdash;`write_condarc`, `conda_default_channels`, etc.&mdash;are ignored.
'''),

    ('company',                False, str, '''
Name of the company/entity who is responsible for the installer.
'''),

    ('uninstall_name',         False, str, '''
Application name in the Windows "Programs and Features" control panel.
Defaults to `${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})`.
'''),

    ('pre_install',            False, str, '''
Path to a pre-install script. For Unix `.sh` installers, the shebang
line is respected if present; otherwise, the script is run by the POSIX
shell `sh`. Note that the use of a shebang can reduce the portability of
the installer. This option is not supported for Windows `.exe` or macOS
`.pkg` installers.
'''),

    ('post_install',           False, str, '''
Path to a post-install script. For Unix `.sh` installers, the shebang
line is respected if present; otherwise, the script is run by the POSIX
shell `sh`. Note that the use of a shebang can reduce the portability of
the installer. For Windows `.exe` installers, this must be a `.bat` file.
This option is not supported for macOS `.pkg` installers.
'''),

    ('post_install_desc',      False, str, '''
A description of the purpose of the supplied post_install script. If this
string is supplied and non-empty, then the Windows and macOS GUI installers
will display it along with checkbox to enable or disable the execution of the
script. If this string is not supplied, it is assumed that the script
is compulsory and the option to disable it will not be offered.
'''),

    ('pre_uninstall',          False, str, '''
Path to a pre uninstall script. This is only supported for on Windows,
and must be a `.bat` file.
'''),

    ('default_prefix',         False, str, '''
Set default install prefix. On Linux, if not provided, the default prefix is
`${HOME}/${NAME}`. On windows, this is used only for "Just Me" installation;
for "All Users" installation, use the `default_prefix_all_users` key.
If not provided, the default prefix is `${USERPROFILE}\${NAME}`.
'''),

    ('default_prefix_domain_user', False, str, '''
Set default installation prefix for domain user. If not provided, the
installation prefix for domain user will be `${LOCALAPPDATA}\${NAME}`.
By default, it is different from the `default_prefix` value to avoid installing
the distribution in the roaming profile. Windows only.
'''),

    ('default_prefix_all_users', False, str, '''
Set default installation prefix for All Users installation. If not provided,
the installation prefix for all users installation will be
`${ALLUSERSPROFILE}\${NAME}`. Windows only.
'''),

    ('welcome_image',          False, str, '''
Path to an image in any common image format (`.png`, `.jpg`, `.tif`, etc.)
to be used as the welcome image for the Windows installer.
The image is re-sized to 164 x 314 pixels.
By default, an image is automatically generated.
'''),

    ('header_image',           False, str, '''
Like `welcome_image` for Windows, re-sized to 150 x 57 pixels.
'''),

    ('icon_image',             False, str, '''
Like `welcome_image` for Windows, re-sized to 256 x 256 pixels.
'''),

    ('default_image_color',    False, str, '''
The color of the default images (when not providing explicit image files)
used on Windows.  Possible values are `red`, `green`, `blue`, `yellow`.
The default is `blue`.
'''),

    ('welcome_image_text',     False, str, '''
If `welcome_image` is not provided, use this text when generating the image
(Windows only). Defaults to `name`.
'''),

    ('header_image_text',      False, str, '''
If `header_image` is not provided, use this text when generating the image
(Windows only). Defaults to `name`.
'''),

    ('initialize_by_default',    False, bool, '''
Whether to add the installation to the PATH environment variable. The default
is true for GUI installers (msi, pkg) and False for shell installers. The user
is able to change the default during interactive installation.
'''),

    ('register_python_default',  False, bool, '''
Default choice for whether to register the installed Python instance as the
system's default Python. The user is still able to change this during
interactive installation. (Windows only)
'''),

    ('check_path_length',     False, bool, '''
Check the length of the path where the distribution is installed to ensure nodejs
can be installed.  Raise a message to request shorter path (less than 46 character)
or enable long path on windows > 10 (require admin right). Default is True. (Windows only)
'''),
]


def ns_platform(platform):
    p = platform
    return dict(
        linux=p.startswith('linux-'),
        linux32=bool(p == 'linux-32'),
        linux64=bool(p == 'linux-64'),
        armv7l=bool(p == 'linux-armv7l'),
        aarch64=bool(p == 'linux-aarch64'),
        ppc64le=bool(p == 'linux-ppc64le'),
        arm64=bool(p == 'osx-arm64'),
        s390x=bool(p == 'linux-s390x'),
        x86=p.endswith(('-32', '-64')),
        x86_64=p.endswith('-64'),
        osx=p.startswith('osx-'),
        unix=p.startswith(('linux-', 'osx-')),
        win=p.startswith('win-'),
        win32=bool(p == 'win-32'),
        win64=bool(p == 'win-64'),
    )

# This regex is taken from https://github.com/conda/conda_build/metadata.py
# The following function "select_lines" is also a slightly modified version of
# the function of the same name from conda_build/metadata.py
sel_pat = re.compile(r'(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2)[^\(\)]*)$')

def select_lines(data, namespace):
    lines = []

    for i, line in enumerate(data.splitlines()):
        line = line.rstrip()

        trailing_quote = ""
        if line and line[-1] in ("'", '"'):
            trailing_quote = line[-1]

        if line.lstrip().startswith('#'):
            # Don't bother with comment only lines
            continue
        m = sel_pat.match(line)
        if m:
            cond = m.group(3)
            try:
                if eval(cond, namespace, {}):
                    lines.append(m.group(1) + trailing_quote)
            except Exception as e:
                sys.exit('''\
Error: Invalid selector in meta.yaml line %d:
offending line:
%s
exception:
%s
''' % (i + 1, line, str(e)))
        else:
            lines.append(line)
    return '\n'.join(lines) + '\n'


# adapted from conda-build
def yamlize(data, directory, content_filter):
    data = content_filter(data)
    try:
        return yaml.safe_load(data)
    except yaml.error.YAMLError as e:
        if ('{{' not in data) and ('{%' not in data):
            raise UnableToParse(original=e)
        try:
            from constructor.jinja import render_jinja
        except ImportError as ex:
            raise UnableToParseMissingJinja2(original=ex)
        data = render_jinja(data, directory, content_filter)
        return yaml.load(data)


def parse(path, platform):
    try:
        with open(path) as fi:
            data = fi.read()
    except IOError:
        sys.exit("Error: could not open '%s' for reading" % path)
    directory = dirname(path)
    content_filter = partial(select_lines, namespace=ns_platform(platform))
    try:
        res = yamlize(data, directory, content_filter)
    except YamlParsingError as e:
        sys.exit(e.error_msg())

    try:
        res['version'] = str(res['version'])
    except KeyError:
        pass

    for key in list(res):
        if res[key] is None:
            del res[key]

    return res


def verify(info):
    types_key = {}  # maps key to types
    required_keys = set()
    obsolete_keys = set()
    for key, required, types, descr in KEYS:
        types_key[key] = types
        if required:
            required_keys.add(key)
        if 'Obsolete' in descr:
            obsolete_keys.add(key)

    for key in info:
        if key not in types_key:
            sys.exit("Error: unknown key '%s' in construct.yaml" % key)
        elt = info[key]
        if key in obsolete_keys:
            sys.stderr.write("Warning: key '%s' is obsolete.\n"
                             "  Its value '%s' is being ignored.\n" % (key, elt))
        types = types_key[key]
        if not isinstance(elt, types):
            sys.exit("Error: key '%s' points to %s,\n"
                     "       expected %s" % (key, type(elt), types))

    for key in required_keys:
        if key not in info:
            sys.exit("Error: Required key '%s' not found in construct.yaml" %
                     key)

    pat = re.compile(r'[\w][\w\-\.]*$')
    for key in 'name', 'version':
        value = info[key]
        if not pat.match(value) or value.endswith(('.', '-')):
            sys.exit("Error: invalid %s '%s'" % (key, value))


def generate_doc():
    print('generate_doc() is deprecated. Use scripts/make_docs.py instead')
    sys.exit(1)


if __name__ == '__main__':
    generate_doc()
