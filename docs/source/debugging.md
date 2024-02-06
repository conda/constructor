# Debugging tips

Sometimes `constructor` fails to build the requested installer. Sometimes the installer builds, but
there are errors when it is run in the target machine.

In this section we will talk about different techniques you can use to find out was wrong with your installers.

## Run `constructor` in debug mode

When you run `constructor`, `conda` is called behind the scenes to solve the requested specs. You can enable advanced logging using the flags `-v` or `--debug`. These will be passed to `conda`. Be prepared for _a lot_ of output!


## Verbose `conda`

Whether it's while running `constructor` to build an installer, or while the installer is running in the target machine, some instance of `conda` will be running behind the scenes. You can request more verbose output via the `CONDA_VERBOSITY` environment variable. It can take values from `1` to `4`. You can also set `CONDA_DEBUG` to `1`.


## Verbose shell installers

The shell installers are simply shell scripts that invoke `conda` in certain events. This means you can enable `bash` verbosity via the `-x` flag:

```bash
$ bash -x ./Miniconda.sh
# or with verbose conda:
$ CONDA_VERBOSITY=3 bash -x ./Miniconda.sh
```

## Verbose PKG installers

PKG installers are usually invoked graphically. You can check the native logs via <kbd>⌘</kbd>+<kbd>L</kbd>. Note that you will need to choose the detailed view in the dropdown menu you'll find in the top right corner.

In order to get more verbosity out of `conda`, you now know you need the `CONDA_VERBOSITY` variable. However, it needs to be set up _before_ running the installer. One way from the command line would be:

```bash
$ CONDA_VERBOSITY=3 installer -pkg ./path/to/installer.pkg -target LocalSystem
```

See `man installer` for more details.

## Verbose EXE installers

Windows installers do not have a verbose mode. By default, the graphical logs are only available in the "progress bar" dialog, by clicking on "Show details". This text box is right-clickable, which will allow you to copy the contents to the clipboard (and then paste them in a text file, presumably).

If you want `conda` to print more details, then, run it from the CMD prompt like this:

```batch
> set "CONDA_VERBOSITY=3"
> cmd.exe /c start /wait your-installer.exe
```

### Building logging-enabled EXE installers

There's a way of building EXE installers that can write logs to a file; for this, you need a special `nsis` package configured to do so:

```batch
> conda install "nsis=*=*log*"
```

Then, you can invoke `constructor` normally after setting a special environment variable:

```batch
> set "NSIS_USING_LOG_BUILD=1"
> cmd.exe /c start /wait constructor .
```

The resulting EXE installer will always generate an `install.log` file in the target directory.
It will contain the full logs, as available in the "Show details" dialog.
