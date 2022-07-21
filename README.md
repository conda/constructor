# (conda) Constructor

## Description

Constructor is a tool which allows constructing an installer
for a collection of conda packages. It solves needed packages using user-provided
specifications, and bundles those packages.  It can currently create 3 kinds of
installers, which are best thought of as delivery vehicles for the bundled packages.
There are shell installers, MacOS .pkg installers, and Windows .exe installers.  Each
of these will create an environment on the end user's system that contains the specs
you provided, along with any necessary dependencies.  These installers are similar
to the Anaconda and Miniconda installers, and indeed constructor is used to create
those installers.

## Installation

`constructor` can be installed into the base environment using:

    $ conda install constructor

Once installed, the constructor command will be available:

    $ constructor -h

## Usage

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


## Development

To build or update ``README.md`` at the root of the repo you'll need to install the
`jinja2` package (`conda install jinja2`) and then run ``make doc``, or invoke the
the script directly with ``python scripts/make_docs.py``.

## Build status

| [![Build status](https://github.com/conda/constructor/workflows/Build%20and%20test%20the%20package/badge.svg)](https://github.com/conda/constructor/actions) [![codecov](https://codecov.io/gh/conda/constructor/branch/main/graph/badge.svg)](https://codecov.io/gh/conda/constructor) | [![Anaconda-Server Badge](https://anaconda.org/ctools/constructor/badges/latest_release_date.svg)](https://anaconda.org/ctools/constructor) |
| --- | :-: |
| [`conda install ctools/label/dev::constructor`](https://anaconda.org/ctools/constructor) | [![Anaconda-Server Badge](https://anaconda.org/ctools/constructor/badges/version.svg)](https://anaconda.org/ctools/constructor) |
| [`conda install defaults::constructor`](https://anaconda.org/anaconda/constructor) | [![Anaconda-Server Badge](https://anaconda.org/anaconda/constructor/badges/version.svg)](https://anaconda.org/anaconda/constructor) |
| [`conda install conda-forge::constructor`](https://anaconda.org/conda-forge/constructor) | [![Anaconda-Server Badge](https://anaconda.org/conda-forge/constructor/badges/version.svg)](https://anaconda.org/conda-forge/constructor) |
