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

See notes in `channels_remap` for details about local channels.
'''),

    ('channels_remap',         False, list, '''
A list of `src/dest` channel pairs. When building the installer, conda will
use the `src` channels to solve and fetch the packages. However, the resulting
installation will see the packages as coming from the `dest` equivalent.
This allows an installer to be built against a different set of channels than
will be present when the installer is actually used. Example use:

```yaml
channels_remap:
  - src: file:///tmp/a3/conda-bld              # [unix]
    dest: https://repo.anaconda.com/pkgs/main  # [unix]
  - src: file:///D:/tmp/a3/conda-bld           # [win]
    dest: https://repo.anaconda.com/pkgs/main  # [unix]
```

At least one channel must be supplied, either in `channels` or `channels_remap`.
'''),

    ('specs',                  False, (list, str), '''
A list of package specifications; e.g. `python 2.7*`, `pyzmq` or `numpy >=1.8`.
The specifications are identical in form and purpose to those that would be
included in a `conda create --file` command. Packages may also be specified
by an exact URL; e.g.,
`https://repo.anaconda.com/pkgs/main/osx-64/openssl-1.0.2o-h26aff7b_0.tar.bz2`.

The specs will be solved with the solver configured for your `base` conda installation,
if any. Starting with conda 22.11, this behavior can be overriden with the
`CONDA_SOLVER` environment variable.
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
By default, constructor will warn you when adding packages with duplicate
files in them. Setting this option to false will raise an error instead.
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
and install the packages. The created environment MUST include `python`.

Read notes about the solver in the `specs` field.
'''),

    ('transmute_file_type', False, str, '''
File type extension for the files to be transmuted into. Currently supports
only '.conda'. See conda-package-handling for supported extension names.
If left empty, no transmuting is done.
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

    ('extra_envs', False, (dict,), '''
Create more environments in addition to the default `base` provided by `specs`,
`environment` or `environment_file`. This should be a map of `str` (environment
name) to a dictionary of options:
- `specs` (list of str): which packages to install in that environment
- `environment` (str): same as global option, for this env
- `environment_file` (str): same as global option, for this env
- `channels` (list of str): using these channels; if not provided, the global
  value is used. To override inheritance, set it to an empty list.
- `channels_remap` (list of str): same as global option, for this env;
  if not provided, the global value is used. To override inheritance, set it to
  an empty list.
- `user_requested_specs` (list of str): same as the global option, but for this env;
  if not provided, global value is _not_ used

Notes:
- `ignore_duplicate_files` will always be considered `True` if `extra_envs` is in use.
- `conda` needs to be present in the `base` environment (via `specs`)
- support for `menu_packages` is planned, but not possible right now. For now, all packages
  in an `extra_envs` config will be allowed to create their shortcuts.
- If a global `exclude` option is used, it will have an effect on the environments created
  by `extra_envs` too. For example, if the global environment excludes `tk`, none of the
  extra environments will have it either. Unlike the global option, an error will not be
  thrown if the excluded package is not found in the packages required by the extra environment.
  To override the global `exclude` value, use an empty list `[]`.
'''),

    ('installer_filename',     False, str, '''
The filename of the installer being created. If not supplied, a reasonable
default will determined by the `name`, `version`, platform, and installer type.
'''),

    ('installer_type',     False, (str, list), '''
The type of the installer being created.  Possible values are:
- `sh`: shell-based installer for Linux or macOS;
- `pkg`: macOS GUI installer built with Apple's `pkgbuild`
- `exe`: Windows GUI installer built with NSIS

The default type is `sh` on Linux and macOS, and `exe` on Windows. A special
value of `all` builds _both_ `sh` and `pkg` installers on macOS, as well
as `sh` on Linux and `exe` on Windows.

Notes for silent mode `/S` on Windows EXEs: 
- NSIS Silent mode will not print any error message, but will silently abort the installation.
  If needed, [NSIS log-builds][nsis-log] can be used to print to `%PREFIX%\\install.log`, which can be 
  searched for `::error::` strings. Pre- and post- install scripts will only throw an error
  if the environment variable `NSIS_SCRIPTS_RAISE_ERRORS` is set.
- The `/D` flag can be used to specify the target location. It must be the last argument in
  the command and should NEVER be quoted, even if it contains spaces. For example:
  `CMD.EXE /C START /WAIT myproject.exe /S /D=C:\\path with spaces\\my project`.

[nsis-log]: https://nsis.sourceforge.io/Special_Builds
'''),

    ('license_file',           False, str, '''
Path to the license file being displayed by the installer during the install
process. It must be plain text (.txt) for shell-based installers. On PKG,
.txt, .rtf and .html are supported. On Windows, .txt and .rtf are supported.
'''),

    ('keep_pkgs',              False, bool, '''
If `False` (default), the package cache in the `pkgs` subdirectory is removed
when the installation process is complete. If `True`, this subdirectory and
its contents are preserved. If `keep_pkgs` is `False`, Unix `.sh` and Windows `.msi`
installers offer a command-line option (`-k` and `/KeepPkgCache`, respectively)
to preserve the package cache.
'''),

    ('batch_mode',             False, bool, '''
Only affects ``.sh`` installers. If ``False`` (default), the installer launches
an interactive wizard guiding the user through the available options. If
``True``, the installer runs automatically as if ``-b`` was passed.
'''),

    ('signing_identity_name',  False, str, '''
By default, the MacOS pkg installer isn't signed. If an identity name is specified
using this option, it will be used to sign the installer with Apple's `productsign`.
Note that you will need to have a certificate (usually an "Installer certificate")
and the corresponding private key, together called an 'identity', in one of your
accessible keychains. Common values for this option follow this format
`Developer ID Installer: Name of the owner (XXXXXX)`.
'''),

    ('notarization_identity_name', False, str, '''
If the pkg installer is going to be signed with `signing_identity_name`, you
can also prepare the bundle for notarization. This will use Apple's `codesign`
to sign `conda.exe`. For this, you need an "Application certificate" (different from the
"Installer certificate" mentioned above). Common values for this option follow the format
`Developer ID Application: Name of the owner (XXXXXX)`.
'''),

    ('signing_certificate',  False, str, '''
On Windows only, set this key to the path of a PFX certificate to be used with `signtool`.
Additional environment variables can be used to configure this step, namely:

- `CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD` (password to unlock the certificate, if needed)
- `CONSTRUCTOR_SIGNTOOL_PATH` (absolute path to `signtool.exe`, in case is not in `PATH`)
- `CONSTRUCTOR_SIGNTOOL_TIMESTAMP_SERVER_URL` (custom RFC 3161 timestamping server, default is
http://timestamp.sectigo.com)
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
file (`write_condarc`, `conda_default_channels`, etc.) are ignored.
'''),

    ('company',                False, str, '''
Name of the company/entity who is responsible for the installer.
'''),

    ('reverse_domain_identifier', False, str, '''
Unique identifier for this package, formatted with reverse domain notation. This is
used internally in the PKG installers to handle future updates and others. If not
provided, it will default to `io.continuum`. (MacOS only)
'''),

    ('uninstall_name',         False, str, '''
Application name in the Windows "Programs and Features" control panel.
Defaults to `${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})`.
'''),

    ('pre_install',            False, str, '''
Path to a pre-install script, run after the package cache has been set, but
before the files are linked to their final locations. As a result, you should
only rely on tools known to be available on most systems (e.g. `bash`, `cmd`,
etc). See `post_install` for information about available environment variables.
'''),

    ('pre_install_desc',      False, str, '''
A description of the purpose of the supplied `pre_install` script. If this
string is supplied and non-empty, then the Windows and macOS GUI installers
will display it along with checkbox to enable or disable the execution of the
script. If this string is not supplied, it is assumed that the script
is compulsory and the option to disable it will not be offered.

This option has no effect on `SH` installers.
'''),

    ('post_install',           False, str, '''
Path to a post-install script. Some notes:

- For Unix `.sh` installers, the shebang line is respected if present;
  otherwise, the script is run by the POSIX shell `sh`. Note that the use
  of a shebang can reduce the portability of the installer. The
  installation path is available as `${PREFIX}`. Installer metadata is
  available in the `${INSTALLER_NAME}`, `${INSTALLER_VER}`, `${INSTALLER_PLAT}`
  environment variables. `${INSTALLER_TYPE}` is set to `SH`.
- For PKG installers, the shebang line is respected if present;
  otherwise, `bash` is used. The same variables mentioned for `sh` 
  installers are available here. `${INSTALLER_TYPE}` is set to `PKG`.
- For Windows `.exe` installers, the script must be a `.bat` file.
  Installation path is available as `%PREFIX%`. Metadata about
  the installer can be found in the `%INSTALLER_NAME%`, `%INSTALLER_VER%`,
  `%INSTALLER_PLAT%` environment variables. `%INSTALLER_TYPE%` is set to `EXE`.

If necessary, you can activate the installed `base` environment like this:

- Unix: `source "$PREFIX/etc/profile.d/conda.sh" && conda activate "$PREFIX"`
- Windows: `call "%PREFIX%\\Scripts\\activate.bat"`
'''),

    ('post_install_desc',      False, str, '''
A description of the purpose of the supplied `post_install` script. If this
string is supplied and non-empty, then the Windows and macOS GUI installers
will display it along with checkbox to enable or disable the execution of the
script. If this string is not supplied, it is assumed that the script
is compulsory and the option to disable it will not be offered.

This option has no effect on `SH` installers.
'''),

    ('pre_uninstall',          False, str, '''
Path to a pre uninstall script. This is only supported for on Windows,
and must be a `.bat` file. Installation path is available as `%PREFIX%`. 
Metadata about the installer can be found in the `%INSTALLER_NAME%`,
`%INSTALLER_VER%`, `%INSTALLER_PLAT%` environment variables. 
`%INSTALLER_TYPE%` is set to `EXE`.
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

    ('default_location_pkg', False, str, '''
Default installation subdirectory in the chosen volume. In PKG installers,
default installation locations are configured differently. The user can choose
between a "Just me" installation (which would result in `~/<PKG_NAME>`) or another
volume (which defaults to `<VOLUME>/<PKG_NAME>`). If you want a different default,
you can add a middle component with this option, let's call it `location`. It would
result in these default values: `~/<LOCATION>/<PKG_NAME>` for "Just me",
`<VOLUME>/<LOCATION>/<PKG_NAME>` for custom volumes. For example, setting this option
to `/Library` in a "Just me" installation will give you `~/Library/<PKG_NAME>`.
Internally, this is passed to `pkgbuild --install-location`.
macOS only.
'''),

    ('pkg_name', False, str, '''
Internal identifier for the installer. This is used in the build prefix and will
determine part of the default location path. Combine with `default_location_pkg`
for more flexibility. If not provided, the value of `name` will be used.  (MacOS only)
'''),

    ('install_path_exists_error_text', False, str, '''
Error message that will be shown if the installation path already exists.
You cannot use double quotes or newlines. The placeholder `{CHOSEN_PATH}` is
available and set to the destination causing the error. Defaults to:

> '{CHOSEN_PATH}' already exists. Please, relaunch the installer and
> choose another location in the Destination Select step.

(MacOS only)
'''),

    ('progress_notifications', False, bool, '''
Whether to show UI notifications on PKG installers. On large installations,
the progress bar reaches ~90% very quickly and stays there for a long time.
This might look like the installer froze. This option enables UI notifications
so the user receives updates after each command executed by the installer.   
(macOS only) 
'''),

    ('welcome_image',          False, str, '''
Path to an image in any common image format (`.png`, `.jpg`, `.tif`, etc.)
to be used as the welcome image for the Windows and PKG installers.
The image is re-sized to 164 x 314 pixels on Windows and 1227 x 600 on Macos.
By default, an image is automatically generated on Windows. On MacOS, Anaconda's
logo is shown if this key is not provided. If you don't want a background on
PKG installers, set this key to `""` (empty string).
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
(Windows and PKG only). Defaults to `name` on Windows.
'''),

    ('header_image_text',      False, str, '''
If `header_image` is not provided, use this text when generating the image
(Windows only). Defaults to `name`.
'''),

    ('initialize_conda',     False, bool, '''
Add an option to the installer so the user can choose whether to run `conda init`
after the install. See also `initialize_by_default`.
'''),

    ('initialize_by_default',    False, bool, '''
Whether to add the installation to the PATH environment variable. The default
is true for GUI installers (msi, pkg) and False for shell installers. The user
is able to change the default during interactive installation. NOTE: For Windows,
`AddToPath` is disabled when `InstallationType=AllUsers`.
'''),

    ('register_python',  False, bool, '''
Whether to offer the user an option to register the installed Python instance as the
system's default Python. (Windows only)
'''),

    ('register_python_default',  False, bool, '''
Default choice for whether to register the installed Python instance as the
system's default Python. The user is still able to change this during
interactive installation. (Windows only).
'''),

    ('check_path_length',     False, bool, '''
Check the length of the path where the distribution is installed to ensure nodejs
can be installed.  Raise a message to request shorter path (less than 46 character)
or enable long path on windows > 10 (require admin right). Default is True. (Windows only).

Read notes about the particularities of Windows silent mode `/S` in the
`installer_type` documentation.
'''),

    ('check_path_spaces',     False, bool, '''
Check if the path where the distribution is installed contains spaces. Default is True.
To allow installations with spaces, change to False. Note that:

- A recent conda-standalone (>=22.11.1) or equivalent is needed for full support.
- `conda` cannot be present in the `base` environment

Read notes about the particularities of Windows silent mode `/S` in the
`installer_type` documentation.
'''),

    ('nsis_template',           False, str, '''
If `nsis_template` is not provided, constructor uses its default
NSIS template. For more complete customization for the installation experience,
provide an NSIS template file. (Windows only).
'''),

    ('welcome_file', False, str, '''
If `installer_type` is `pkg` on MacOS, this message will be
shown before the license information, right after the introduction.
File can be plain text (.txt), rich text (.rtf) or HTML (.html). If
both `welcome_file` and `welcome_text` are provided, `welcome_file` takes precedence.
(MacOS only).
'''),

    ('welcome_text', False, str, '''
If `installer_type` is `pkg` on MacOS, this message will be
shown before the license information, right after the introduction.
If this key is missing, it defaults to a message about Anaconda Cloud.
You can disable it altogether so it defaults to the system message
if you set this key to `""` (empty string).
(MacOS only).
'''),

    ('readme_file', False, str, '''
If `installer_type` is `pkg` on MacOS, this message will be
shown before the license information, right after the welcome screen.
File can be plain text (.txt), rich text (.rtf) or HTML (.html). If
both `readme_file` and `readme_text` are provided, `readme_file` takes precedence.
(MacOS only).
'''),

    ('readme_text', False, str, '''
If `installer_type` is `pkg` on MacOS, this message will be
shown before the license information, right after the welcome screen.
If this key is missing, it defaults to a message about Anaconda Cloud.
You can disable it altogether if you set this key to `""` (empty string).
(MacOS only).
'''),

    ('conclusion_file', False, str, '''
If `installer_type` is `pkg` on MacOS, this message will be
shown at the end of the installer upon success. File can be
plain text (.txt), rich text (.rtf) or HTML (.html). If both
`conclusion_file` and `conclusion_text` are provided,
`conclusion_file` takes precedence. (MacOS only).
'''),

    ('conclusion_text', False, str, '''
A message that will be shown at the end of the installer upon success.
The behaviour is slightly different across installer types:
- PKG: If this key is missing, it defaults to a message about Anaconda Cloud.
  You can disable it altogether so it defaults to the system message if you set this
  key to `""` (empty string).
- EXE: The first line will be used as a title. The following lines will be used as text.
(macOS PKG and Windows only).
'''),

    ('extra_files', False, (list), '''
Extra, non-packaged files that should be added to the installer. If provided as relative
paths, they will be considered relative to the directory where `construct.yaml` is.
This setting can be passed as a list of:
- `str`: each found file will be copied to the root prefix
- `Mapping[str, str]`: map of path in disk to path in prefix.
'''),

    ('build_outputs', False, list, '''
Additional artifacts to be produced after building the installer.
It expects either a list of strings or single-key dictionaries:
Allowed keys are:
- `info.json`: The internal `info` object, serialized to JSON. Takes no options.
- `pkgs_list`: The list of packages contained in a given environment. Options:
    - `env` (optional, default=`base`): Name of an environment in `extra_envs` to export.
- `licenses`: Generate a JSON file with the licensing details of all included packages. Options:
    - `include_text` (optional bool, default=`False`): Whether to dump the license text in the JSON.
      If false, only the path will be included.
    - `text_errors` (optional str, default=`None`): How to handle decoding errors when reading the
      license text. Only relevant if include_text is True. Any str accepted by open()'s 'errors' 
      argument is valid. See https://docs.python.org/3/library/functions.html#open.
''')
]


_EXTRA_ENVS_SCHEMA = {
    "specs": (list, tuple),
    "environment": (str,),
    "environment_file": (str,),
    "channels": (list, tuple),
    "channels_remap": (list, tuple),
    "user_requested_specs": (list, tuple),
    "exclude": (list, tuple),
    # TODO: we can't support menu_packages for extra envs yet
    # will implement when the PR for new menuinst lands
    # "menu_packages": (list, tuple),
}


def generate_key_info_list():
    key_info_list = []
    for key_info in KEYS:
        type_names = {str: 'string', list: 'list', dict: 'dictionary', bool: 'boolean'}
        key_types = key_info[2]
        if not isinstance(key_types, (tuple, list)):
            key_types = key_types,
        plural = 's' if len(key_types) > 1 else ''
        key_types = ', '.join(type_names.get(k, '') for k in key_types)
        required = 'yes' if key_info[1] else 'no'

        if key_info[3] == 'XXX':
            print("Not including %s because the skip sentinel ('XXX') is set" % key_info[0])
            continue

        key_info_list.append((key_info[0], required, key_types, key_info[3], plural))
    return key_info_list


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
        return yaml.load(data, Loader=yaml.SafeLoader)


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

    for env_name, env_data in info.get("extra_envs", {}).items():
        disallowed = ('/', ' ', ':', '#')
        if any(character in env_name for character in disallowed):
            sys.exit(
                f"Environment names (keys in 'extra_envs') cannot contain any of {disallowed}. "
                f"You tried to use: {env_name}"
                )
        for key, value in env_data.items():
            if key not in _EXTRA_ENVS_SCHEMA:
                sys.exit(f"Key '{key}' not supported in 'extra_envs'.")
            types = _EXTRA_ENVS_SCHEMA[key]
            if not isinstance(value, types):
                types_str = " or ".join([type_.__name__ for type_ in types])
                sys.exit(f"Value for 'extra_envs.{env_name}.{key}' "
                         f"must be an instance of {types_str}")


def generate_doc():
    print('generate_doc() is deprecated. Use scripts/make_docs.py instead')
    sys.exit(1)


if __name__ == '__main__':
    generate_doc()
