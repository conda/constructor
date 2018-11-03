#!/bin/sh
#
# NAME:  __NAME__
# VER:   __VERSION__
# PLAT:  __PLAT__
# BYTES: @SIZE_BYTES@
# LINES: @LINES@
# MD5:   __MD5__

#if osx
unset DYLD_LIBRARY_PATH
#else
export OLD_LD_LIBRARY_PATH=$LD_LIBRARY_PATH
unset LD_LIBRARY_PATH
#endif

if ! echo "$0" | grep '\.sh$' > /dev/null; then
    printf 'Please run using "bash" or "sh", but not "." or "source"\\n' >&2
    return 1
fi

# Determine RUNNING_SHELL; if SHELL is non-zero use that.
if [ -n "$SHELL" ]; then
    RUNNING_SHELL="$SHELL"
else
    if [ "$(uname)" = "Darwin" ]; then
        RUNNING_SHELL=/bin/bash
    else
        if [ -d /proc ] && [ -r /proc ] && [ -d /proc/$$ ] && [ -r /proc/$$ ] && [ -L /proc/$$/exe ] && [ -r /proc/$$/exe ]; then
            RUNNING_SHELL=$(readlink /proc/$$/exe)
        fi
        if [ -z "$RUNNING_SHELL" ] || [ ! -f "$RUNNING_SHELL" ]; then
            RUNNING_SHELL=$(ps -p $$ -o args= | sed 's|^-||')
            case "$RUNNING_SHELL" in
                */*)
                    ;;
                default)
                    RUNNING_SHELL=$(which "$RUNNING_SHELL")
                    ;;
            esac
        fi
    fi
fi

# Some final fallback locations
if [ -z "$RUNNING_SHELL" ] || [ ! -f "$RUNNING_SHELL" ]; then
    if [ -f /bin/bash ]; then
        RUNNING_SHELL=/bin/bash
    else
        if [ -f /bin/sh ]; then
            RUNNING_SHELL=/bin/sh
        fi
    fi
fi

if [ -z "$RUNNING_SHELL" ] || [ ! -f "$RUNNING_SHELL" ]; then
    printf 'Unable to determine your shell. Please set the SHELL env. var and re-run\\n' >&2
    exit 1
fi

THIS_DIR=$(DIRNAME=$(dirname "$0"); cd "$DIRNAME"; pwd)
THIS_FILE=$(basename "$0")
THIS_PATH="$THIS_DIR/$THIS_FILE"
PREFIX=__DEFAULT_PREFIX__
BATCH=0
FORCE=0
SKIP_SCRIPTS=0
TEST=0
REINSTALL=0
USAGE="
usage: $0 [options]

Installs __NAME__ __VERSION__

-b           run install in batch mode (without manual intervention),
             it is expected the license terms are agreed upon
-f           no error if install prefix already exists
-h           print this help message and exit
-p PREFIX    install prefix, defaults to $PREFIX, must not contain spaces.
-s           skip running pre/post-link/install scripts
-u           update an existing installation
-t           run package tests after installation (may install conda-build)
"

if which getopt > /dev/null 2>&1; then
    OPTS=$(getopt bfhp:sut "$*" 2>/dev/null)
    if [ ! $? ]; then
        printf "%s\\n" "$USAGE"
        exit 2
    fi

    eval set -- "$OPTS"

    while true; do
        case "$1" in
            -h)
                printf "%s\\n" "$USAGE"
                exit 2
                ;;
            -b)
                BATCH=1
                shift
                ;;
            -f)
                FORCE=1
                shift
                ;;
            -p)
                PREFIX="$2"
                shift
                shift
                ;;
            -s)
                SKIP_SCRIPTS=1
                shift
                ;;
            -u)
                FORCE=1
                shift
                ;;
            -t)
                TEST=1
                shift
                ;;
            --)
                shift
                break
                ;;
            *)
                printf "ERROR: did not recognize option '%s', please try -h\\n" "$1"
                exit 1
                ;;
        esac
    done
else
    while getopts "bfhp:sut" x; do
        case "$x" in
            h)
                printf "%s\\n" "$USAGE"
                exit 2
            ;;
            b)
                BATCH=1
                ;;
            f)
                FORCE=1
                ;;
            p)
                PREFIX="$OPTARG"
                ;;
            s)
                SKIP_SCRIPTS=1
                ;;
            u)
                FORCE=1
                ;;
            t)
                TEST=1
                ;;
            ?)
                printf "ERROR: did not recognize option '%s', please try -h\\n" "$x"
                exit 1
                ;;
        esac
    done
fi

if ! bzip2 --help >/dev/null 2>&1; then
    printf "WARNING: bzip2 does not appear to be installed this may cause problems below\\n" >&2
fi

# verify the size of the installer
if ! wc -c "$THIS_PATH" | grep @SIZE_BYTES@ >/dev/null; then
    printf "ERROR: size of %s should be @SIZE_BYTES@ bytes\\n" "$THIS_FILE" >&2
    exit 1
fi

if [ "$BATCH" = "0" ] # interactive mode
then
#if x86 and not x86_64
    if [ "$(uname -m)" = "x86_64" ]; then
        printf "WARNING:\\n"
        printf "    Your system is x86_64, but you are trying to install an x86 (32-bit)\\n"
        printf "    version of __NAME__.  Unless you have the necessary 32-bit libraries\\n"
        printf "    installed, __NAME__ will not work.\\n"
        printf "    We STRONGLY recommend installing the x86_64 version of __NAME__ on\\n"
        printf "    an x86_64 system.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
           [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if x86_64
    if [ "$(uname -m)" != "x86_64" ]; then
        printf "WARNING:\\n"
        printf "    Your operating system appears not to be 64-bit, but you are trying to\\n"
        printf "    install a 64-bit version of __NAME__.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
           [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if ppc64le
    if [ "$(uname -m)" != "ppc64le" ]; then
        printf "WARNING:\\n"
        printf "    Your machine hardware does not appear to be Power8 (little endian), \\n"
        printf "    but you are trying to install a ppc64le version of __NAME__.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
           [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if osx
    if [ "$(uname)" != "Darwin" ]; then
        printf "WARNING:\\n"
        printf "    Your operating system does not appear to be macOS, \\n"
        printf "    but you are trying to install a macOS version of __NAME__.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
           [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if linux
    if [ "$(uname)" != "Linux" ]; then
        printf "WARNING:\\n"
        printf "    Your operating system does not appear to be Linux, \\n"
        printf "    but you are trying to install a Linux version of __NAME__.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
           [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

    printf "\\n"
    printf "Welcome to __NAME__ __VERSION__\\n"
#if has_license
    printf "\\n"
    printf "In order to continue the installation process, please review the license\\n"
    printf "agreement.\\n"
    printf "Please, press ENTER to continue\\n"
    printf ">>> "
    read -r dummy
    pager="cat"
    if command -v "more" > /dev/null 2>&1; then
      pager="more"
    fi
    "$pager" <<EOF
__LICENSE__
EOF
    printf "\\n"
    printf "Do you accept the license terms? [yes|no]\\n"
    printf "[no] >>> "
    read -r ans
    while [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
          [ "$ans" != "no" ]  && [ "$ans" != "No" ]  && [ "$ans" != "NO" ]
    do
        printf "Please answer 'yes' or 'no':'\\n"
        printf ">>> "
        read -r ans
    done
    if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ]
    then
        printf "The license agreement wasn't approved, aborting installation.\\n"
        exit 2
    fi
#endif

    printf "\\n"
    printf "__NAME__ will now be installed into this location:\\n"
    printf "%s\\n" "$PREFIX"
    printf "\\n"
    printf "  - Press ENTER to confirm the location\\n"
    printf "  - Press CTRL-C to abort the installation\\n"
    printf "  - Or specify a different location below\\n"
    printf "\\n"
    printf "[%s] >>> " "$PREFIX"
    read -r user_prefix
    if [ "$user_prefix" != "" ]; then
        case "$user_prefix" in
            *\ * )
                printf "ERROR: Cannot install into directories with spaces\\n" >&2
                exit 1
                ;;
            *)
                eval PREFIX="$user_prefix"
                ;;
        esac
    fi
fi # !BATCH

case "$PREFIX" in
    *\ * )
        printf "ERROR: Cannot install into directories with spaces\\n" >&2
        exit 1
        ;;
esac

if [ "$FORCE" = "0" ] && [ -e "$PREFIX" ]; then
    printf "ERROR: File or directory already exists: '%s'\\n" "$PREFIX" >&2
    printf "If you want to update an existing installation, use the -u option.\\n" >&2
    exit 1
elif [ "$FORCE" = "1" ] && [ -e "$PREFIX" ]; then
    REINSTALL=1
fi


if ! mkdir -p "$PREFIX"; then
    printf "ERROR: Could not create directory: '%s'\\n" "$PREFIX" >&2
    exit 1
fi

PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX

printf "PREFIX=%s\\n" "$PREFIX"

# verify the MD5 sum of the tarball appended to this header
#if osx
MD5=$(tail -n +@LINES@ "$THIS_PATH" | md5)
#else
MD5=$(tail -n +@LINES@ "$THIS_PATH" | md5sum -)
#endif

if ! echo "$MD5" | grep __MD5__ >/dev/null; then
    printf "WARNING: md5sum mismatch of tar archive\\n" >&2
    printf "expected: __MD5__\\n" >&2
    printf "     got: %s\\n" "$MD5" >&2
fi

# extract the tarball appended to this header, this creates the *.tar.bz2 files
# for all the packages which get installed below
cd "$PREFIX"


if ! tail -n +@LINES@ "$THIS_PATH" | tar xf -; then
    printf "ERROR: could not extract tar starting at line @LINES@\\n" >&2
    exit 1
fi

PRECONDA="$PREFIX/preconda.tar.bz2"
bunzip2 -c $PRECONDA | tar -xf - --no-same-owner || exit 1
rm -f $PRECONDA

#if has_pre_install
if [ "$SKIP_SCRIPTS" = "1" ]; then
    export INST_OPT='--skip-scripts'
    printf "WARNING: skipping pre_install.sh by user request\\n" >&2
else
    export INST_OPT=''
    if ! $RUNNING_SHELL "$PREFIX/pkgs/pre_install.sh"; then
        printf "ERROR: executing pre_install.sh failed\\n" >&2
        exit 1
    fi
fi
#endif

PYTHON="$PREFIX/bin/python"
MSGS="$PREFIX/.messages.txt"
touch "$MSGS"
export FORCE

install_dist()
{
    # This function installs a conda package into prefix, but without linking
    # the conda packages.  It untars the package and calls a simple script
    # which does the post extract steps (update prefix files, run 'post-link',
    # and creates the conda metadata).  Note that this is all done without
    # conda.
    if [ "$REINSTALL" = "1" ]; then
      printf "reinstalling: %s ...\\n" "$1"
    else
      printf "installing: %s ...\\n" "$1"
    fi
    PKG_PATH="$PREFIX"/pkgs/$1
    PKG="$PKG_PATH".tar.bz2
    mkdir -p $PKG_PATH || exit 1
#if attempt_hardlinks
    bunzip2 -c "$PKG" | tar -xf - -C "$PKG_PATH" --no-same-owner || exit 1
    "$PREFIX/pkgs/__DIST0__/bin/python" -E -s \
        "$PREFIX"/pkgs/.install.py $INST_OPT --root-prefix="$PREFIX" --link-dist="$1" || exit 1
#else
    bunzip2 -c "$PKG" | tar -xf - -C "$PREFIX" --no-same-owner || exit 1
    "$PYTHON" -E -s "$PREFIX"/pkgs/.install.py $INST_OPT || exit 1
#endif
    if [ "$1" = "__DIST0__" ]; then
        if ! "$PYTHON" -E -V; then
            printf "ERROR:\\n" >&2
            printf "cannot execute native __PLAT__ binary, output from 'uname -a' is:\\n" >&2
            uname -a >&2
            exit 1
        fi
    fi
#if not keep_pkgs
    rm "$PKG"
#endif
}

__INSTALL_COMMANDS__

mkdir -p $PREFIX/envs

if [ "$FORCE" = "1" ]; then
    "$PYTHON" -E -s "$PREFIX"/pkgs/.install.py --rm-dup || exit 1
fi

#if has_post_install
if [ "$SKIP_SCRIPTS" = "1" ]; then
    printf "WARNING: skipping post_install.sh by user request\\n" >&2
else
    if ! $RUNNING_SHELL "$PREFIX/pkgs/post_install.sh"; then
        printf "ERROR: executing post_install.sh failed\\n" >&2
        exit 1
    fi
fi
#endif

cat "$MSGS"
rm -f "$MSGS"
#if not keep_pkgs
rm -rf "$PREFIX"/pkgs
#endif

printf "installation finished.\\n"

if [ "$PYTHONPATH" != "" ]; then
    printf "WARNING:\\n"
    printf "    You currently have a PYTHONPATH environment variable set. This may cause\\n"
    printf "    unexpected behavior when running the Python interpreter in __NAME__.\\n"
    printf "    For best results, please verify that your PYTHONPATH only points to\\n"
    printf "    directories of packages that are compatible with the Python interpreter\\n"
    printf "    in __NAME__: $PREFIX\\n"
fi

if [ "$BATCH" = "0" ]; then
    # Interactive mode.
#if osx
    BASH_RC="$HOME"/.bash_profile
    DEFAULT=yes
#else
    BASH_RC="$HOME"/.bashrc
    DEFAULT=no
#endif
#if initialize_by_default is True
    DEFAULT=yes
#endif
#if initialize_by_default is False
    DEFAULT=no
#endif

    printf "Do you wish the installer to initialize __NAME__\\n"
    printf "in your %s ? [yes|no]\\n" "$BASH_RC"
    printf "[%s] >>> " "$DEFAULT"
    read -r ans
    if [ "$ans" = "" ]; then
        ans=$DEFAULT
    fi
    if [ "$ans" != "yes" ] && [ "$ans" != "Yes" ] && [ "$ans" != "YES" ] && \
       [ "$ans" != "y" ]   && [ "$ans" != "Y" ]
    then
        printf "\\n"
        printf "You may wish to edit your $BASH_RC to setup __NAME__:\\n"
        printf "\\n"
        if [ -f "$PREFIX/etc/profile.d/conda.sh" ]; then
            printf "source $PREFIX/etc/profile.d/conda.sh\\n"
        else
            printf "export PATH=\"$PREFIX/bin:\$PATH\"\\n"
        fi
        printf "\\n"
    else
        if [ -f "$BASH_RC" ]; then
            printf "\\n"
            printf "Initializing __NAME__ in %s\\n" "$BASH_RC"
            printf "A backup will be made to: %s-__name__.bak\\n" "$BASH_RC"
            printf "\\n"
            cp "$BASH_RC" "${BASH_RC}"-__name__.bak
        else
            printf "\\n"
            printf "Initializing __NAME__ in newly created %s\\n" "$BASH_RC"
        fi
        cat <<EOF >> "$BASH_RC"

# added by __NAME__ __VERSION__ installer
# >>> conda init >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="\$(CONDA_REPORT_ERRORS=false '$PREFIX/bin/conda' shell.bash hook 2> /dev/null)"
if [ \$? -eq 0 ]; then
    \\eval "\$__conda_setup"
else
    if [ -f "$PREFIX/etc/profile.d/conda.sh" ]; then
        . "$PREFIX/etc/profile.d/conda.sh"
        CONDA_CHANGEPS1=false conda activate base
    else
        \\export PATH="$PREFIX/bin:\$PATH"
    fi
fi
unset __conda_setup
# <<< conda init <<<
EOF
        printf "\\n"
        printf "For this change to become active, you have to open a new terminal.\\n"
        printf "\\n"
    fi

    printf "Thank you for installing __NAME__!\\n"
fi # !BATCH

if [ "$TEST" = "1" ]; then
    printf "INFO: Running package tests in a subshell\\n"
    (. "$PREFIX"/bin/activate
     which conda-build > /dev/null 2>&1 || conda install -y conda-build
#if keep_pkgs
     if [ ! -d "$PREFIX"/conda-bld/__PLAT__ ]; then
         mkdir -p "$PREFIX"/conda-bld/__PLAT__
     fi
     cp -f "$PREFIX"/pkgs/*.tar.bz2 "$PREFIX"/conda-bld/__PLAT__/
     conda index "$PREFIX"/conda-bld/__PLAT__/
     conda-build --override-channels --channel local --test --keep-going "$PREFIX"/conda-bld/__PLAT__/*.tar.bz2
#endif
#if not keep_pkgs
#          conda-build -t -k "$PREFIX"/pkgs/*
     printf "ERROR: Testing not possible without keep_pkgs\\n"
     exit 1
#endif
    )
    NFAILS=$?
    if [ "$NFAILS" != "0" ]; then
        if [ "$NFAILS" = "1" ]; then
            printf "ERROR: 1 test failed\\n" >&2
            printf "To re-run the tests for the above failed package, please enter:\\n"
            printf ". %s/bin/activate\\n" "$PREFIX"
            printf "conda-build --override-channels --channel local --test <full-path-to-failed.tar.bz2>\\n"
        else
            printf "ERROR: %s test failed\\n" $NFAILS >&2
            printf "To re-run the tests for the above failed packages, please enter:\\n"
            printf ". %s/bin/activate\\n" "$PREFIX"
            printf "conda-build --override-channels --channel local --test <full-path-to-failed.tar.bz2>\\n"
        fi
        exit $NFAILS
    fi
fi

exit 0
@@END_HEADER@@
