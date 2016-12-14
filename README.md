(conda) constructor
===================

constructor is a tool which allows constructing an installer for
a collection of conda packages.  Basically, it creates an Anaconda-like
installer consisting of conda packages.   This tool was previously
proprietary and known as `cas-installer`.


Installation:
-------------

As of version 1.3.0, `constructor` may be installed into any conda
environment using:

    $ conda install constructor

Once installed, the constructor command will be available:

    $ constructor -h


Usage:
------

The `constructor` command takes an installer specification directory as its
argument.  This directory needs to contain a file `construct.yaml`,
which specifies the name of the installer, the conda channels to
pull packages from, the conda packages included in the installer etc. .
The complete list of keys in this file can be
found in <a href="./CONSTRUCT.md">CONSTRUCT.md</a>.
Also, the directory may contain some additional optional files (such as a
license file, and image files for the Windows installer).
An example is located
in <a href="./examples/maxiconda">examples/maxiconda</a>.


Notes:
------

  * Constructor does not work with `noarch`-Python packages. All conda
    packages must be available for the platform you are building the
    installer for.

  * For Windows builds, add the Continuum channels `/free` and `/msys2` 
    to the file `constructor.yaml`. This provides packages such as 
    `m2w64-toolchain` which is a dependency of `theano`. It is best to 
    add `/msys2` as `http://repo.continuum.io/pkgs/msys2`. `/msys2` 
    can also be added as `https://conda.anaconda.org/msys2` if no 
    firewall is set to block this URL.
