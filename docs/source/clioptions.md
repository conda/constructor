# CLI options for constructor-generated installers
...
## Windows installers

Windows installers have the following CLI options available:

- `/RegisterPython`
- `/NoRegistry`: This flag prevents all registry modification during installation. It helps to ease installation in sandboxed environments.
- `/NoScripts`: This flag prevents post-installation scripts from running.
- `/NoShortcuts`: This flag enables non-user visible installation, whose icons otherwise clobber the "main" miniconda start menu shortcut. It helps you to create clean portable environments.
- `/CheckPathLength`

We also hvae the following NSIS standard flags:

- `/NCRC`:
- `/S`: 
- `/D`: 

Note NSIS installers won't add any output to the terminal. We recommend running them in one of the following ways:

- With  CMD, use ...
- With Powershell, use ...