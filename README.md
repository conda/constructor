# (conda) constructor


## Build status

[![Build Status](https://travis-ci.org/conda/constructor.svg?branch=master)](https://travis-ci.org/conda/constructor)
[![Build status](https://ci.appveyor.com/api/projects/status/cxf565h1rh3v0kaq?svg=true)](https://ci.appveyor.com/project/ContinuumAnalyticsFOSS/constructor)
[![codecov](https://codecov.io/gh/conda/constructor/branch/master/graph/badge.svg)](https://codecov.io/gh/conda/constructor)

## Description:

constructor is a tool which allows constructing an installer for
a collection of conda packages.  Basically, it creates an Anaconda-like
installer consisting of conda packages.   This tool was previously
proprietary and known as `cas-installer`.


## Installation:

`constructor` can be installed into the base environment using:

    $ conda install constructor

Once installed, the constructor command will be available:

    $ constructor -h


## Usage:

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


## Notes:

  * Constructor does not work with `noarch`-Python packages.
    All conda packages must be available for the platform you are
    building the installer for.
  * An installer created by constructor does not need to include `conda`
    itself.  If you require the ability to use `conda` after installation,
    add `conda` to the package list.
  * An installer created by constructor is not the same as Miniconda.  All
    packages you want to include in the installer need to be listed
    explicitly.
    In particular, on Windows this means that if you want the "Anaconda
    Prompt", you will have to list `console_shortcut`, as well as `menuinst`.
  * For Windows builds, add the Anaconda channel `/msys2`
    to the file `constructor.yaml`. This provides packages such as
    `m2w64-toolchain` which is a dependency of `theano`. It is best to
    add `/msys2` as `http://repo.anaconda.com/pkgs/msys2`.
  * Constructor requires conda >=4.5.0


## Devel

To build or update ``README.md`` at the root of the repo you'll need jinja2 installed

```
conda install jinja2
```

and then run ``make doc``. Or invoke the script directly with ``python scripts/make_docs.py``.
