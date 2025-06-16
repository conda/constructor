# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
Logic to generate the JSON Schema for construct.yaml, using Pydantic.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from hashlib import algorithms_guaranteed
from inspect import cleandoc
from pathlib import Path
from typing import Annotated, Literal, TypeAlias, Union  # noqa

from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "data" / "construct.schema.json"
NAME_REGEX = VERSION_REGEX = r"^[a-zA-Z0-9_]([a-zA-Z0-9._-]*[a-zA-Z0-9_])?$"
ENV_NAME_REGEX = r"^[^/:# ]+$"
NonEmptyStr = Annotated[str, Field(min_length=1)]
_base_config_dict = ConfigDict(
    extra="forbid",
    use_attribute_docstrings=True,
)


class WinSignTools(StrEnum):
    AZURESIGNTOOL = "azuresigntool"
    AZURESIGNTOOL_EXE = "azuresigntool.exe"
    SIGNTOOL = "signtool"
    SIGNTOOL_EXE = "signtool.exe"


class InstallerTypes(StrEnum):
    ALL = "all"
    EXE = "exe"
    PKG = "pkg"
    SH = "sh"


class PkgDomains(StrEnum):
    ANYWHERE = "enable_anywhere"
    CURRENT_USER_HOME = "enable_currentUserHome"
    LOCAL_SYSTEM = "enable_localSystem"


class ChannelRemap(BaseModel):
    model_config: ConfigDict = _base_config_dict

    src: NonEmptyStr = ...
    "Source channel, before being mapped"
    dest: NonEmptyStr = ...
    "Target channel, after being mapped"


class ExtraEnv(BaseModel):
    model_config: ConfigDict = _base_config_dict

    specs: list[NonEmptyStr] = []
    "Which packages to install in this environment"
    environment: NonEmptyStr | None = None
    "Same as global option, for this environment"
    environment_file: NonEmptyStr | None = None
    "Same as global option, for this environment"
    channels: list[NonEmptyStr] | None = None
    """
    Solve specs using these channels; if not provided, the global
    value is used. To override inheritance, set it to an empty list.
    """
    channels_remap: list[ChannelRemap] | None = None
    """
    Same as global option, for this env; if not provided, the global
    value is used. To override inheritance, set it to an empty list.
    """
    user_requested_specs: list[NonEmptyStr] | None = None
    """
    Same as the global option, but for this env.
    If not provided, global value is _not_ used.
    """
    menu_packages: list[NonEmptyStr] | None = None
    """
    Same as the global option, but for this env.
    If not provided, global value is _not_ used.
    """
    exclude: list[NonEmptyStr] | None = None
    """
    Same as the global option, but for this env.
    See global option for notes about overrides.
    """


class BuildOutputs(StrEnum):
    "Allowed keys in 'build_outputs' setting."

    HASH = "hash"
    INFO_JSON = "info.json"
    LICENSES = "licenses"
    LOCKFILE = "lockfile"
    PKGS_LIST = "pkgs_list"


_GuaranteedAlgorithmsEnum = StrEnum(
    "GuaranteedAlgorithmsEnum",
    tuple(sorted((value, value) for value in algorithms_guaranteed)),
)


class _HashBuildOutputOptions(BaseModel):
    model_config: ConfigDict = _base_config_dict
    algorithm: _GuaranteedAlgorithmsEnum | list[_GuaranteedAlgorithmsEnum]
    "The hash algorithm. Must be one of `hashlib.algorithms_guaranteed`."


class _InfoJsonBuildOutputOptions(BaseModel):
    model_config: ConfigDict = _base_config_dict


class _PkgsListBuildOutputOptions(BaseModel):
    model_config: ConfigDict = _base_config_dict
    env: NonEmptyStr = "base"
    "Name of an environment in 'extra_envs' to be exported."


class _LockfileBuildOutputOptions(BaseModel):
    model_config: ConfigDict = _base_config_dict
    env: NonEmptyStr = "base"
    "Name of an environment in 'extra_envs' to be exported."


class _LicensesBuildOutputOptions(BaseModel):
    model_config: ConfigDict = _base_config_dict
    include_text: bool = False
    "Whether to dump the license text in the JSON. If false, only the path will be included."
    text_errors: str | None = None
    """
    How to handle decoding errors when reading the license text. Only relevant if `include_text` is
    True. Any str accepted by `open()`'s 'errors' argument is valid. See
    https://docs.python.org/3/library/functions.html#open.
    """


class HashBuildOutput(BaseModel):
    """
    The hash of the installer files. The output file is designed to work with the `shasum`
    command and thus has POSIX line endings, including on Windows
    """

    model_config: ConfigDict = _base_config_dict
    hash_: _HashBuildOutputOptions = Field(..., alias="hash")


class InfoJsonBuildOutput(BaseModel):
    "The internal `info` object, serialized to JSON. Takes no options."

    model_config: ConfigDict = _base_config_dict
    info_json: _InfoJsonBuildOutputOptions


class PkgsListBuildOutput(BaseModel):
    "The list of packages contained in a given environment."

    model_config: ConfigDict = _base_config_dict
    pkgs_list: _PkgsListBuildOutputOptions


class LockfileBuildOutput(BaseModel):
    "An `@EXPLICIT` lockfile for a given environment."

    model_config: ConfigDict = _base_config_dict
    lockfile: _LockfileBuildOutputOptions


class LicensesBuildOutput(BaseModel):
    "Generate a JSON file with the licensing details of all included packages."

    model_config: ConfigDict = _base_config_dict
    licenses: _LicensesBuildOutputOptions


BuildOutputConfigs: TypeAlias = Union[
    HashBuildOutput,
    InfoJsonBuildOutput,
    PkgsListBuildOutput,
    LockfileBuildOutput,
    LicensesBuildOutput,
]


class ConstructorConfiguration(BaseModel):
    """
    Schema for constructor.yaml input files.
    """

    model_config: ConfigDict = _base_config_dict

    schema_: Annotated[str, Field(min_length=1, alias="$schema")] = (
        "https://schemas.conda.org/constructor/v0/construct.schema.json"
    )
    """
    JSON Schema URL or path used to validate this input file.
    """
    name: Annotated[str, Field(min_length=1, pattern=NAME_REGEX)] = ...
    """
    Name of the installer. Names may be composed of letters, numbers,
    underscores, dashes, and periods, but must not begin or end with a
    dash or period.
    """
    version: Annotated[str, Field(min_length=1, pattern=VERSION_REGEX)] = ...
    """
    Version of the installer. Versions may be composed of letters, numbers,
    underscores, dashes, and periods, but must not begin or end with a
    dash or period.
    """
    channels: list[NonEmptyStr] = []
    """
    The conda channels from which packages are retrieved. At least one channel must
    be supplied, either in `channels` or `channels_remap`.

    See notes in `channels_remap` for details about local channels.
    """
    channels_remap: list[ChannelRemap] = []
    """
    A list of `src/dest` channel URL pairs. When building the installer, conda will
    use the `src` channels to solve and fetch the packages. However, the resulting
    installation will see the packages as coming from the `dest` equivalent.
    This allows an installer to be built against a different set of channels than
    will be present when the installer is actually used. Example use:

    ```yaml
    channels_remap:
      - src: file:///tmp/a3/conda-bld              # [unix]
        dest: https://repo.anaconda.com/pkgs/main  # [unix]
      - src: file:///D:/tmp/a3/conda-bld           # [win]
        dest: https://repo.anaconda.com/pkgs/main  # [win]
    ```

    At least one channel must be supplied, either in `channels` or `channels_remap`.
    """
    specs: list[NonEmptyStr] | NonEmptyStr = []
    """
    A list of package specifications; e.g. `python 2.7*`, `pyzmq` or `numpy >=1.8`.
    The specifications are identical in form and purpose to those that would be
    included in a `conda create --file` command. Packages may also be specified
    by an exact URL, e.g.,
    `https://repo.anaconda.com/pkgs/main/osx-64/openssl-1.0.2o-h26aff7b_0.tar.bz2`.
    This key can also take a `str` pointing to a requirements file with the same syntax.

    Note: `constructor` relies on `conda`'s Python API to solve the passed
    specifications. You can still set the `CONDA_SOLVER` environment variable
    to override system-wide settings for `constructor`. If you are using
    `constructor` from a non-`base` environment, make sure the
    configured solver plugin is also installed in that environment.
    """
    user_requested_specs: list[NonEmptyStr] = []
    """
    A list of package specifications to be recorded as "user-requested" for the
    initial environment in conda's history file. This information is used by newer
    versions of conda to better filter its package choices on subsequent installs;
    for example, if `python=3.6` is included, then conda will always seek versions
    of packages compatible with Python 3.6. If this option is not provided, it
    will be set equal to the value of `specs`.
    """
    virtual_specs: list[Annotated[str, Field(min_length=3, pattern=r"^__\S+.*$")]] = []
    """
    A list of virtual packages that must be satisfied at install time. Virtual
    packages must start with `__`. For example, `__osx>=11` or `__glibc>=2.24`.
    These specs are dry-run solved offline by the bundled `--conda-exe` binary.
    In SH installers, `__glibc>=x.y` and `__osx>=x.y` specs can be checked with
    Bash only. The detected version can be overriden with environment variables
    `CONDA_OVERRIDE_GLIBC` and `CONDA_OVERRIDE_OSX`, respectively. In PKG
    installers, `__osx` specs can be checked natively without the solver being
    involved as long as only `>=`, `<` or `,` are used.
    """
    exclude: list[NonEmptyStr] = []
    """
    A list of package names to be excluded after the `specs` have been resolved.
    For example, you can say that `readline` should be excluded, even though it
    is contained as a result of resolving the specs for `python 2.7`.
    """
    menu_packages: list[NonEmptyStr] | None = None
    """
    A list of packages with menu items to be installed. The packages must have
    necessary metadata in `Menu/<package name>.json`. By default, all menu items
    found in the installation will be created; supplying this list allows a
    subset to be selected instead. If an empty list is supplied, no shortcuts will
    be created.

    If all environments (`extra_envs` included) set `menu_packages` to an empty list,
    no UI options about shortcuts will be offered to the user.

    Note: This option is not fully implemented when `micromamba` is used as
    the `--conda-exe` binary. The only accepted value is an empty list (`[]`).
    """
    ignore_duplicate_files: bool = True
    """
    By default, constructor will warn you when adding packages with duplicate
    files in them. Setting this option to false will raise an error instead.
    """
    install_in_dependency_order: bool | str = Field(True, deprecated=True)
    """
    _Obsolete_. The current version of constructor relies on the standalone
    conda executable for its installation behavior. This option is now
    ignored with a warning.
    """
    environment: NonEmptyStr | None = None
    """
    Name of the environment to construct from. If this option is present, the
    `specs` argument will be ignored. Using this option allows the user to
    curate the enviromment interactively using standard `conda` commands, and
    run constructor with full confidence that the exact environment will be
    reproduced.
    """
    environment_file: NonEmptyStr | None = None
    """
    Path to an environment file (TXT or YAML) to construct from. If this option
    is present, the `specs` argument will be ignored. Instead, constructor will
    call conda to create a temporary environment, constructor will build an
    installer from that, and the temporary environment will be removed.
    This ensures that constructor is using the precise local conda configuration
    to discover and install the packages. The created environment MUST include
    `python`.

    See notes about the solver in the `specs` field for more information.
    """
    transmute_file_type: Literal[".conda"] | None = None
    """
    File type extension for the files to be transmuted into.
    If left empty, no transmuting is done.
    """
    conda_default_channels: list[NonEmptyStr] = []
    """
    If this value is provided as well as `write_condarc`, then the channels
    in this list will be included as the value of the `default_channels:`
    option in the environment's `.condarc` file. This will have an impact
    only if `conda` is included in the environmnent.
    """
    conda_channel_alias: NonEmptyStr | None = None
    """
    The channel alias that would be assumed for the created installer
    (only useful if it includes `conda`).
    """
    extra_envs: dict[Annotated[str, Field(min_length=1, pattern=ENV_NAME_REGEX)], ExtraEnv] = {}
    """
    Create more environments in addition to the default `base` provided by `specs`,
    `environment` or `environment_file`.

    Notes:
    - `ignore_duplicate_files` will always be considered `True` if `extra_envs` is in use.
    - `conda` needs to be present in the `base` environment (via `specs`)
    - If a global `exclude` option is used, it will have an effect on the environments created
      by `extra_envs` too. For example, if the global environment excludes `tk`, none of the
      extra environments will have it either. Unlike the global option, an error will not be
      thrown if the excluded package is not found in the packages required by the extra environment.
      To override the global `exclude` value, use an empty list `[]`.
    """
    register_envs: bool = True
    """
    Whether to register the environments created by the installer (both `base` and `extra_envs`)
    in `~/.conda/environments.txt`. Only compatible with conda-standalone >=23.9.
    """
    installer_filename: NonEmptyStr | None = None
    """
    The filename of the installer being created. If not supplied, a reasonable
    default will be determined by the `name`, `version`, `platform`, and `installer_type`.
    """
    installer_type: InstallerTypes | list[InstallerTypes] | None = None
    """
    The type of the installer being created. Possible values are:
    - `sh`: shell-based installer for Linux or macOS
    - `pkg`: macOS GUI installer built with Apple's `pkgbuild`
    - `exe`: Windows GUI installer built with NSIS

    The default type is `sh` on Linux and macOS, and `exe` on Windows. A special
    value of `all` builds _both_ `sh` and `pkg` installers on macOS, as well
    as `sh` on Linux and `exe` on Windows.

    """
    license_file: NonEmptyStr | None = None
    """
    Path to the license file being displayed by the installer during the install
    process. It must be plain text (.txt) for shell-based installers. For PKG,
    .txt, .rtf and .html are supported. On Windows, .txt and .rtf are supported.
    """
    keep_pkgs: bool = False
    """
    If `False`, the package cache in the `pkgs` subdirectory is removed
    when the installation process is complete. If `True`, this subdirectory and
    its contents are preserved. If `keep_pkgs` is `False`, Unix `.sh` and Windows `.exe`
    installers offer a command-line option (`-k` and `/KeepPkgCache`, respectively)
    to preserve the package cache.
    """
    batch_mode: bool = False
    """
    Only affects `.sh` installers. If `False`, the installer launches
    an interactive wizard guiding the user through the available options. If
    `True`, the installer runs automatically as if `-b` was passed.
    """
    signing_identity_name: NonEmptyStr | None = None
    """
    By default, the MacOS pkg installer isn't signed. If an identity name is specified
    using this option, it will be used to sign the installer with Apple's `productsign`.
    Note that you will need to have a certificate (usually an "Installer certificate")
    and the corresponding private key, together called an 'identity', in one of your
    accessible keychains. Common values for this option follow this format
    `Developer ID Installer: Name of the owner (XXXXXX)`.
    """
    notarization_identity_name: NonEmptyStr | None = None
    """
    If the pkg installer is going to be signed with `signing_identity_name`, you
    can also prepare the bundle for notarization. This will use Apple's `codesign`
    to sign `conda.exe`. For this, you need an "Application certificate" (different from the
    "Installer certificate" mentioned above). Common values for this option follow the format
    `Developer ID Application: Name of the owner (XXXXXX)`.
    """
    windows_signing_tool: WinSignTools | None = None
    """
    The tool used to sign Windows installers. Must be one of: azuresigntool, signtool.
    Some tools require `signing_certificate` to be set.
    Defaults to `signtool` if `signing_certificate` is set.
    Additional environment variables may need to be used to configure signing.
    See the documentation for details:
    https://conda.github.io/constructor/howto/#signing-exe-installers
    """
    signing_certificate: NonEmptyStr | None = None
    """
    On Windows only, set this key to the path of the certificate file to be used
    with the `windows_signing_tool`.
    """
    attempt_hardlinks: bool | str = Field(True, deprecated=True)
    """
    _Obsolete_. The current version of constructor relies on the standalone
    conda executable for its installation behavior. This option is now
    ignored with a warning.
    """
    write_condarc: bool = False
    """
    By default, no `.condarc` file is written. If set, a `.condarc` file is written to
    the installation directory if there are any channels or `conda_default_channels` is set.
    """
    condarc: NonEmptyStr | dict | None = None
    """
    If set, a `.condarc` file is written to the base environment containing the contents
    of this value. The value can either be a string (likely a multi-line string) or
    a dictionary, which will be converted to a YAML string for writing. _Note:_ if this
    option is used, then all other options related to the construction of a `.condarc`
    file (`write_condarc`, `conda_default_channels`, etc.) are ignored.
    """
    company: NonEmptyStr | None = None
    """
    Name of the company/entity responsible for the installer.
    """
    reverse_domain_identifier: NonEmptyStr | None = None
    """
    Unique identifier for this package, formatted with reverse domain notation. This is
    used internally in the PKG installers to handle future updates and others. If not
    provided, it will default to `io.continuum`. (MacOS only)
    """
    uninstall_name: NonEmptyStr | None = None
    """
    Application name in the Windows "Programs and Features" control panel.
    Defaults to `${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})`.
    """
    script_env_variables: dict[NonEmptyStr, str] = {}
    """
    Dictionary of additional environment variables to be made available to
    the pre_install and post_install scripts, in the form of VAR:VALUE
    pairs. These environment variables are in addition to those in the
    `post_install` section above and take precedence in the case of name
    collisions.

    On Unix the variable values are automatically single quoted, allowing
    you to supply strings with spaces, without needing to worry about
    escaping. As a consequence, string interpolation is disabled: if you
    need string interpolation, you can apply it in the
    pre_install/post_install script(s). If you need to include single quotes
    in your value, you can escape them by replacing each single quote with
    `'''`.

    On Windows, single quotes and double quotes are not supported.

    Note that the # (hash) character cannot be used as it denotes yaml
    comments for all platforms.
    """
    pre_install: NonEmptyStr | None = None
    """
    Path to a pre-install script, run after the package cache has been set, but
    before the files are linked to their final locations. As a result, you should
    only rely on tools known to be available on most systems (e.g. `bash`, `cmd`,
    etc). See `post_install` for information about available environment variables.
    """
    pre_install_desc: NonEmptyStr | None = None
    """
    A description of the purpose of the supplied `pre_install` script. If this
    string is supplied and non-empty, then the Windows and macOS GUI installers
    will display it along with a checkbox to enable or disable the execution of the
    script. If this string is not supplied, it is assumed that the script
    is compulsory and the option to disable it will not be offered.

    This option has no effect on `SH` installers.
    """
    post_install: NonEmptyStr | None = None
    """
    Path to a post-install script. Some notes:

    - For Unix `.sh` installers, the shebang line is respected if present;
      otherwise, the script is run by the POSIX shell `sh`. Note that the use
      of a shebang can reduce the portability of the installer. The
      installation path is available as `${PREFIX}`. Installer metadata is
      available in the `${INSTALLER_NAME}`, `${INSTALLER_VER}`, `${INSTALLER_PLAT}`
      environment variables. `${INSTALLER_TYPE}` is set to `SH`.
      `${INSTALLER_UNATTENDED}` will be `"1"` in batch mode (`-b`), `"0"` otherwise.
    - For PKG installers, the shebang line is respected if present;
      otherwise, `bash` is used. The same variables mentioned for `sh`
      installers are available here. `${INSTALLER_TYPE}` is set to `PKG`.
      `${INSTALLER_UNATTENDED}` will be `"1"` for command line installs, `"0"` otherwise.
    - For Windows `.exe` installers, the script must be a `.bat` file.
      Installation path is available as `%PREFIX%`. Metadata about
      the installer can be found in the `%INSTALLER_NAME%`, `%INSTALLER_VER%`,
      `%INSTALLER_PLAT%` environment variables. `%INSTALLER_TYPE%` is set to `EXE`.
      `%INSTALLER_UNATTENDED%` will be `"1"` in silent mode (`/S`), `"0"` otherwise.

    If necessary, you can activate the installed `base` environment like this:

    - Unix: `. "$PREFIX/etc/profile.d/conda.sh" && conda activate "$PREFIX"`
    - Windows: `call "%PREFIX%\\Scripts\\activate.bat"`
    """
    post_install_desc: NonEmptyStr | None = None
    """
    A description of the purpose of the supplied `post_install` script. If this
    string is supplied and non-empty, then the Windows and macOS GUI installers
    will display it along with a checkbox to enable or disable the execution of the
    script. If this string is not supplied, it is assumed that the script
    is compulsory and the option to disable it will not be offered.

    This option has no effect on `SH` installers.
    """
    pre_uninstall: NonEmptyStr | None = None
    """
    Path to a pre uninstall script. This is only supported on Windows,
    and must be a `.bat` file. Installation path is available as `%PREFIX%`.
    Metadata about the installer can be found in the `%INSTALLER_NAME%`,
    `%INSTALLER_VER%`, `%INSTALLER_PLAT%` environment variables.
    `%INSTALLER_TYPE%` is set to `EXE`.
    """
    default_prefix: NonEmptyStr | None = None
    """
    Set default install prefix. On Linux, if not provided, the default prefix
    is `${HOME}/<NAME>` (or, if `HOME` is not set, `/opt/<NAME>`). On Windows,
    this is used only for "Just Me" installations; for "All Users" installations,
    use the `default_prefix_all_users` key. If not provided, the default prefix
    is `%USERPROFILE%\\<NAME>`. Environment variables will be expanded at
    install time.
    """
    default_prefix_domain_user: NonEmptyStr | None = None
    """
    Set default installation prefix for domain users. If not provided, the
    installation prefix for domain users will be `%LOCALAPPDATA%\\<NAME>`.
    By default, it is different from the `default_prefix` value to avoid installing
    the distribution into the roaming profile. Environment variables will be expanded
    at install time. Windows only.
    """
    default_prefix_all_users: NonEmptyStr | None = None
    """
    Set default installation prefix for All Users installations. If not provided,
    the installation prefix will be `%ALLUSERSPROFILE%\\<NAME>`.
    Environment variables will be expanded at install time. Windows only.
    """
    default_location_pkg: NonEmptyStr | None = None
    """
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
    """
    pkg_domains: dict[PkgDomains, bool] = {"enable_anywhere": True, "enable_currentUserHome": False}
    """
    The domains the package can be installed into. For a detailed explanation, see:
    https://developer.apple.com/library/archive/documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html
    constructor defaults to `enable_anywhere=true` and `enable_currentUserHome=true`.
    `enable_localSystem` should not be set to true unless `default_location_pkg` is set as well.
    macOS only.
    """
    pkg_name: NonEmptyStr | None = None
    """
    Internal identifier for the installer. This is used in the build prefix and will
    determine part of the default location path. Combine with `default_location_pkg`
    for more flexibility. If not provided, the value of `name` will be used.  (macOS only)
    """
    install_path_exists_error_text: NonEmptyStr | None = None
    """
    Error message that will be shown if the installation path already exists.
    You cannot use double quotes or newlines. The placeholder `{CHOSEN_PATH}` is
    available and set to the destination causing the error. Defaults to:

    > '{CHOSEN_PATH}' already exists. Please, relaunch the installer and
    choose another location in the Destination Select step.

    (PKG only)
    """
    progress_notifications: bool = False
    """
    Whether to show UI notifications on PKG installers. On large installations,
    the progress bar reaches ~90% very quickly and stays there for a long time.
    This might look like the installer froze. This option enables UI notifications
    so the user receives updates after each command executed by the installer.
    (macOS only)
    """
    welcome_image: str | None = None
    """
    Path to an image in any common image format (`.png`, `.jpg`, `.tif`, etc.)
    to be used as the welcome image for the Windows and PKG installers.
    The image is re-sized to 164 x 314 pixels on Windows and 1227 x 600 on macOS.
    By default, an image is automatically generated on Windows. On macOS, Anaconda's
    logo is shown if this key is not provided. If you don't want a background on
    PKG installers, set this key to `""` (empty string).
    """
    header_image: str | None = None
    """
    Like `welcome_image` for Windows, re-sized to 150 x 57 pixels.
    """
    icon_image: str | None = None
    """
    Like `welcome_image` for Windows, re-sized to 256 x 256 pixels.
    """
    default_image_color: Literal["red", "green", "blue", "yellow"] = "blue"
    """
    The color of the default images (when not providing explicit image files)
    used on Windows.
    """
    welcome_image_text: NonEmptyStr | None = None
    """
    If `welcome_image` is not provided, use this text when generating the image
    (Windows and PKG only). Defaults to `name` on Windows.
    """
    header_image_text: NonEmptyStr | None = None
    """
    If `header_image` is not provided, use this text when generating the image
    (Windows only). Defaults to `name`.
    """
    initialize_conda: bool = True
    """
    Add an option to the installer so the user can choose whether to run `conda init`
    after the installation (Unix), or to add certain subdirectories of the installation
    to PATH (Windows). See also `initialize_by_default`.
    """
    initialize_by_default: bool | None = None
    """
    Default value for the option added by `initialize_conda`. The default
    is true for GUI installers (EXE, PKG) and false for shell installers. The user
    is able to change the default during interactive installation. NOTE: For Windows,
    `AddToPath` is disabled when `InstallationType=AllUsers`.

    Only applies if `initialize_conda` is true.
    """
    add_condabin_to_path: bool = True
    """
    Add an option to the installer so the user can choose whether to add the `condabin/`
    directory to PATH. Only applicable if `conda` is part of the installation.
    On Linux and macOS, `conda >=25.5.0` is required. See also `add_condabin_to_path_default`.
    """
    add_condabin_to_path_default: bool | None = None
    """
    Default value for the option added by `add_condabin_to_path`. The default
    is true for GUI installers (EXE, PKG) and false for shell installers. The user
    is able to change the default during interactive installation. NOTE: For Windows,
    `AddCondabinToPath` is disabled when `InstallationType=AllUsers`.

    Only applies if `add_condabin_to_path` is true.
    """
    register_python: bool = True
    """
    Whether to offer the user an option to register the installed Python instance as the
    system's default Python. (Windows only)
    """
    register_python_default: bool | None = False
    """
    Default choice for whether to register the installed Python instance as the
    system's default Python. The user is still able to change this during
    interactive installation. (Windows only).

    Only applies if `register_python` is true.
    """
    check_path_length: bool | None = None
    """
    Check the length of the path where the distribution is installed to ensure nodejs
    can be installed.  Raise a message to request shorter paths (less than 46 character)
    or enable long paths on windows > 10 (require admin right). Default is True. (Windows only).
    """
    check_path_spaces: bool = True
    """
    Check if the path where the distribution is installed contains spaces.
    To allow installations with spaces, change to False. Note that:

    - A recent conda-standalone (>=22.11.1) or equivalent is needed for full support.
    - `conda` cannot be present in the `base` environment
    """
    nsis_template: NonEmptyStr | None = None
    """
    Path to an NSIS template file to use instead of the default template. (Windows only)
    """
    welcome_file: NonEmptyStr | None = None
    """
    If `installer_type` is `pkg` on macOS, this message will be
    shown before the license information, right after the introduction.
    File can be plain text (.txt), rich text (.rtf) or HTML (.html). If
    both `welcome_file` and `welcome_text` are provided, `welcome_file` takes precedence.

    If the installer is for Windows and the welcome file type is nsi,
    it will use the nsi script to add in extra pages before the installer
    begins the installation process.
    """
    welcome_text: str | None = None
    """
    If `installer_type` is `pkg` on macOS, this message will be
    shown before the license information, right after the introduction.
    If this key is missing, it defaults to a message about Anaconda Cloud.
    You can disable it altogether so it defaults to the system message
    if you set this key to `""` (empty string).
    """
    readme_file: NonEmptyStr | None = None
    """
    If `installer_type` is `pkg` on macOS, this message will be
    shown before the license information, right after the welcome screen.
    File can be plain text (.txt), rich text (.rtf) or HTML (.html). If
    both `readme_file` and `readme_text` are provided, `readme_file` takes precedence.
    """
    readme_text: str | None = None
    """
    If `installer_type` is `pkg` on macOS, this message will be
    shown before the license information, right after the welcome screen.
    If this key is missing, it defaults to a message about Anaconda Cloud.
    You can disable it altogether if you set this key to `""` (empty string).
    """
    post_install_pages: NonEmptyStr | list[NonEmptyStr] | None = None
    """
    Adds extra pages to the installers to be shown after installation.

    For PKG installers, these can be compiled `installer` plug-ins or
    directories containing an Xcode project. In the latter case,
    constructor will try and compile the project file using `xcodebuild`.

    For Windows, the extra pages must be `.nsi` files.
    They will be inserted as-is before the conclusion page.
    """
    conclusion_file: NonEmptyStr | None = None
    """
    If `installer_type` is `pkg` on macOS, this message will be
    shown at the end of the installer upon success. File can be
    plain text (.txt), rich text (.rtf) or HTML (.html). If both
    `conclusion_file` and `conclusion_text` are provided,
    `conclusion_file` takes precedence.

    If the installer is for Windows, the file type must be nsi.
    """
    conclusion_text: str | None = None
    """
    A message that will be shown at the end of the installer upon success.
    The behaviour is slightly different across installer types:
    - PKG: If this key is missing, it defaults to a message about Anaconda Cloud.
      You can disable it altogether so it defaults to the system message if you set this
      key to `""` (empty string).
    - EXE: The first line will be used as a title. The following lines will be used as text.
    """
    extra_files: list[NonEmptyStr | dict[NonEmptyStr, NonEmptyStr]] = []
    """
    Extra, non-packaged files that should be added to the installer. If provided as relative
    paths, they will be considered relative to the directory where `construct.yaml` is.
    This setting can be passed as a list of:
    - `str`: each found file will be copied to the root prefix
    - `Mapping[str, str]`: map of path in disk to path in prefix.
    """
    temp_extra_files: list[NonEmptyStr | dict[NonEmptyStr, NonEmptyStr]] = []
    """
    Temporary files that could be referenced in the installation process (i.e. customized
    `welcome_file` and `conclusion_file`). Should be a list of
    file paths, relative to the directory where `construct.yaml` is. In Windows, these
    files will be copied into a temporary folder, the NSIS `$PLUGINSDIR`, during
    the install process (Windows only).

    Supports the same values as `extra_files`.
    """
    build_outputs: list[BuildOutputs | BuildOutputConfigs] = Field(
        # Need a Field to render the description docstring dynamically
        [],
        description=cleandoc(
            """
            Additional artifacts to be produced after building the installer.
            It expects either a list of strings or single-key dictionaries.

            Allowed strings / keys: {}.
            """.format(", ".join([f"`{v}`" for v in BuildOutputs.__members__.values()])),
        ),
    )
    uninstall_with_conda_exe: bool | None = None
    """
    Use the standalone binary to perform the uninstallation on Windows.
    Requires conda-standalone 24.11.0 or newer.
    """


def fix_descriptions(obj):
    for key, value in obj.items():
        if isinstance(value, dict):
            obj[key] = fix_descriptions(value)
        if key == "description" and isinstance(value, str):
            codeblocks = re.findall(r"```.*```", value, flags=re.MULTILINE | re.DOTALL)
            for i, codeblock in enumerate(codeblocks):
                value = value.replace(codeblock, f"__CODEBLOCK_{i}__")
            value = (
                value.replace("\n\n", "__NEWLINE__")
                .replace("\n-", "__NEWLINE__-")
                .replace("\n", " ")
                .replace("  ", " ")
                .replace("__NEWLINE__", "\n")
            )
            for i, codeblock in enumerate(codeblocks):
                value = value.replace(f"__CODEBLOCK_{i}__", codeblock)
            obj[key] = value

    return obj


def checks():
    from constructor.build_outputs import OUTPUT_HANDLERS

    if sorted(BuildOutputs.__members__.values()) != sorted(OUTPUT_HANDLERS.keys()):
        print(sorted(BuildOutputs.__members__.values()))
        print("!=")
        print(sorted(OUTPUT_HANDLERS.keys()))
        raise AssertionError(
            "Need to sync constructor.build_outputs.OUTPUT_HANDLERS "
            "with constructor._schema.BuildOutputs enum."
        )


def dump_schema():
    model = ConstructorConfiguration(name="doesnotmatter", version="0.0.0")
    obj = model.model_json_schema()
    obj = fix_descriptions(obj)
    obj["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    SCHEMA_PATH.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    print(json.dumps(obj, sort_keys=True, indent=2))


if __name__ == "__main__":
    checks()
    dump_schema()
