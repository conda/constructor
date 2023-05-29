# CLI options for constructor-generated installers

## Shell-based installers for MacOS and Linux

We have the following CLI options available for MacOS and Linux:

- `-b` helps to run the installer in batch mode through manual intervention.
- `f` returns no error if the prefix already exists.
- `h` allows us to display this help message and exit.
- `-i` is used to run it in an interactive mode if the installer is running in a batch. Otherwise, the installer runs in batch mode without manual intervention by . 
- `-k` keeps the package cache after installation.
- `-p PREFIX` installs a prefix. Kindly note that the path should not contain any spaces.
- `-s` skips running `pre/post-link/install`scripts.
- `-t` can be used to run package tests after installation (it may install conda-build), if conda is installed.
- `-u` is used to update an existing installation.

## Windows installers

Windows installers have the following CLI options available:

- `/RegisterPython`
- `/NoRegistry`: This flag prevents all registry modification during installation. It helps to ease installation in sandboxed environments.
- `/NoScripts`: This flag prevents post-installation scripts from running.
- `/NoShortcuts`: This flag enables non-user visible installation, whose icons otherwise clobber the "main" miniconda start menu shortcut. It helps you to create clean portable environments.
- `/CheckPathLength`

We also hvae the following NSIS standard flags:

- `/NCRC` disables the CRC check, unless CRCCheck force was used in the script.
- `/S` runs the installer or uninstaller in silent mode.
- `/D` sets the default installation directory and overrides InstallDir and InstallDirRegKey. Kindly note that even if the path contains spaces, it must be the last parameter used in the command line and must not contain any quotes. Only absolute paths are supported.

Note NSIS installers won't add any output to the terminal. We recommend running them in one of the following ways:

- With  CMD, use ...
- With Powershell, use ...