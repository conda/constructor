#!/bin/sh
#
# Created by constructor __CONSTRUCTOR_VERSION__
#
# NAME:  __NAME__
# VER:   __VERSION__
# PLAT:  __PLAT__
# MD5:   __MD5__

set -eu

#if osx
unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH
#else
export OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
unset LD_LIBRARY_PATH
#endif

if ! echo "$0" | grep '\.sh$' > /dev/null; then
    printf 'Please run using "bash"/"dash"/"sh"/"zsh", but not "." or "source".\n' >&2
    return 1
fi

# Export variables to make installer metadata available to pre/post install scripts
# NOTE: If more vars are added, make sure to update the examples/scripts tests too

_SCRIPT_ENV_VARIABLES_=''  # Templated extra environment variable(s)
export INSTALLER_NAME='__NAME__'
export INSTALLER_VER='__VERSION__'
export INSTALLER_PLAT='__PLAT__'
export INSTALLER_TYPE="SH"

THIS_DIR=$(DIRNAME=$(dirname "$0"); cd "$DIRNAME"; pwd)
THIS_FILE=$(basename "$0")
THIS_PATH="$THIS_DIR/$THIS_FILE"
PREFIX="__DEFAULT_PREFIX__"
#if batch_mode
BATCH=1
#else
BATCH=0
#endif
FORCE=0
#if keep_pkgs
KEEP_PKGS=1
#else
KEEP_PKGS=0
#endif
SKIP_SCRIPTS=0
#if enable_shortcuts == "true"
SKIP_SHORTCUTS=0
#endif
TEST=0
REINSTALL=0
USAGE="
usage: $0 [options]

Installs ${INSTALLER_NAME} ${INSTALLER_VER}

#if batch_mode
-i           run install in interactive mode
#else
-b           run install in batch mode (without manual intervention),
             it is expected the license terms (if any) are agreed upon
#endif
-f           no error if install prefix already exists
-h           print this help message and exit
#if not keep_pkgs
-k           do not clear the package cache after installation
#endif
#if check_path_spaces
-p PREFIX    install prefix, defaults to $PREFIX, must not contain spaces.
#else
-p PREFIX    install prefix, defaults to $PREFIX
#endif
-s           skip running pre/post-link/install scripts
#if enable_shortcuts == 'true'
-m           disable the creation of menu items / shortcuts
#endif
-u           update an existing installation
#if has_conda
-t           run package tests after installation (may install conda-build)
#endif
"

# We used to have a getopt version here, falling back to getopts if needed
# However getopt is not standardized and the version on Mac has different
# behaviour. getopts is good enough for what we need :)
# More info: https://unix.stackexchange.com/questions/62950/
#if enable_shortcuts == "true"
while getopts "bifhkp:smut" x; do
#else
while getopts "bifhkp:sut" x; do
#endif
    case "$x" in
        h)
            printf "%s\\n" "$USAGE"
            exit 2
        ;;
        b)
            BATCH=1
            ;;
        i)
            BATCH=0
            ;;
        f)
            FORCE=1
            ;;
        k)
            KEEP_PKGS=1
            ;;
        p)
            PREFIX="$OPTARG"
            ;;
        s)
            SKIP_SCRIPTS=1
            ;;
#if enable_shortcuts == "true"
        m)
            SKIP_SHORTCUTS=1
            ;;
#endif
        u)
            FORCE=1
            ;;
#if has_conda
        t)
            TEST=1
            ;;
#endif
        ?)
            printf "ERROR: did not recognize option '%s', please try -h\\n" "$x"
            exit 1
            ;;
    esac
done

# For testing, keep the package cache around longer
CLEAR_AFTER_TEST=0
if [ "$TEST" = "1" ] && [ "$KEEP_PKGS" = "0" ]; then
    CLEAR_AFTER_TEST=1
    KEEP_PKGS=1
fi

if [ "$BATCH" = "0" ] # interactive mode
then
#if x86 and not x86_64
    if [ "$(uname -m)" = "x86_64" ]; then
        printf "WARNING:\\n"
        printf "    Your system is x86_64, but you are trying to install an x86 (32-bit)\\n"
        printf "    version of %s.  Unless you have the necessary 32-bit libraries\\n" "${INSTALLER_NAME}"
        printf "    installed, %s will not work.\\n" "${INSTALLER_NAME}"
        printf "    We STRONGLY recommend installing the x86_64 version of %s on\\n" "${INSTALLER_NAME}"
        printf "    an x86_64 system.\\n"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
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
        printf "    install a 64-bit version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
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
        printf "    but you are trying to install a ppc64le version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if s390x
    if [ "$(uname -m)" != "s390x" ]; then
        printf "WARNING:\\n"
        printf "    Your machine hardware does not appear to be s390x (big endian), \\n"
        printf "    but you are trying to install a s390x version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

#if aarch64
    if [ "$(uname -m)" != "aarch64" ]; then
        printf "WARNING:\\n"
        printf "    Your machine hardware does not appear to be aarch64, \\n"
        printf "    but you are trying to install a aarch64 version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
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
        printf "    but you are trying to install a macOS version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
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
        printf "    but you are trying to install a Linux version of %s.\\n" "${INSTALLER_NAME}"
        printf "    Are sure you want to continue the installation? [yes|no]\\n"
        printf "[no] >>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
        if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
        then
            printf "Aborting installation\\n"
            exit 2
        fi
    fi
#endif

    printf "\\n"
    printf "Welcome to %s %s\\n" "${INSTALLER_NAME}" "${INSTALLER_VER}"
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
    "$pager" <<'EOF'
__LICENSE__
EOF
    printf "\\n"
    printf "Do you accept the license terms? [yes|no]\\n"
    printf ">>> "
    read -r ans
    ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    while [ "$ans" != "YES" ] && [ "$ans" != "NO" ]
    do
        printf "Please answer 'yes' or 'no':'\\n"
        printf ">>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    done
    if [ "$ans" != "YES" ]
    then
        printf "The license agreement wasn't approved, aborting installation.\\n"
        exit 2
    fi
#endif

    printf "\\n"
    printf "%s will now be installed into this location:\\n" "${INSTALLER_NAME}"
    printf "%s\\n" "$PREFIX"
    printf "\\n"
    printf "  - Press ENTER to confirm the location\\n"
    printf "  - Press CTRL-C to abort the installation\\n"
    printf "  - Or specify a different location below\\n"
    printf "\\n"
    printf "[%s] >>> " "$PREFIX"
    read -r user_prefix
    if [ "$user_prefix" != "" ]; then
#if check_path_spaces is True
        case "$user_prefix" in
            *\ * )
                printf "ERROR: Cannot install into directories with spaces\\n" >&2
                exit 1
                ;;
            *)
                eval PREFIX="$user_prefix"
                ;;
        esac
#else
        PREFIX="$user_prefix"
#endif
    fi
fi # !BATCH

#if check_path_spaces is True
case "$PREFIX" in
    *\ * )
        printf "ERROR: Cannot install into directories with spaces\\n" >&2
        exit 1
        ;;
esac
#endif

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

total_installation_size_kb="__TOTAL_INSTALLATION_SIZE_KB__"
free_disk_space_bytes="$(df -Pk "$PREFIX" | tail -n 1 | awk '{print $4}')"
free_disk_space_kb="$((free_disk_space_bytes / 1024))"
free_disk_space_kb_with_buffer="$((free_disk_space_bytes - 100 * 1024))"  # add 100MB of buffer
if [ "$free_disk_space_kb_with_buffer" -lt "$total_installation_size_kb" ]; then
    printf "ERROR: Not enough free disk space: %s < %s\\n" "$free_disk_space_kb_with_buffer" "$total_installation_size_kb" >&2
    exit 1
fi

# pwd does not convert two leading slashes to one
# https://github.com/conda/constructor/issues/284
PREFIX=$(cd "$PREFIX"; pwd | sed 's@//@/@')
export PREFIX

printf "PREFIX=%s\\n" "$PREFIX"

# 3-part dd from https://unix.stackexchange.com/a/121798/34459
# Using a larger block size greatly improves performance, but our payloads
# will not be aligned with block boundaries. The solution is to extract the
# bulk of the payload with a larger block size, and use a block size of 1
# only to extract the partial blocks at the beginning and the end.
extract_range () {
    # Usage: extract_range first_byte last_byte_plus_1
    blk_siz=16384
    dd1_beg=$1
    dd3_end=$2
    dd1_end=$(( ( dd1_beg / blk_siz + 1 ) * blk_siz ))
    dd1_cnt=$(( dd1_end - dd1_beg ))
    dd2_end=$(( dd3_end / blk_siz ))
    dd2_beg=$(( ( dd1_end - 1 ) / blk_siz + 1 ))
    dd2_cnt=$(( dd2_end - dd2_beg ))
    dd3_beg=$(( dd2_end * blk_siz ))
    dd3_cnt=$(( dd3_end - dd3_beg ))
    dd if="$THIS_PATH" bs=1 skip="${dd1_beg}" count="${dd1_cnt}" 2>/dev/null
    dd if="$THIS_PATH" bs="${blk_siz}" skip="${dd2_beg}" count="${dd2_cnt}" 2>/dev/null
    dd if="$THIS_PATH" bs=1 skip="${dd3_beg}" count="${dd3_cnt}" 2>/dev/null
}

# the line marking the end of the shell header and the beginning of the payload
last_line=$(grep -anm 1 '^@@END_HEADER@@' "$THIS_PATH" | sed 's/:.*//')
# the start of the first payload, in bytes, indexed from zero
boundary0=$(head -n "${last_line}" "${THIS_PATH}" | wc -c | sed 's/ //g')
# the start of the second payload / the end of the first payload, plus one
boundary1=$(( boundary0 + __FIRST_PAYLOAD_SIZE__ ))
# the end of the second payload, plus one
boundary2=$(( boundary1 + __SECOND_PAYLOAD_SIZE__ ))

# verify the MD5 sum of the tarball appended to this header
#if osx
MD5=$(extract_range "${boundary0}" "${boundary2}" | md5)
#else
MD5=$(extract_range "${boundary0}" "${boundary2}" | md5sum -)
#endif

if ! echo "$MD5" | grep __MD5__ >/dev/null; then
    printf "WARNING: md5sum mismatch of tar archive\\n" >&2
    printf "expected: __MD5__\\n" >&2
    printf "     got: %s\\n" "$MD5" >&2
fi

cd "$PREFIX"

# disable sysconfigdata overrides, since we want whatever was frozen to be used
unset PYTHON_SYSCONFIGDATA_NAME _CONDA_PYTHON_SYSCONFIGDATA_NAME

# the first binary payload: the standalone conda executable
CONDA_EXEC="$PREFIX/_conda"
extract_range "${boundary0}" "${boundary1}" > "$CONDA_EXEC"
chmod +x "$CONDA_EXEC"

export TMP_BACKUP="${TMP:-}"
export TMP="$PREFIX/install_tmp"
mkdir -p "$TMP"

# Create $PREFIX/.nonadmin if the installation didn't require superuser permissions
if [ "$(id -u)" -ne 0 ]; then
    touch "$PREFIX/.nonadmin"
fi

# the second binary payload: the tarball of packages
printf "Unpacking payload ...\n"
extract_range $boundary1 $boundary2 | \
    "$CONDA_EXEC" constructor --extract-tarball --prefix "$PREFIX"

PRECONDA="$PREFIX/preconda.tar.bz2"
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-tarball < "$PRECONDA" || exit 1
rm -f "$PRECONDA"

"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-conda-pkgs || exit 1

#The templating doesn't support nested if statements
#if has_pre_install
if [ "$SKIP_SCRIPTS" = "1" ]; then
    export INST_OPT='--skip-scripts'
    printf "WARNING: skipping pre_install.sh by user request\\n" >&2
else
    export INST_OPT=''
#endif
#if has_pre_install and direct_execute_pre_install
    if ! "$PREFIX/pkgs/pre_install.sh"; then
#endif
#if has_pre_install and not direct_execute_pre_install
    if ! sh "$PREFIX/pkgs/pre_install.sh"; then
#endif
#if has_pre_install
        printf "ERROR: executing pre_install.sh failed\\n" >&2
        exit 1
    fi
fi
#endif

MSGS="$PREFIX/.messages.txt"
touch "$MSGS"
export FORCE

# original issue report:
# https://github.com/ContinuumIO/anaconda-issues/issues/11148
# First try to fix it (this apparently didn't work; QA reported the issue again)
# https://github.com/conda/conda/pull/9073
# Avoid silent errors when $HOME is not writable
# https://github.com/conda/constructor/pull/669
test -d ~/.conda || mkdir -p ~/.conda >/dev/null 2>/dev/null || test -d ~/.conda || mkdir ~/.conda

printf "\nInstalling base environment...\n\n"

#if enable_shortcuts == "true"
if [ "$SKIP_SHORTCUTS" = "1" ]; then
    shortcuts="--no-shortcuts"
else
    shortcuts="__SHORTCUTS__"
fi
#endif
#if enable_shortcuts == "false"
shortcuts="--no-shortcuts"
#endif
#if enable_shortcuts == "incompatible"
shortcuts=""
#endif

# shellcheck disable=SC2086
CONDA_ROOT_PREFIX="$PREFIX" \
CONDA_REGISTER_ENVS="__REGISTER_ENVS__" \
CONDA_SAFETY_CHECKS=disabled \
CONDA_EXTRA_SAFETY_CHECKS=no \
CONDA_CHANNELS="__CHANNELS__" \
CONDA_PKGS_DIRS="$PREFIX/pkgs" \
"$CONDA_EXEC" install --offline --file "$PREFIX/pkgs/env.txt" -yp "$PREFIX" $shortcuts || exit 1
rm -f "$PREFIX/pkgs/env.txt"

#The templating doesn't support nested if statements
#if has_conda
mkdir -p "$PREFIX/envs"
for env_pkgs in "${PREFIX}"/pkgs/envs/*/; do
    env_name=$(basename "${env_pkgs}")
    if [ "$env_name" = "*" ]; then
        continue
    fi
    printf "\nInstalling %s environment...\n\n" "${env_name}"
    mkdir -p "$PREFIX/envs/$env_name"

    if [ -f "${env_pkgs}channels.txt" ]; then
        env_channels=$(cat "${env_pkgs}channels.txt")
        rm -f "${env_pkgs}channels.txt"
    else
        env_channels="__CHANNELS__"
    fi
#endif
#if has_conda and enable_shortcuts == "true"
    if [ "$SKIP_SHORTCUTS" = "1" ]; then
        env_shortcuts="--no-shortcuts"
    else
        # This file is guaranteed to exist, even if empty
        env_shortcuts=$(cat "${env_pkgs}shortcuts.txt")
        rm -f "${env_pkgs}shortcuts.txt"
    fi
#endif
#if has_conda and enable_shortcuts == "false"
    env_shortcuts="--no-shortcuts"
#endif
#if has_conda and enable_shortcuts == "incompatible"
    env_shortcuts=""
#endif
#if has_conda
    # shellcheck disable=SC2086
    CONDA_ROOT_PREFIX="$PREFIX" \
    CONDA_REGISTER_ENVS="__REGISTER_ENVS__" \
    CONDA_SAFETY_CHECKS=disabled \
    CONDA_EXTRA_SAFETY_CHECKS=no \
    CONDA_CHANNELS="$env_channels" \
    CONDA_PKGS_DIRS="$PREFIX/pkgs" \
    "$CONDA_EXEC" install --offline --file "${env_pkgs}env.txt" -yp "$PREFIX/envs/$env_name" $env_shortcuts || exit 1
    rm -f "${env_pkgs}env.txt"
done
#endif

__INSTALL_COMMANDS__

POSTCONDA="$PREFIX/postconda.tar.bz2"
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-tarball < "$POSTCONDA" || exit 1
rm -f "$POSTCONDA"
rm -rf "$PREFIX/install_tmp"
export TMP="$TMP_BACKUP"


#The templating doesn't support nested if statements
#if has_post_install
if [ "$SKIP_SCRIPTS" = "1" ]; then
    printf "WARNING: skipping post_install.sh by user request\\n" >&2
else
#endif
#if has_post_install and direct_execute_post_install
    if ! "$PREFIX/pkgs/post_install.sh"; then
#endif
#if has_post_install and not direct_execute_post_install
    if ! sh "$PREFIX/pkgs/post_install.sh"; then
#endif
#if has_post_install
        printf "ERROR: executing post_install.sh failed\\n" >&2
        exit 1
    fi
fi
#endif

if [ -f "$MSGS" ]; then
  cat "$MSGS"
fi
rm -f "$MSGS"
if [ "$KEEP_PKGS" = "0" ]; then
    rm -rf "$PREFIX"/pkgs
else
    # Attempt to delete the empty temporary directories in the package cache
    # These are artifacts of the constructor --extract-conda-pkgs
    find "$PREFIX/pkgs" -type d -empty -exec rmdir {} \; 2>/dev/null || :
fi

cat <<'EOF'
__CONCLUSION_TEXT__
EOF

if [ "${PYTHONPATH:-}" != "" ]; then
    printf "WARNING:\\n"
    printf "    You currently have a PYTHONPATH environment variable set. This may cause\\n"
    printf "    unexpected behavior when running the Python interpreter in %s.\\n" "${INSTALLER_NAME}"
    printf "    For best results, please verify that your PYTHONPATH only points to\\n"
    printf "    directories of packages that are compatible with the Python interpreter\\n"
    printf "    in %s: %s\\n" "${INSTALLER_NAME}" "$PREFIX"
fi

if [ "$BATCH" = "0" ]; then
#if initialize_conda is True and initialize_by_default is True
    DEFAULT=yes
#endif
#if initialize_conda is True and initialize_by_default is False
    DEFAULT=no
#endif

#if has_conda and initialize_conda is True
    # Interactive mode.

    printf "Do you wish to update your shell profile to automatically initialize conda?\\n"
    printf "This will activate conda on startup and change the command prompt when activated.\\n"
    printf "If you'd prefer that conda's base environment not be activated on startup,\\n"
    printf "   run the following command when conda is activated:\\n"
    printf "\\n"
    printf "conda config --set auto_activate_base false\\n"
    printf "\\n"
    printf "You can undo this by running \`conda init --reverse \$SHELL\`? [yes|no]\\n"
    printf "[%s] >>> " "$DEFAULT"
    read -r ans
    if [ "$ans" = "" ]; then
        ans=$DEFAULT
    fi
    ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
    then
        printf "\\n"
        printf "You have chosen to not have conda modify your shell scripts at all.\\n"
        printf "To activate conda's base environment in your current shell session:\\n"
        printf "\\n"
        printf "eval \"\$(%s/bin/conda shell.YOUR_SHELL_NAME hook)\" \\n" "$PREFIX"
        printf "\\n"
        printf "To install conda's shell functions for easier access, first activate, then:\\n"
        printf "\\n"
        printf "conda init\\n"
        printf "\\n"
    else
        case $SHELL in
            # We call the module directly to avoid issues with spaces in shebang
            *zsh) "$PREFIX/bin/python" -m conda init zsh ;;
            *) "$PREFIX/bin/python" -m conda init ;;
        esac
        if [ -f "$PREFIX/bin/mamba" ]; then
            case $SHELL in
                # We call the module directly to avoid issues with spaces in shebang
                *zsh) "$PREFIX/bin/python" -m mamba.mamba init zsh ;;
                *) "$PREFIX/bin/python" -m mamba.mamba init ;;
            esac
        fi
    fi
#endif

    printf "Thank you for installing %s!\\n" "${INSTALLER_NAME}"
fi # !BATCH


#if has_conda
if [ "$TEST" = "1" ]; then
    printf "INFO: Running package tests in a subshell\\n"
    NFAILS=0
    (# shellcheck disable=SC1091
     . "$PREFIX"/bin/activate
     which conda-build > /dev/null 2>&1 || conda install -y conda-build
     if [ ! -d "$PREFIX/conda-bld/${INSTALLER_PLAT}" ]; then
         mkdir -p "$PREFIX/conda-bld/${INSTALLER_PLAT}"
     fi
     cp -f "$PREFIX"/pkgs/*.tar.bz2 "$PREFIX/conda-bld/${INSTALLER_PLAT}/"
     cp -f "$PREFIX"/pkgs/*.conda "$PREFIX/conda-bld/${INSTALLER_PLAT}/"
     if [ "$CLEAR_AFTER_TEST" = "1" ]; then
         rm -rf "$PREFIX/pkgs"
     fi
     conda index "$PREFIX/conda-bld/${INSTALLER_PLAT}/"
     conda-build --override-channels --channel local --test --keep-going "$PREFIX/conda-bld/${INSTALLER_PLAT}/"*.tar.bz2
    ) || NFAILS=$?
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
#endif

exit 0
# shellcheck disable=SC2317
@@END_HEADER@@
