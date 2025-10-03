#!/bin/sh
#
# Created by constructor {{ constructor_version }}
#
# NAME:  {{ installer_name }}
# VER:   {{ installer_version }}
# PLAT:  {{ installer_platform }}
# MD5:   {{ installer_md5 }}

set -eu

{%- if osx %}
unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH
{%- else %}
export OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
unset LD_LIBRARY_PATH
{%- endif %}

if ! echo "$0" | grep '\.sh$' > /dev/null; then
    printf 'Please run using "bash"/"dash"/"sh"/"zsh", but not "." or "source".\n' >&2
    exit 1
fi

{%- if osx and min_osx_version %}
min_osx_version="{{ min_osx_version }}"
system_osx_version="${CONDA_OVERRIDE_OSX:-$(SYSTEM_VERSION_COMPAT=0 sw_vers -productVersion)}"
# shellcheck disable=SC2183 disable=SC2046
int_min_osx_version="$(printf "%02d%02d%02d" $(echo "$min_osx_version" | sed 's/\./ /g'))"
# shellcheck disable=SC2183 disable=SC2046
int_system_osx_version="$(printf "%02d%02d%02d" $(echo "$system_osx_version" | sed 's/\./ /g'))"
if [ "$int_system_osx_version" -lt "$int_min_osx_version" ]; then
    echo "Installer requires macOS >=${min_osx_version}, but system has ${system_osx_version}."
    exit 1
fi
{%- elif linux and min_glibc_version %}
min_glibc_version="{{ min_glibc_version }}"
system_glibc_version="${CONDA_OVERRIDE_GLIBC:-}"
if [ "${system_glibc_version}" = "" ]; then
    case "$(ldd --version 2>&1)" in
        *musl*)
            # musl ldd will report musl version; call libc.so directly
            # see https://github.com/conda/constructor/issues/850#issuecomment-2343756454
            libc_so="$(find /lib /usr/local/lib /usr/lib -name 'libc.so.*' -print -quit 2>/dev/null)"
            if [ -z "${libc_so}" ]; then
                libc_so="$(strings /etc/ld.so.cache | grep '^/.*/libc\.so.*' | head -1)"
            fi
            if [ -z "${libc_so}" ]; then
                echo "Warning: Couldn't find libc.so; won't be able to determine GLIBC version!" >&2
                echo "Override by setting CONDA_OVERRIDE_GLIBC" >&2
                system_glibc_version="0.0"
            else
                system_glibc_version=$("${libc_so}" --version | awk 'NR==1{ sub(/\.$/, ""); print $NF}')
            fi
        ;;
        *)
            # ldd reports glibc in the last field of the first line
            system_glibc_version=$(ldd --version | awk 'NR==1{print $NF}')
        ;;
    esac
fi
# shellcheck disable=SC2183 disable=SC2046
int_min_glibc_version="$(printf "%02d%02d%02d" $(echo "$min_glibc_version" | sed 's/\./ /g'))"
# shellcheck disable=SC2183 disable=SC2046
int_system_glibc_version="$(printf "%02d%02d%02d" $(echo "$system_glibc_version" | sed 's/\./ /g'))"
if [ "$int_system_glibc_version" -lt "$int_min_glibc_version" ]; then
    echo "Installer requires GLIBC >=${min_glibc_version}, but system has ${system_glibc_version}."
    exit 1
fi
{%- endif %}

# Export variables to make installer metadata available to pre/post install scripts
# NOTE: If more vars are added, make sure to update the examples/scripts tests too

{%- for key, val in script_env_variables|items %}
export {{ key }}='{{ val }}'
{%- endfor %}
export INSTALLER_NAME='{{ installer_name }}'
export INSTALLER_VER='{{ installer_version }}'
export INSTALLER_PLAT='{{ installer_platform }}'
export INSTALLER_TYPE="SH"
# Installers should ignore pre-existing configuration files.
unset CONDARC
unset MAMBARC

THIS_DIR=$(DIRNAME=$(dirname "$0"); cd "$DIRNAME"; pwd)
THIS_FILE=$(basename "$0")
THIS_PATH="$THIS_DIR/$THIS_FILE"
PREFIX="{{ default_prefix }}"
BATCH={{ 1 if batch_mode else 0 }}
FORCE=0
KEEP_PKGS={{ 1 if keep_pkgs else 0 }}
SKIP_SCRIPTS=0
{%- if enable_shortcuts == "true" %}
SKIP_SHORTCUTS=0
{%- endif %}
INIT_CONDA=0
TEST=0
REINSTALL=0
USAGE="
usage: $0 [options]

Installs ${INSTALLER_NAME} ${INSTALLER_VER}

{%- if batch_mode %}
-i           run install in interactive mode
{%- else %}
-b           run install in batch mode (without manual intervention),
             it is expected the license terms (if any) are agreed upon
{%- endif %}
-f           no error if install prefix already exists
-h           print this help message and exit
{%- if not keep_pkgs %}
-k           do not clear the package cache after installation
{%- endif %}
{%- if check_path_spaces %}
-p PREFIX    install prefix, defaults to $PREFIX, must not contain spaces.
{%- else %}
-p PREFIX    install prefix, defaults to $PREFIX
{%- endif %}
-s           skip running pre/post-link/install scripts
{%- if enable_shortcuts == 'true' %}
-m           disable the creation of menu items / shortcuts
{%- endif %}
-u           update an existing installation
{%- if has_conda %}
-t           run package tests after installation (may install conda-build)
{%-   if initialize_conda %}
-c           run 'conda init{{ ' --condabin' if initialize_conda == 'condabin' else ''}}' after installation (only applies to batch mode)
{%-   endif %}
{%- endif %}
"

{#-
# We used to have a getopt version here, falling back to getopts if needed
# However getopt is not standardized and the version on Mac has different
# behaviour. getopts is good enough for what we need :)
# More info: https://unix.stackexchange.com/questions/62950/
#}
{%- set getopts_str = "bifhkp:s" %}
{%- if enable_shortcuts == "true" %}
{%-   set getopts_str = getopts_str ~ "m" %}
{%- endif %}
{%- set getopts_str = getopts_str ~ "u" %}
{%- if has_conda %}
{%-   set getopts_str = getopts_str ~ "t" %}
{%-     if initialize_conda %}
{%-       set getopts_str = getopts_str ~ "c" %}
{%-     endif %}
{%- endif %}
while getopts "{{ getopts_str }}" x; do
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
{%- if enable_shortcuts == "true" %}
        m)
            SKIP_SHORTCUTS=1
            ;;
{%- endif %}
        u)
            FORCE=1
            ;;
{%- if has_conda %}
        t)
            TEST=1
            ;;
{%-   if initialize_conda %}
        c)
            INIT_CONDA=1
            ;;
{%-   endif %}
{%- endif %}
        ?)
            printf "ERROR: did not recognize option '%s', please try -h\\n" "$x"
            exit 1
            ;;
    esac
done

# For pre- and post-install scripts
export INSTALLER_UNATTENDED="$BATCH"

# For testing, keep the package cache around longer
CLEAR_AFTER_TEST=0
if [ "$TEST" = "1" ] && [ "$KEEP_PKGS" = "0" ]; then
    CLEAR_AFTER_TEST=1
    KEEP_PKGS=1
fi

if [ "$BATCH" = "0" ] # interactive mode
then
{%- if x86 and not x86_64 %}
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
{%- elif x86_64 %}
    if [ "$(uname -m)" != "x86_64" ]; then
        printf "WARNING:\\n"
        printf "    Your operating system appears not to be x86_64, but you are trying to\\n"
        printf "    install a x86_64 version of %s.\\n" "${INSTALLER_NAME}"
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
{%- elif ppc64le %}
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
{%- elif s390x %}
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
{%- elif aarch64 %}
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
{%- endif %}

{%- if osx %}
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
{%- elif linux %}
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
{%- endif %}

    printf "\\n"
    printf "Welcome to %s %s\\n" "${INSTALLER_NAME}" "${INSTALLER_VER}"
{%- if has_license %}
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
{{ license }}
EOF
    printf "\\n"
    printf "Do you accept the license terms? [yes|no]\\n"
    printf ">>> "
    read -r ans
    ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    while [ "$ans" != "YES" ] && [ "$ans" != "NO" ]
    do
        printf "Please answer 'yes' or 'no':\\n"
        printf ">>> "
        read -r ans
        ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    done
    if [ "$ans" != "YES" ]
    then
        printf "The license agreement wasn't approved, aborting installation.\\n"
        exit 2
    fi
{%- endif %}

    expand_user_input() {
        expanded_prefix=$(echo "${1}" | sed -r "s#^~#$HOME#")
        if command -v envsubst > /dev/null 2>&1; then
            envsubst << EOF
$expanded_prefix
EOF
        else
            echo "$expanded_prefix"
        fi
    }

    printf "\\n"
    printf "%s will now be installed into this location:\\n" "${INSTALLER_NAME}"
    printf "%s\\n" "$PREFIX"
    printf "\\n"
    printf "  - Press ENTER to confirm the location\\n"
    printf "  - Press CTRL-C to abort the installation\\n"
    printf "  - Or specify a different location below\\n"
    if ! command -v envsubst > /dev/null 2>&1; then
        printf "    Note: environment variables will NOT be expanded.\\n"
    fi
    printf "\\n"
    printf "[%s] >>> " "$PREFIX"
    read -r user_prefix
    if [ "$user_prefix" != "" ]; then
{%- if check_path_spaces %}
        case "$user_prefix" in
            *\ * )
                printf "ERROR: Cannot install into directories with spaces\\n" >&2
                exit 1
                ;;
            *)
                PREFIX="$(expand_user_input "${user_prefix}")"
                ;;
        esac
{%- else %}
        PREFIX="$(expand_user_input "${user_prefix}")"
{%- endif %}
    fi
fi # !BATCH

{%- if check_path_spaces %}
case "$PREFIX" in
    *\ * )
        printf "ERROR: Cannot install into directories with spaces\\n" >&2
        exit 1
        ;;
esac
{%- endif %}

if [ "$FORCE" = "0" ] && [ -e "$PREFIX" ]; then
    printf "ERROR: File or directory already exists: '%s'\\n" "$PREFIX" >&2
    printf "If you want to update an existing installation, use the -u option.\\n" >&2
    exit 1
elif [ "$FORCE" = "1" ] && [ -e "$PREFIX" ]; then
    REINSTALL=1
fi

total_installation_size_kb="{{ total_installation_size_kb }}"
total_installation_size_mb="$(( total_installation_size_kb / 1024 ))"
if ! mkdir -p "$PREFIX"; then
    printf "ERROR: Could not create directory: '%s'.\\n" "$PREFIX" >&2
    printf "Check permissions and available disk space (%s MB needed).\\n" "$total_installation_size_mb" >&2
    exit 1
fi

free_disk_space_kb="$(df -Pk "$PREFIX" | tail -n 1 | awk '{print $4}')"
free_disk_space_kb_with_buffer="$((free_disk_space_kb - 50 * 1024))"  # add 50MB of buffer
if [ "$free_disk_space_kb_with_buffer" -lt "$total_installation_size_kb" ]; then
    printf "ERROR: Not enough free disk space. Only %s MB are available, but %s MB are required (leaving a 50 MB buffer).\\n" \
        "$((free_disk_space_kb_with_buffer / 1024))" "$total_installation_size_mb" >&2
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
    range_size=$(( dd3_end - dd1_beg ))
    if [ $blk_siz -gt $range_size ]; then
        blk_siz=$range_size
    fi
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
# first payload: conda.exe
# second payload (optional): supporting files for conda.exe (only in conda-standalone onedir)
# third payload: conda packages
# the start of the first payload, in bytes, indexed from zero
boundary0=$(head -n "${last_line}" "${THIS_PATH}" | wc -c | sed 's/ //g')
# the start of the second payload / the end of the first payload, plus one
boundary1=$(( boundary0 + {{ first_payload_size }} ))
# the start of the third payload / the end of the second payload, plus one
boundary2=$(( boundary1 + {{ conda_exe_payloads_size }} ))
# the end of the third payload, plus one
boundary3=$(( boundary2 + {{ second_payload_size }} ))

# verify the MD5 sum of the tarball appended to this header
MD5=$(extract_range "${boundary0}" "${boundary3}" | {{ "md5" if osx else "md5sum -" }})

if ! echo "$MD5" | grep {{ installer_md5 }} >/dev/null; then
    printf "WARNING: md5sum mismatch of tar archive\\n" >&2
    printf "expected: {{ installer_md5 }}\\n" >&2
    printf "     got: %s\\n" "$MD5" >&2
fi

cd "$PREFIX"

# disable sysconfigdata overrides, since we want whatever was frozen to be used
unset PYTHON_SYSCONFIGDATA_NAME _CONDA_PYTHON_SYSCONFIGDATA_NAME

# the first binary payload: the standalone conda executable
printf "Unpacking bootstrapper...\n"
CONDA_EXEC="$PREFIX/_conda"
extract_range "${boundary0}" "${boundary1}" > "$CONDA_EXEC"
chmod +x "$CONDA_EXEC"
{%- for filename, (start, end, executable) in conda_exe_payloads|items %}
mkdir -p "$(dirname "$PREFIX/{{ filename }}")"
{%- if start == end %}
touch "$PREFIX/{{ filename }}"
{%- else %}
extract_range $(( boundary1 + {{ start }} )) $(( boundary1 + {{ end }} ))  > "$PREFIX/{{ filename }}"
{%- endif %}
{%- if executable %}
chmod +x "$PREFIX/{{ filename }}"
{%- endif %}
{%- endfor %}

export TMP_BACKUP="${TMP:-}"
export TMP="$PREFIX/install_tmp"
mkdir -p "$TMP"

# Check whether the virtual specs can be satisfied
# We need to specify CONDA_SOLVER=classic for conda-standalone
# to work around this bug in conda-libmamba-solver:
# https://github.com/conda/conda-libmamba-solver/issues/480
# micromamba needs an existing pkgs_dir to operate even offline,
# but we haven't created $PREFIX/pkgs yet... give it a temp location
# shellcheck disable=SC2050
{%- if virtual_specs %}
    echo "Checking virtual specs compatibility:" {{ virtual_specs }}
    CONDA_QUIET="$BATCH" \
    CONDA_SOLVER="classic" \
    CONDA_PKGS_DIRS="$(mktemp -d)" \
    "$CONDA_EXEC" create --dry-run --prefix "$PREFIX/envs/_virtual_specs_checks" --offline {{ virtual_specs }} {{ no_rcs_arg }}
{%- endif %}

# Create $PREFIX/.nonadmin if the installation didn't require superuser permissions
if [ "$(id -u)" -ne 0 ]; then
    touch "$PREFIX/.nonadmin"
fi

# the third binary payload: the tarball of packages
printf "Unpacking payload...\n"
extract_range "${boundary2}" "${boundary3}" | \
    CONDA_QUIET="$BATCH" "$CONDA_EXEC" constructor --extract-tarball --prefix "$PREFIX"

PRECONDA="$PREFIX/preconda.tar.bz2"
CONDA_QUIET="$BATCH" \
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-tarball < "$PRECONDA" || exit 1
rm -f "$PRECONDA"

CONDA_QUIET="$BATCH" \
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-conda-pkgs || exit 1

{%- if has_pre_install %}
if [ "$SKIP_SCRIPTS" = "1" ]; then
    export INST_OPT='--skip-scripts'
    printf "WARNING: skipping pre_install.sh by user request\\n" >&2
else
    export INST_OPT=''
    {%- if direct_execute_pre_install %}
    if ! "$PREFIX/pkgs/pre_install.sh"; then
    {%- else %}
    if ! sh "$PREFIX/pkgs/pre_install.sh"; then
    {%- endif %}
        printf "ERROR: executing pre_install.sh failed\\n" >&2
        exit 1
    fi
fi
{%- endif %}

MSGS="$PREFIX/.messages.txt"
touch "$MSGS"
export FORCE

{#-
# original issue report:
# https://github.com/ContinuumIO/anaconda-issues/issues/11148
# First try to fix it (this apparently didn't work; QA reported the issue again)
# https://github.com/conda/conda/pull/9073
# Avoid silent errors when $HOME is not writable
# https://github.com/conda/constructor/pull/669
#}
test -d ~/.conda || mkdir -p ~/.conda >/dev/null 2>/dev/null || test -d ~/.conda || mkdir ~/.conda

printf "\nInstalling base environment...\n\n"

{%- if enable_shortcuts == "true" %}
if [ "$SKIP_SHORTCUTS" = "1" ]; then
    shortcuts="--no-shortcuts"
else
    shortcuts="{{ shortcuts }}"
fi
{%- elif enable_shortcuts == "false" %}
shortcuts="--no-shortcuts"
{%- elif enable_shortcuts == "incompatible" %}
shortcuts=""
{%- endif %}

{%- set channels = final_channels|join(",") %}
# shellcheck disable=SC2086
CONDA_PROTECT_FROZEN_ENVS="0" \
CONDA_ROOT_PREFIX="$PREFIX" \
CONDA_REGISTER_ENVS="{{ register_envs }}" \
CONDA_SAFETY_CHECKS=disabled \
CONDA_EXTRA_SAFETY_CHECKS=no \
CONDA_CHANNELS="{{ channels }}" \
CONDA_PKGS_DIRS="$PREFIX/pkgs" \
CONDA_QUIET="$BATCH" \
"$CONDA_EXEC" install --offline --file "$PREFIX/conda-meta/initial-state.explicit.txt" -yp "$PREFIX" $shortcuts {{ no_rcs_arg }} || exit 1

{%- if has_conda %}
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
        env_channels="{{ channels }}"
    fi
    {%- if enable_shortcuts == "true" %}
    if [ "$SKIP_SHORTCUTS" = "1" ]; then
        env_shortcuts="--no-shortcuts"
    else
        # This file is guaranteed to exist, even if empty
        env_shortcuts=$(cat "${env_pkgs}shortcuts.txt")
        rm -f "${env_pkgs}shortcuts.txt"
    fi
    {%- elif enable_shortcuts == "false" %}
    env_shortcuts="--no-shortcuts"
    {%- elif enable_shortcuts == "incompatible" %}
    env_shortcuts=""
    {%- endif %}
    # shellcheck disable=SC2086
    CONDA_PROTECT_FROZEN_ENVS="0" \
    CONDA_ROOT_PREFIX="$PREFIX" \
    CONDA_REGISTER_ENVS="{{ register_envs }}" \
    CONDA_SAFETY_CHECKS=disabled \
    CONDA_EXTRA_SAFETY_CHECKS=no \
    CONDA_CHANNELS="$env_channels" \
    CONDA_PKGS_DIRS="$PREFIX/pkgs" \
    CONDA_QUIET="$BATCH" \
    "$CONDA_EXEC" install --offline --file "$PREFIX/envs/$env_name/conda-meta/initial-state.explicit.txt" -yp "$PREFIX/envs/$env_name" $env_shortcuts {{ no_rcs_arg }} || exit 1
done
{%- endif %}

{%- for condarc in write_condarc %}
{{ condarc }}
{%- endfor %}

POSTCONDA="$PREFIX/postconda.tar.bz2"
CONDA_QUIET="$BATCH" \
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-tarball < "$POSTCONDA" || exit 1
rm -f "$POSTCONDA"
rm -rf "$PREFIX/install_tmp"
export TMP="$TMP_BACKUP"


{%- if has_post_install %}
if [ "$SKIP_SCRIPTS" = "1" ]; then
    printf "WARNING: skipping post_install.sh by user request\\n" >&2
else
    {%- if direct_execute_post_install %}
    if ! "$PREFIX/pkgs/post_install.sh"; then
    {%- else %}
    if ! sh "$PREFIX/pkgs/post_install.sh"; then
    {%- endif %}
        printf "ERROR: executing post_install.sh failed\\n" >&2
        exit 1
    fi
fi
{%- endif %}

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
{{ conclusion_text }}
EOF

if [ "${PYTHONPATH:-}" != "" ]; then
    printf "WARNING:\\n"
    printf "    You currently have a PYTHONPATH environment variable set. This may cause\\n"
    printf "    unexpected behavior when running the Python interpreter in %s.\\n" "${INSTALLER_NAME}"
    printf "    For best results, please verify that your PYTHONPATH only points to\\n"
    printf "    directories of packages that are compatible with the Python interpreter\\n"
    printf "    in %s: %s\\n" "${INSTALLER_NAME}" "$PREFIX"
fi
{% if has_conda %}
{%- if initialize_conda == 'condabin' %}
_maybe_run_conda_init_condabin() {
    case $SHELL in
        # We call the module directly to avoid issues with spaces in shebang
        *zsh) "$PREFIX/bin/python" -m conda init --condabin zsh ;;
        *) "$PREFIX/bin/python" -m conda init --condabin ;;
    esac
}
{%- elif initialize_conda %}
_maybe_run_conda_init() {
    case $SHELL in
        # We call the module directly to avoid issues with spaces in shebang
        *zsh) "$PREFIX/bin/python" -m conda init zsh ;;
        *) "$PREFIX/bin/python" -m conda init ;;
    esac
    if [ -f "$PREFIX/bin/mamba" ]; then
        # If the version of mamba is <2.0.0, we preferably use the `mamba` python module
        # to perform the initialization.
        #
        # Otherwise (i.e. as of 2.0.0), we use the `mamba shell init` command
        if [ "$("$PREFIX/bin/mamba" --version | head -n 1 | cut -d' ' -f2 | cut -d'.' -f1)" -lt 2 ]; then
            case $SHELL in
                # We call the module directly to avoid issues with spaces in shebang
                *zsh) "$PREFIX/bin/python" -m mamba.mamba init zsh ;;
                *) "$PREFIX/bin/python" -m mamba.mamba init ;;
            esac
        else
            case $SHELL in
                *zsh) "$PREFIX/bin/mamba" shell init --shell zsh ;;
                *) "$PREFIX/bin/mamba" shell init ;;
            esac
        fi
    fi
}
{%- endif %}
{%- endif %}

if [ "$BATCH" = "0" ]; then
{%- if has_conda %}
{%-     if initialize_conda == 'condabin' %}
    DEFAULT={{ 'yes' if initialize_by_default else 'no' }}

    printf "Do you wish to update your shell profile to add '%s/condabin' to PATH?\\n" "$PREFIX"
    printf "This will enable you to run 'conda' anywhere, without injecting a shell function.\\n"
    printf "Note: You can undo this by running \`conda init --condabin --reverse\`\\n"
    printf "\\n"
    printf "Proceed with initialization? [yes|no]\\n"
    printf "[%s] >>> " "$DEFAULT"
    read -r ans
    if [ "$ans" = "" ]; then
        ans=$DEFAULT
    fi
    ans=$(echo "${ans}" | tr '[:lower:]' '[:upper:]')
    if [ "$ans" != "YES" ] && [ "$ans" != "Y" ]
    then
        printf "\\n"
        printf "'%s/condabin' will not be added to PATH.\\n" "$PREFIX"
    else
        _maybe_run_conda_init_condabin
    fi
{%-     elif initialize_conda %}
    DEFAULT={{ 'yes' if initialize_by_default else 'no' }}
    # Interactive mode.

    printf "Do you wish to update your shell profile to automatically initialize conda?\\n"
    printf "This will activate conda on startup and change the command prompt when activated.\\n"
    printf "If you'd prefer that conda's base environment not be activated on startup,\\n"
    printf "   run the following command when conda is activated:\\n"
    printf "\\n"
    printf "conda config --set auto_activate_base false\\n"
    printf "\\n"
    printf "Note: You can undo this later by running \`conda init --reverse \$SHELL\`\\n"
    printf "\\n"
    printf "Proceed with initialization? [yes|no]\\n"
    printf "[%s] >>> " "$DEFAULT"„
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
        _maybe_run_conda_init
    fi
{%-     endif %}
{%- endif %}

    printf "Thank you for installing %s!\\n" "${INSTALLER_NAME}"
{#- End of Interactive mode #}
{#- Batch mode #}
{%- if has_conda and initialize_conda %}
elif [ "$INIT_CONDA" = "1" ]; then
{%-     if initialize_conda == 'condabin' %}
        printf "Adding '%s/condabin' to PATH...\\n" "$PREFIX"
        _maybe_run_conda_init_condabin
{%-     else %}
        printf "Initializing '%s' with 'conda init'...\\n" "$PREFIX"
        _maybe_run_conda_init
{%-     endif %}
{%- endif %}
{#- End of Batch mode #}
fi


{%- if has_conda %}
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
{%- endif %}

exit 0
# shellcheck disable=SC2317
@@END_HEADER@@
