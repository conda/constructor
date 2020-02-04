# (conda) constructor


## Build status

[![Build Status](https://travis-ci.org/conda/constructor.svg?branch=master)](https://travis-ci.org/conda/constructor)
[![Build status](https://ci.appveyor.com/api/projects/status/cxf565h1rh3v0kaq?svg=true)](https://ci.appveyor.com/project/ContinuumAnalyticsFOSS/constructor)
[![codecov](https://codecov.io/gh/conda/constructor/branch/master/graph/badge.svg)](https://codecov.io/gh/conda/constructor)

## Description:

Constructor is a tool which allows constructing an installer
for a collection of conda packages. It solves needed packages using user-provided
specifications, and bundles those packages.  It can currently create 3 kinds of
installers, which are best thought of as delivery vehicles for the bundled packages.
There are shell installers, MacOS .pkg installers, and Windows .exe installers.  Each
of these will create an environment on the end user's system that contains the specs
you provided, along with any necessary dependencies.  These installers are similar
to the Anaconda and Miniconda installers, and indeed constructor is used to create
those installers.


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


## Devel

To build or update ``README.md`` at the root of the repo you'll need jinja2 installed

```
conda install jinja2
```

and then run ``make doc``. Or invoke the script directly with ``python scripts/make_docs.py``.
