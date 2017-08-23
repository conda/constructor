Maxiconda example
=================

In this example, we want to demonstrate how to build installers for
Linux, Mac and Windows, which are similar to Anaconda installers, but
significantly smaller in size, but bigger than Miniconda (hence the name
Maxiconda).

We only want to construct installers which include:
  - Python 3.5 (because Python 3 is the way of the future)
  - `conda`, so people can install additional packages
  - `numpy` (but not the MKL linked version, to save space)
  - `scipy`, `pandas`
  - the Jupyter `notebook`
  - `matplotlib` (but not Qt and PyQt, again to save space)
  - `lighttpd`, the web server, but only on Unix systems

We also want to include our license file `EULA.txt`, which located in
this directory.
Also, we want to have a our own welcome image for the Windows installer.
This image `bird.png` is also located in this directory, and is re-sized
by constructor as well.

Finally, to create a Maxiconda installer, you simply run (in this directory):

    $ constructor .
    ...
    $ ls -lh Maxi*
    -rwxr-xr-x  1 ilan  staff    59M Feb 27 18:02 Maxiconda-2.5.5-MacOSX-x86_64.sh

This was done on Mac OS X.
A 60MB installer is not bad for all these packages, I would say.
Note that `constructor` will be default create an installer for the platform
which it is executed on.  However, it is also possible to build installers
for other platforms, see <a href="../../CONSTRUCT.md">the platform key</a>.
