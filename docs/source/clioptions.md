We have a number of constructor installer CLI options available. Following are the flags and their respective usages:

### 1. NoRegistry:
This flag prevents all registry manipulations that allow easy installation in sandboxed environments. 

Default value: 0 

It prevents registry modification only for you (the user) when the flag is set to 1.

### 2. NoShortcuts:
This flag enables non-user visible installation, whose icons otherwise clobber the "main" miniconda start menu shortcut. It helps you to create clean portable environments.

Default value: 0 

### 3. NoScripts:
This flag prevents post-installation scripts from running.

Default value: 0