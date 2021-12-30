===========================================
Creating custom installers with constructor
===========================================

Constructor is a tool which allows constructing an installer
for a collection of conda packages. It solves needed packages using user-provided
specifications, and bundles those packages.  It can currently create 3 kinds of
installers, which are best thought of as delivery vehicles for the bundled packages.
There are shell installers, MacOS .pkg installers, and Windows .exe installers.  Each
of these will create an environment on the end user's system that contains the specs
you provided, along with any necessary dependencies.  These installers are similar
to the Anaconda and Miniconda installers, and indeed constructor is used to create
those installers.

You can install constructor using conda:

.. code-block::

    conda install constructor
    constructor -h
 
The constructor command takes an installer specification directory
as its argument. This directory needs to contain a ``construct.yaml`` file,
which specifies the name of the installer, the conda channels to pull packages
from, the conda packages included in the installer, etc. The full specification
for what a construct.yaml file may contain is at :doc:`construct_yaml`. Also,
the directory may contain some additional optional files such as a license file,
and image files for the Windows installer.


An example construct.yaml file
==============================
 
In this example you will see a few of the common keys such as
name, version, channels, specs, and a few others like the key
for ``license_file`` and ``welcome_image``. You will also
notice that certain packages in specs are specified for only
specific platforms - UNIX, Win.

.. code-block::

    name: Maxiconda
    version: 2.5.5
    channels:
    - http://repo.continuum.io/pkgs/main/
    specs:
    - python 3.7*
    - conda
    - nomkl   	[not win]
    - numpy
    - scipy
    - pandas
    - notebook
    - matplotlib
    - lighttpd   	[unix]
    license_file: EULA.txt
    welcome_image: photo.png [win]

In order to create your custom installer, create a directory
with your ``construct.yaml`` file inside as well as any other
necessary files (EULA.txt, photo.png, etc).


Building installers
===================

Navigate your terminal so that your current working directory is the folder
containing your desired construct.yaml. From there, run this command:

.. code-block::

    constructor .

Your installer will be created inside of the directory with
this naming scheme: `name-version-yourPlatform.{sh|exe|pkg}`.


Controlling which kind of installer gets generated
==================================================

Constructor is currently limited to generating installers for the platform on
which it is running. In other words, if you run constructor on a Windows
computer, you can only generate Windows installers. This is largely because
OS-native tools are needed to generate the Windows .exe files and MacOS .pkg
files.  There is a key in construct.yaml, `installer_type`, which dictates
the type of installer that gets generated. This is primarily only useful for
MacOS, where you can generate either .pkg or .sh installers. When not set in
construct.yaml, this value defaults to .sh on Unix platforms, and .exe on
Windows. Using this key is generally done with selectors.  For example, to
build a .pkg installer on MacOS, but fall back to default behavior on other
platforms:

.. code-block::

   installer_type: pkg                   [osx]

 
Some additional considerations
==============================
* All conda packages must be available for the platform you are
  building the installer for.  Noarch packages are allowed, as of
  constructor version 3.0.0
* An installer created by constructor does not need to include
  conda itself. If you require the ability to use conda after
  installation, add conda to the package list.  All installers
  include the standalone conda executable, but this is not a
  documented tool for independent use at this time.
* An installer created by constructor is not the same as
  Miniconda. All packages you want to include in the installer
  need to be listed explicitly. In particular, on Windows this
  means that if you want the "Anaconda Prompt", you will have
  to list console_shortcut, as well as menuinst.
* For Windows builds, add the Anaconda channels /main and /msys2
  to the file ``construct.yaml``. This provides packages such
  as m2w64-toolchain, which is a dependency of theano. It is best
  to add /msys2 as https://repo.anaconda.com/pkgs/msys2/.
* Constructor requires conda >=4.5.0
* MacOS .pkg installers are finicky. One great resource on the topic is
  https://stackoverflow.com/a/11487658
