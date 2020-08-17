
# The `construct.yaml` specification format

The `construct.yaml` file is the primary mechanism for controlling
the output of the Constructor package. The file contains a list of
key/value pairs in the standard [YAML](https://yaml.org/) format.
Each configuration option is listed in its own subsection below.

Constructor employs the Selector enhancement of the YAML format
first employed in the
[conda-build](https://docs.conda.io/projects/conda-build/en/latest/)
project. Selectors are specially formatted YAML comments that Constructor
uses to customize the specification for different platforms. The precise
syntax for selectors is described in
[this section](https://docs.conda.io/projects/conda-build/en/latest/resources/define-metadata.html#preprocessing-selectors)
of the `conda-build` documentation. The list of selectors available
for use in Constructor specs is given in the section
[Available selectors](#Available-selectors) below.


## `name`

required: True

argument type: `str`

Name of the installer.  May also contain uppercase letter.  The installer
name is independent of the names of any of the conda packages the installer
is composed of.

## `version`

required: True

argument type: `str`

Version of the installer.  Just like the installer name, this version
is independent of any conda package versions contained in the installer.

## `channels`

required: False

argument type: `list`

The conda channels from which packages are retrieved, in priority order,
when using the `specs`/`packages` to describe the environment.

## `channels_remap`

required: False

argument type: `list`

List of `(src, dest)` channels, from which, channels from `src` are also
considered while running solver, but are replaced by corresponding values from
dest when writing `urls{,.txt}`. Example use:
```
channels_remap:
  -
      src: file:///tmp/a3/conda-bld
      dest: https://repo.anaconda.com/pkgs/main
  -
      src: file:///tmp/r/conda-bld
      dest: https://repo.anaconda.com/pkgs/r
```

## `specs`

required: False

argument types: `list`, `str`

This configuration can be supplied as either a list or a string:
- If a list is supplied, each entry of the list contains a `conda`-compatible
  package specification; e.g., `python 2.7*`, `pyzmq` or `numpy >=1.8`. The
  format is the same as would be supplied to a `conda create` / `conda install` command.
- If a string is supplied, it is assumed to represent a filename from which
  the package list is to be read. This file should have exactly one specification
  per line, except that lines beginning with `#` are ignored.

In either format, packages may be specified with their entire URL; e.g.,
`https://repo.anaconda.com/pkgs/main/osx-64/openssl-1.0.2o-h26aff7b_0.tar.bz2`.

## `user_requested_specs`

required: False

argument types: `list`, `str`

List of package specifications to be recorded as "user-requested" for the
initial environment in conda's history file. If not given, user-requested
specs will fall back to 'specs'.

## `exclude`

required: False

argument type: `list`

List of package names to be excluded, after the '`specs` have been resolved.
For example, you can say that `readline` should be excluded, even though it
is contained as a result of resolving the specs for `python 2.7`.

## `menu_packages`

required: False

argument type: `list`

Packages for menu items will be installed (if the conda package contains the
necessary metadata in "Menu/<package name>.json").  Menu items are currently
only supported on Windows.  By default, all menu items will be installed.

## `ignore_duplicate_files`

required: False

argument type: `bool`

By default, constructor will error out when adding packages with duplicate
files in them. Enable this option to warn instead and continue.

## `install_in_dependency_order`

required: False

argument type: `bool`

By default the conda packages included in the created installer are installed
in alphabetical order, Python is always installed first for technical
reasons.  Using this option, the packages are installed in their dependency
order (unless the explicit list in `packages` is used).

## `environment`

required: False

argument type: `str`

Name of the environment to construct from. If this option is present and
non-empty, specs will be ignored.

## `environment_file`

required: False

argument type: `str`

Path to an environment file to construct from. If this option is present,
a temporary environment will be created, constructor will build an installer
from that, and then the temporary environment will be removed. This ensures
that constructor and conda use the same mechanism to discover and install
the packages. If this option is present and non-empty, specs will be ignored.

## `conda_default_channels`

required: False

argument type: `list`

You can list conda channels here which will be the default conda channels
of the created installer (if it includes conda).

## `installer_filename`

required: False

argument type: `str`

The filename of the installer being created.  A reasonable default filename
will determined by the `name`, `version`, platform and installer type.

## `installer_type`

required: False

argument type: `str`

The type of the installer being created.  Possible values are "sh", "pkg",
and "exe".  By default, the type is "sh" on Unix, and "exe" on Windows.

## `license_file`

required: False

argument type: `str`

Path to the license file being displayed by the installer during the install
process.

## `keep_pkgs`

required: False

argument type: `bool`

By default, no conda packages are preserved after running the created
installer in the `pkgs` directory.  Using this option changes the default
behavior.

## `signing_identity_name`

required: False

argument type: `str`

By default, the MacOS pkg installer isn't signed. If an identity name is specified
using this option, it will be used to sign the installer. Note that you will need
to have a certificate and corresponding private key together called an 'identity'
in one of your accessible keychains.

## `attempt_hardlinks`

required: False

argument type: `bool`

By default, conda packages are extracted into the root environment and then
patched. Enabling this option will result into extraction of the packages into
the `pkgs` directory and the files in the root environment will be hardlinks to
the files kept in the `pkgs` directory and then patched accordingly.

## `write_condarc`

required: False

argument type: `bool`

By default, no .condarc file is written. If set, a .condarc file is written to
the base environment if there are any channels or conda_default_channels is set.

## `company`

required: False

argument type: `str`

Name of the company/entity who is responsible for the installer.

## `uninstall_name`

required: False

argument type: `str`

Application name in the Windows "Programs and Features" control panel.
Defaults to `${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})`.

## `pre_install`

required: False

argument type: `str`

Path to a pre install (bash - Unix only) script.

## `post_install`

required: False

argument type: `str`

Path to a post install (bash for Unix - .bat for Windows) script.

## `post_install_desc`

required: False

argument type: `str`

Short description of the "post_install" script to be displayed as label of
the "Do not run post install script" checkbox in the windows installer.
If used and not an empty string, the "Do not run post install script"
checkbox will be displayed with this label.

## `pre_uninstall`

required: False

argument type: `str`

Path to a pre uninstall (.bat for Windows) script. Only supported on Windows.

## `welcome_image`

required: False

argument type: `str`

Path to an image (in any common image format `.png`, `.jpg`, `.tif`, etc.)
which is used as the welcome image for the Windows installer.
The image is re-sized to 164 x 314 pixels.
By default, an image is automatically generated.

## `header_image`

required: False

argument type: `str`

Like `welcome_image` for Windows, re-sized to 150 x 57 pixels.

## `icon_image`

required: False

argument type: `str`

Like `welcome_image` for Windows, re-sized to 256 x 256 pixels.

## `default_image_color`

required: False

argument type: `str`

The color of the default images (when not providing explicit image files)
used on Windows.  Possible values are `red`, `green`, `blue`, `yellow`.
The default is `blue`.

## `welcome_image_text`

required: False

argument type: `str`

If `welcome_image` is not provided, use this text when generating the image
(Windows only). Defaults to `name`.

## `header_image_text`

required: False

argument type: `str`

If `header_image` is not provided, use this text when generating the image
(Windows only). Defaults to `name`.

## `initialize_by_default`

required: False

argument type: `bool`

Default choice for whether to add the installation to the PATH environment
variable. The user is still able to change this during interactive
installation.

## `register_python_default`

required: False

argument type: `bool`

Default choice for whether to register the installed Python instance as the
system's default Python. The user is still able to change this during
interactive installation. (Windows only)

## `installers`

required: False

argument type: `dict`

When supplied, `installers` is a dictionary of dictionaries that allows a single
`construct.yaml` file to describe multiple installers. In this mode, the top-level
options provide a set of "parent" specifications which are merged which each
child dictionary in a simple fashion to yield a complete installer specification.
The merging approach is as follows:
- For _string_ options, the "parent" spec provides a simple default. If a
  child spec includes the same key, its value overrides the parent.
- For _list_ options, the "parent" and "child" lists are _concatenated_ for the
  final spec. This allows, for instance, the parent to specify a set of
  base packages to include in all installers.
- For _dictionary_ options, the "parent" and "child" dictionaries are combined,
  with any intersecting keys resolved in favor of the child.

In this mode, the name of each installer is given by the dictionary keys in the
`installers` option, and the `name` field must not be explicitly supplied.


## Available selectors

- `aarch64`
- `armv7l`
- `linux`
- `linux32`
- `linux64`
- `osx`
- `ppc64le`
- `s390x`
- `unix`
- `win`
- `win32`
- `win64`
- `x86`
- `x86_64`
