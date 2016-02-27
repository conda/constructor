

Keys in `construct.yaml` file:
==============================

This document describes each of they keys in the `construct.yaml` file,
which is the main configuration file of a constructor configuration
directory.

All keys are optional, except otherwise noted.  Also, the keys `specs`
and `packages` take either a list of items, or a path to a file,
which contains one item per line (excluding lines starting with `#`).


`name`: required
----------------
Name of the installer.  May also contain uppercase letter.  The installer
name is independent of the names of any of the conda packages the installer
is composed of.


`version`: required
----------------
Version of the installer.  Just like the installer name, this version
is independent of any conda package versions contained in the installer.


`channels`:
----------------
The conda channels from which packages are retrieved, when using the `specs`
key below, but also when using the `packages` key ,unless the full URL is
given in the `packages` list (see below).


`specs`:
----------------
List of package specifications, e.g. `python 2.7*`, `pyzmq` or `numpy >=1.8`.
This list of specifications if given to the conda resolver (as if you were
to create a new environment with those specs.


`exclude`:
----------------
List of package names to be excluded, after the '`specs` have been resolved.
For example, you can say that `readline` should be excluded, even though it
is contained as a result of resolving the specs for `python 2.7`.


`packages`:
----------------
A list of explicit conda packages to be included, eg. `yaml-0.1.6-0.tar.bz2`.
The packages may also be specified by their entire URL,
eg.`https://repo.continuum.io/pkgs/free/osx-64/openssl-1.0.1k-1.tar.bz2`.
Optionally, the MD5 hash sum of the package, may be added after an immediate
`#` character, eg. `readline-6.2-2.tar.bz2#0801e644bd0c1cd7f0923b56c52eb7f7`.


`sort_by_name`:
----------------
By default packages are sorted by install dependency order (unless the
explicit list in `packages` is used.  Python is always moved to the front
of the packages to be installed.  This option allows sorting by the package
names instead.


`platform`:
----------------
The platform for which the installer is created, eg. `linux-32`.  This is
not necessarily the current platform.  The default, however, is the current
platform.


`installer_filename`:
----------------
The filename of the installer being created.  A reasonable default filename
will determined by the `name`, `version`, `platform` and installer type.


`license_file`:
----------------
Path to the license file being displayed by the installer during the install
process.


`welcome_image`:
----------------
Path to an image which is used as the welcome image for the Windows
installer.  The image is re-sized to 164 x 314 pixels.
By default, an image is automatically generated.


`header_image`:
----------------
Like `welcome_image` for Windows, re-sized to 150 x 57 pixels.


`icon_image`:
----------------
Like `welcome_image` for Windows, re-sized to 256 x 256 pixels.

