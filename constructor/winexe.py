# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import logging
import os
import shutil
import sys
import tempfile
from os.path import abspath, basename, dirname, isfile, join
from pathlib import Path
from subprocess import check_output, run
from typing import List, Union

from .construct import ns_platform
from .imaging import write_images
from .jinja import render_template
from .preconda import copy_extra_files
from .preconda import write_files as preconda_write_files
from .signing import AzureSignTool, WindowsSignTool
from .utils import (
    add_condarc,
    approx_size_kb,
    filename_dist,
    get_final_channels,
    make_VIProductVersion,
    shortcuts_flags,
    win_str_esc,
)

NSIS_DIR = join(abspath(dirname(__file__)), 'nsis')
MAKENSIS_EXE = abspath(join(sys.prefix, 'NSIS', 'makensis.exe'))

logger = logging.getLogger(__name__)


def read_nsi_tmpl(info) -> str:
    path = abspath(info.get('nsis_template', join(NSIS_DIR, 'main.nsi.tmpl')))
    logger.info('Reading: %s', path)
    with open(path) as fi:
        return fi.read()


def pkg_commands(download_dir, dists):
    for fn in dists:
        yield 'File %s' % win_str_esc(join(download_dir, fn))


def extra_files_commands(paths, common_parent):
    paths = sorted([Path(p) for p in paths])
    lines = []
    current_output_path = "$INSTDIR"
    for path in paths:
        relative_parent = path.relative_to(common_parent).parent
        output_path = f"$INSTDIR\\{relative_parent}"
        if output_path != current_output_path:
            lines.append(f"SetOutPath {output_path}")
            current_output_path = output_path
        lines.append(f"File {path}")
    return lines


def insert_tempfiles_commands(paths: os.PathLike) -> List[str]:
    """Helper function that copies paths into temporary install directory.

    Args:
        paths (os.PathLike): Paths to files that need to be copied

    Returns:
        List[str]: Commands to be inserted into nsi template
    """
    if not paths:
        return []
    # Setting OutPath to PluginsDir so NSIS File command copies the path into the PluginsDir
    lines = ['SetOutPath $PLUGINSDIR']
    for path in sorted([Path(p) for p in paths]):
        lines.append(f"File {path}")
    return lines


def setup_script_env_variables(info) -> List[str]:
    """Helper function to insert extra environment variables into nsis template.

    Args:
        info: Dictionary of information parsed from construct.yaml

    Returns:
        List[str]: Commands to be inserted into nsi template
    """
    lines = []
    for name, value in info.get('script_env_variables', {}).items():
        lines.append(
            "System::Call 'kernel32::SetEnvironmentVariable(t,t)i"
            + f"""("{name}", {win_str_esc(value)}).r0'""")
    return lines


def custom_nsi_insert_from_file(filepath: os.PathLike) -> str:
    """Insert NSI script commands from file.

    Args:
        filepath (os.PathLike): Path to file

    Returns:
        string block of file
    """
    if not filepath:
        return ''
    return Path(filepath).read_text()


def setup_envs_commands(info, dir_path):
    template = r"""
        # Set up {name} env
        SetDetailsPrint both
        ${{Print}} "Setting up the {name} environment..."
        SetDetailsPrint listonly

        # List of packages to install
        SetOutPath "{env_txt_dir}"
        File "{env_txt_abspath}"

        # A conda-meta\history file is required for a valid conda prefix
        SetOutPath "{conda_meta}"
        File "{history_abspath}"

        # Set channels
        System::Call 'kernel32::SetEnvironmentVariable(t,t)i("CONDA_CHANNELS", "{channels}").r0'
        # Set register_envs
        System::Call 'kernel32::SetEnvironmentVariable(t,t)i("CONDA_REGISTER_ENVS", "{register_envs}").r0'

        # Run conda install
        ${{If}} $Ana_CreateShortcuts_State = ${{BST_CHECKED}}
            ${{Print}} "Installing packages for {name}, creating shortcuts if necessary..."
            push '"$INSTDIR\_conda.exe" install --offline -yp "{prefix}" --file "{env_txt}" {shortcuts} {no_rcs_arg}'
        ${{Else}}
            ${{Print}} "Installing packages for {name}..."
            push '"$INSTDIR\_conda.exe" install --offline -yp "{prefix}" --file "{env_txt}" --no-shortcuts {no_rcs_arg}'
        ${{EndIf}}
        push 'Failed to link extracted packages to {prefix}!'
        push 'WithLog'
        SetDetailsPrint listonly
        call AbortRetryNSExecWait
        SetDetailsPrint both

        # Cleanup {name} env.txt
        SetOutPath "$INSTDIR"
        Delete "{env_txt}"

        # Restore shipped conda-meta\history for remapped
        # channels and retain only the first transaction
        SetOutPath "{conda_meta}"
        File "{history_abspath}"
        """  # noqa

    lines = template.format(  # this one block is for the base environment
        name="base",
        prefix=r"$INSTDIR",
        env_txt=r"$INSTDIR\pkgs\env.txt",  # env.txt as seen by the running installer
        env_txt_dir=r"$INSTDIR\pkgs",  # env.txt location in the installer filesystem
        env_txt_abspath=join(dir_path, "env.txt"),  # env.txt location while building the installer
        conda_meta=r"$INSTDIR\conda-meta",
        history_abspath=join(dir_path, "conda-meta", "history"),
        channels=','.join(get_final_channels(info)),
        shortcuts=shortcuts_flags(info),
        register_envs=str(info.get("register_envs", True)).lower(),
        no_rcs_arg=info.get("_ignore_condarcs_arg", ""),
    ).splitlines()
    # now we generate one more block per extra env, if present
    for env_name in info.get("_extra_envs_info", {}):
        lines += ["", ""]
        env_info = info["extra_envs"][env_name]
        # Needed for shortcuts_flags function
        if "_conda_exe_type" not in env_info:
            env_info["_conda_exe_type"] = info.get("_conda_exe_type")
        channel_info = {
            "channels": env_info.get("channels", info.get("channels", ())),
            "channels_remap": env_info.get("channels_remap", info.get("channels_remap", ()))
        }
        lines += template.format(
            name=env_name,
            prefix=join("$INSTDIR", "envs", env_name),
            env_txt=join("$INSTDIR", "pkgs", "envs", env_name, "env.txt"),
            env_txt_dir=join("$INSTDIR", "pkgs", "envs", env_name),
            env_txt_abspath=join(dir_path, "envs", env_name, "env.txt"),
            conda_meta=join("$INSTDIR", "envs", env_name, "conda-meta"),
            history_abspath=join(dir_path, "envs", env_name, "conda-meta", "history"),
            channels=",".join(get_final_channels(channel_info)),
            shortcuts=shortcuts_flags(env_info),
            register_envs=str(info.get("register_envs", True)).lower(),
            no_rcs_arg=info.get("_ignore_condarcs_arg", ""),
        ).splitlines()

    return [line.strip() for line in lines]


def uninstall_menus_commands(info):
    tmpl = r"""
        SetDetailsPrint both
        ${{Print}} "Deleting {name} menus in {env_name}..."
        SetDetailsPrint listonly
        push '"$INSTDIR\_conda.exe" constructor --prefix "{path}" --rm-menus'
        push 'Failed to delete menus in {env_name}'
        push 'WithLog'
        call un.AbortRetryNSExecWait
        SetDetailsPrint both
        """
    lines = tmpl.format(name=info["name"], env_name="base", path="$INSTDIR").splitlines()
    for env_name in info.get("_extra_envs_info", {}):
        path = join("$INSTDIR", "envs", env_name)
        lines += tmpl.format(name=info["name"], env_name=env_name, path=path).splitlines()
    return [line.strip() for line in lines]


def make_nsi(
    info: dict,
    dir_path: str,
    extra_files: List = None,
    temp_extra_files: List = None,
    signing_tool: Union[AzureSignTool, WindowsSignTool] = None,
):
    "Creates the tmp/main.nsi from the template file"

    if extra_files is None:
        extra_files = []
    if temp_extra_files is None:
        temp_extra_files = []
    name = info['name']
    download_dir = info['_download_dir']

    dists = info['_dists'].copy()
    for env_info in info["_extra_envs_info"].values():
        dists += env_info["_dists"]
    dists = list({dist: None for dist in dists})  # de-duplicate

    py_name, py_version, unused_build = filename_dist(dists[0]).rsplit('-', 2)
    assert py_name == 'python'
    arch = int(info['_platform'].split('-')[1])
    info['pre_install_desc'] = info.get('pre_install_desc', "")
    info['post_install_desc'] = info.get('post_install_desc', "")

    variables = {
        'installer_name': name,
        'installer_version': info['version'],
        'company': info.get('company', 'Unknown, Inc.'),
        'installer_platform': info['_platform'],
        'arch': '%d-bit' % arch,
        'py_ver': ".".join(py_version.split(".")[:2]),
        'pyversion_justdigits': ''.join(py_version.split('.')),
        'pyversion': py_version,
        'pyversion_major': py_version.split('.')[0],
        'default_prefix': info.get('default_prefix', join('%USERPROFILE%', name.lower())),
        'default_prefix_domain_user': info.get('default_prefix_domain_user',
                                               join('%LOCALAPPDATA%', name.lower())),
        'default_prefix_all_users': info.get('default_prefix_all_users',
                                             join('%ALLUSERSPROFILE%', name.lower())),
        'pre_install_desc': info['pre_install_desc'],
        'post_install_desc': info['post_install_desc'],
        'enable_shortcuts': "yes" if info['_enable_shortcuts'] is True else "no",
        'show_register_python': "yes" if info.get("register_python", True) else "no",
        'show_add_to_path': "yes" if info.get("initialize_conda", True) else "no",
        'outfile': info['_outpath'],
        'vipv': make_VIProductVersion(info['version']),
        'constructor_version': info['CONSTRUCTOR_VERSION'],
        'iconfile': '@icon.ico',
        'headerimage': '@header.bmp',
        'welcomeimage': '@welcome.bmp',
        'licensefile': abspath(info.get('license_file', join(NSIS_DIR, 'placeholder_license.txt'))),
        'conda_history': '@' + join('conda-meta', 'history'),
        'conda_exe': '@_conda.exe',
        'env_txt': '@env.txt',
        'urls_file': '@urls',
        'urls_txt_file': '@urls.txt',
        'pre_install': '@pre_install.bat',
        'post_install': '@post_install.bat',
        'pre_uninstall': '@pre_uninstall.bat',
        'index_cache': '@cache',
        'repodata_record': '@repodata_record.json',
    }

    conclusion_text = info.get("conclusion_text", "")
    if conclusion_text:
        conclusion_lines = conclusion_text.strip().splitlines()
        variables['conclusion_title'] = conclusion_lines[0].strip()
        # See https://nsis.sourceforge.io/Docs/Modern%20UI/Readme.html#toggle_pgf
        # for the newlines business
        variables['conclusion_text'] = "\r\n".join(conclusion_lines[1:])

    for key in ['welcome_file', 'conclusion_file', 'post_install_pages']:
        value = info.get(key, "")
        if not value:
            continue
        if isinstance(value, str) and not value.endswith(".nsi"):
            logger.warning(
                "On Windows, %s must be an .nsi file; %s will be ignored.",
                key,
                value,
            )
        elif isinstance(value, list):
            valid_values = []
            for val in value:
                if val.endswith(".nsi"):
                    valid_values.append(val)
                else:
                    logger.warning(
                        "On Windows, %s must be .nsi files; %s will be ignored.",
                        key,
                        val,
                    )
                info[key] = valid_values

    for key, value in variables.items():
        if value.startswith('@'):
            value = join(dir_path, value[1:])
        variables[key] = win_str_esc(value)

    # From now on, the items added to variables will NOT be escaped

    # These are mostly booleans we use with if-checks
    variables.update(ns_platform(info['_platform']))
    variables['initialize_conda'] = info.get('initialize_conda', True)
    variables['initialize_by_default'] = info.get('initialize_by_default', None)
    variables['register_python'] = info.get('register_python', True)
    variables['register_python_default'] = info.get('register_python_default', None)
    variables['check_path_length'] = info.get('check_path_length', None)
    variables['check_path_spaces'] = info.get('check_path_spaces', True)
    variables['keep_pkgs'] = info.get('keep_pkgs') or False
    variables['pre_install_exists'] = bool(info.get('pre_install'))
    variables['post_install_exists'] = bool(info.get('post_install'))
    variables['with_conclusion_text'] = bool(conclusion_text)
    variables["enable_debugging"] = bool(os.environ.get("NSIS_USING_LOG_BUILD"))
    variables["has_conda"] = info["_has_conda"]
    variables["custom_welcome"] = info.get("welcome_file", "").endswith(".nsi")
    variables["custom_conclusion"] = info.get("conclusion_file", "").endswith(".nsi")
    variables["has_license"] = bool(info.get("license_file"))
    variables["post_install_pages"] = bool(info.get("post_install_pages"))

    approx_pkgs_size_kb = approx_size_kb(info, "pkgs")

    # UPPERCASE variables are unescaped (and unquoted)
    variables['NAME'] = name
    variables['NSIS_DIR'] = NSIS_DIR
    variables['BITS'] = str(arch)
    variables['PKG_COMMANDS'] = '\n    '.join(pkg_commands(download_dir, dists))
    variables['SIGNTOOL_COMMAND'] = signing_tool.get_signing_command() if signing_tool else ""
    variables['SETUP_ENVS'] = '\n    '.join(setup_envs_commands(info, dir_path))
    variables['WRITE_CONDARC'] = '\n    '.join(add_condarc(info))
    variables['SIZE'] = approx_pkgs_size_kb
    variables['UNINSTALL_NAME'] = info.get(
        'uninstall_name',
        '${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})'
    )
    variables['UNINSTALL_MENUS'] = '\n    '.join(uninstall_menus_commands(info))
    variables['EXTRA_FILES'] = '\n    '.join(extra_files_commands(extra_files, dir_path))
    variables['SCRIPT_ENV_VARIABLES'] = '\n    '.join(setup_script_env_variables(info))
    variables['CUSTOM_WELCOME_FILE'] = (
        custom_nsi_insert_from_file(info.get('welcome_file', ''))
        if variables['custom_welcome']
        else ''
    )
    variables['CUSTOM_CONCLUSION_FILE'] = (
        custom_nsi_insert_from_file(info.get('conclusion_file', ''))
        if variables['custom_conclusion']
        else ''
    )
    if isinstance(info.get("post_install_pages"), str):
        variables["POST_INSTALL_PAGES"] = custom_nsi_insert_from_file(info["post_install_pages"])
    else:
        variables['POST_INSTALL_PAGES'] = '\n'.join(
            custom_nsi_insert_from_file(file) for file in info.get('post_install_pages', [])
        )
    variables['TEMP_EXTRA_FILES'] = '\n    '.join(insert_tempfiles_commands(temp_extra_files))
    variables['VIRTUAL_SPECS'] = " ".join([f'"{spec}"' for spec in info.get("virtual_specs", ())])
    # This is the same but without quotes so we can print it fine
    variables['VIRTUAL_SPECS_DEBUG'] = " ".join([spec for spec in info.get("virtual_specs", ())])
    variables['LICENSEFILENAME'] = basename(info.get('license_file', 'placeholder_license.txt'))
    variables['NO_RCS_ARG'] = info.get('_ignore_condarcs_arg', '')

    data = render_template(read_nsi_tmpl(info), **variables)
    if info['_platform'].startswith("win") and sys.platform != 'win32':
        # Branding /TRIM commannd is unsupported on non win platform
        data_lines = data.split("\n")
        for i, line in enumerate(data_lines):
            if "/TRIM" in line:
                del data_lines[i]
                break
        data = "\n".join(data_lines)

    nsi_path = join(dir_path, 'main.nsi')
    with open(nsi_path, 'w') as fo:
        fo.write(data)
    # Uncomment to see the file for debugging
    # with open('main.nsi', 'w') as fo:
    #     fo.write(data)
    # Copy all the NSIS header files (*.nsh)
    for fn in os.listdir(NSIS_DIR):
        if fn.endswith('.nsh'):
            shutil.copy(join(NSIS_DIR, fn),
                        join(dir_path, fn))

    logger.info('Created %s file', nsi_path)
    return nsi_path


def verify_nsis_install():
    logger.info("Checking for '%s'", MAKENSIS_EXE)
    if not isfile(MAKENSIS_EXE):
        sys.exit("""
Error: no file %s
    please make sure nsis is installed:
    > conda install nsis
""" % MAKENSIS_EXE)
    if sys.platform == "win32":
        out = check_output([MAKENSIS_EXE, '/VERSION'])
    else:
        out = check_output([MAKENSIS_EXE, '-VERSION'])
    out = out.decode('utf-8').strip()
    logger.info("NSIS version: %s", out)
    for dn in 'x86-unicode', 'x86-ansi', '.':
        untgz_dll = abspath(join(sys.prefix, 'NSIS',
                                 'Plugins', dn, 'untgz.dll'))
        if isfile(untgz_dll):
            break
    else:
        sys.exit("Error: no file untgz.dll")


def create(info, verbose=False):
    verify_nsis_install()
    signing_tool = None
    if signing_tool_name := info.get("windows_signing_tool"):
        if signing_tool_name == "signtool":
            signing_tool = WindowsSignTool(
                certificate_file=info.get("signing_certificate")
            )
        elif signing_tool_name == "azuresigntool":
            signing_tool = AzureSignTool()
        else:
            raise ValueError(f"Unknown signing tool: {signing_tool_name}")
        signing_tool.verify_signing_tool()
    tmp_dir = tempfile.mkdtemp()
    preconda_write_files(info, tmp_dir)
    copied_extra_files = copy_extra_files(info.get("extra_files", []), tmp_dir)
    copied_temp_extra_files = copy_extra_files(info.get("temp_extra_files", []), tmp_dir)
    shutil.copyfile(info['_conda_exe'], join(tmp_dir, '_conda.exe'))

    pre_dst = join(tmp_dir, 'pre_install.bat')
    pre_install_script = info.get("pre_install")
    if pre_install_script:
        shutil.copy(pre_install_script, pre_dst)

    post_dst = join(tmp_dir, 'post_install.bat')
    try:
        shutil.copy(info['post_install'], post_dst)
    except KeyError:
        with open(post_dst, 'w') as fo:
            fo.write(":: this is an empty post install .bat script\n")

    preun_dst = join(tmp_dir, 'pre_uninstall.bat')
    try:
        shutil.copy(info['pre_uninstall'], preun_dst)
    except KeyError:
        with open(preun_dst, 'w') as fo:
            fo.write(":: this is an empty pre uninstall .bat script\n")

    write_images(info, tmp_dir)
    nsi = make_nsi(
        info,
        tmp_dir,
        extra_files=copied_extra_files,
        temp_extra_files=copied_temp_extra_files,
        signing_tool=signing_tool,
    )
    verbosity = f"{'/' if sys.platform == 'win32' else '-'}V{4 if verbose else 2}"
    args = [MAKENSIS_EXE, verbosity, nsi]
    logger.info('Calling: %s', args)
    process = run(args, capture_output=True, text=True)
    if process.returncode:
        logger.info("makensis stdout:\n'%s'", process.stdout)
        logger.error("makensis stderr:\n'%s'", process.stderr)
        sys.exit(f"Failed to run {args}. Exit code: {process.returncode}.")
    else:
        logger.debug("makensis stdout:\n'%s'", process.stdout)
        logger.debug("makensis stderr:\n'%s'", process.stderr)

    if signing_tool:
        signing_tool.verify_signature(info['_outpath'])

    shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    make_nsi({'name': 'Maxi', 'version': '1.2',
              '_platform': 'win-64',
              '_outpath': 'dummy.exe',
              '_download_dir': 'dummy',
              '_dists': ['python-2.7.9-0.tar.bz2',
                         'vs2008_runtime-1.0-1.tar.bz2']},
             '.')
