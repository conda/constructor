import logging
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from os.path import abspath, dirname, exists, isdir, join
from pathlib import Path
from plistlib import dump as plist_dump
from tempfile import NamedTemporaryFile

from . import preconda
from .conda_interface import conda_context
from .construct import ns_platform, parse
from .imaging import write_images
from .utils import (
    add_condarc,
    approx_size_kb,
    explained_check_call,
    fill_template,
    get_final_channels,
    preprocess,
    rm_rf,
)

OSX_DIR = join(dirname(__file__), "osx")
CACHE_DIR = PACKAGE_ROOT = PACKAGES_DIR = SCRIPTS_DIR = None

logger = logging.getLogger(__name__)


def calculate_install_dir(yaml_file, subdir=None):
    contents = parse(yaml_file, subdir or conda_context.subdir)
    if contents.get("installer_type") == "sh":
        return contents["name"]
    name = contents.get("pkg_name") or contents["name"]
    location = contents.get("default_location_pkg")
    if location:
        return f"{location}/{name}"
    return name


def write_readme(dst, info):

    src = join(OSX_DIR, 'readme_header.rtf')
    with open(src) as fi:
        data = fi.read()

    # This is necessary for when installing on case-sensitive macOS filesystems.
    data = data.replace('__NAME_LOWER__', info.get("pkg_name", info['name']).lower())
    data = data.replace('__NAME__', info['name'])
    data = data.replace('__VERSION__', info['version'])

    with open(dst, 'w') as f:
        f.write(data)

        all_dists = info["_dists"].copy()
        for env_info in info.get("_extra_envs_info", {}).values():
            all_dists += env_info["_dists"]
        all_dists = list({dist: None for dist in all_dists})  # de-duplicate

        # TODO: Split output by env name
        for dist in sorted(all_dists):
            if dist.startswith('_'):
                continue
            f.write("{\\listtext\t\n\\f1 \\uc0\\u8259 \n\\f0 \t}%s %s\\\n" %
                    tuple(dist.rsplit('-', 2)[:2]))
        f.write('}')


def _detect_mimetype(path: str):
    extension = Path(path).suffix.lower().strip(".")
    if extension == "rtf":
        return "richtext/rtf"
    if extension in ("html", "htm"):
        return "text/html"
    # we assume it's plain text
    return "text/plain"


def modify_xml(xml_path, info):
    # See
    # http://developer.apple.com/library/mac/#documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html#//apple_ref/doc/uid/TP40005370-CH100-SW20
    # for all the options you can put here.

    tree = ET.parse(xml_path)
    root = tree.getroot()

    title = ET.Element('title')
    title.text = f"{info['name']} {info['version']}"
    root.append(title)

    license = ET.Element('license', file=info.get('license_file',
                                                  'No license'))
    root.append(license)

    # -- BACKGROUND -- #
    # Default setting for the background was using Anaconda's logo
    # located at ./osx/MacInstaller.png. If `welcome_image` or
    # `welcome_image_text` are not provided, this will still happen.
    # However, if the user provides one of those, we will use that instead.
    # If no background is desired, set `welcome_image` to None
    if "welcome_image" in info:
        if not info["welcome_image"]:
            background_path = None
        else:
            write_images(info, PACKAGES_DIR, os="osx")
            background_path = os.path.join(PACKAGES_DIR, "welcome.png")
    elif "welcome_image_text" in info:
        write_images(info, PACKAGES_DIR, os="osx")
        background_path = os.path.join(PACKAGES_DIR, "welcome.png")
    else:
        # Default to Anaconda's logo if the keys above were not specified
        background_path = join(OSX_DIR, 'MacInstaller.png')

    if background_path:
        logger.info("Using background image: %s", background_path)
        for key in ("background", "background-darkAqua"):
            background = ET.Element(key,
                                    file=background_path,
                                    scaling='proportional',
                                    alignment='center')
            root.append(background)

    # -- WELCOME -- #
    # The endswith .nsi is for windows specifically.  The nsi script will add in
    # welcome pages if added.
    if "welcome_file" in info and not info["welcome_file"].endswith(".nsi"):
        welcome_path = info["welcome_file"]
    elif "welcome_text" in info and info["welcome_text"]:
        welcome_path = join(PACKAGES_DIR, "welcome.txt")
        with open(welcome_path, "w") as f:
            f.write(info["welcome_text"])
    else:
        welcome_path = None
        if info.get("welcome_file", "").endswith(".nsi"):
            logger.info("Warning: NSI welcome_file, %s, is ignored.", info['welcome_file'])

    if welcome_path:
        welcome = ET.Element(
            'welcome', file=welcome_path,
            attrib={'mime-type': _detect_mimetype(welcome_path)}
        )
        root.append(welcome)

    # -- CONCLUSION -- #
    # The endswith .nsi is for windows specifically.  The nsi script will add in
    # conclusion pages if added.
    if "conclusion_file" in info and not info["conclusion_file"].endswith(".nsi"):
        conclusion_path = info["conclusion_file"]
    elif "conclusion_text" in info:
        if not info["conclusion_text"]:
            conclusion_path = None
        else:
            conclusion_path = join(PACKAGES_DIR, "conclusion.txt")
            with open(conclusion_path, "w") as f:
                f.write(info["conclusion_text"])
    else:
        conclusion_path = join(OSX_DIR, 'acloud.rtf')
        if info.get("conclusion_file", "").endswith(".nsi"):
            logger.warning("NSI conclusion_file '%s' is ignored.", info['conclusion_file'])
    if conclusion_path:
        conclusion = ET.Element(
            'conclusion', file=conclusion_path,
            attrib={'mime-type': _detect_mimetype(conclusion_path)}
        )
        root.append(conclusion)
    # when not provided, conclusion defaults to a system message

    # -- README -- #
    if "readme_file" in info:
        readme_path = info["readme_file"]
    elif "readme_text" in info:
        if not info["readme_text"]:
            readme_path = None
        else:
            readme_path = join(PACKAGES_DIR, "readme.txt")
            with open(readme_path, "w") as f:
                f.write(info["readme_text"])
    else:
        readme_path = join(PACKAGES_DIR, "readme.rtf")
        write_readme(readme_path, info)

    if readme_path:
        readme = ET.Element(
            'readme', file=readme_path,
            attrib={'mime-type': _detect_mimetype(readme_path)}
        )
        root.append(readme)

    # See below for an explanation of the consequences of this
    # customLocation value.
    for options in root.findall('options'):
        options.set('customize', 'allow')
        options.set('customLocation', '/')

    # By default, the package builder puts all of our options under
    # a single master choice. This deletes that master choice and
    # allows the user to see all options without effort.
    for choices_outline in root.findall('choices-outline'):
        [child] = list(choices_outline)
        choices_outline.extend(list(child))
        choices_outline.remove(child)

    for path_choice in root.findall('choice'):
        ident = path_choice.get('id')
        if ident == 'default':
            root.remove(path_choice)
        elif ident.endswith('prepare_installation'):
            path_choice.set('visible', 'true')
            path_choice.set('title', 'Install {}'.format(info['name']))
            path_choice.set('enabled', 'false')
        elif ident.endswith('run_installation'):
            # We leave this one out on purpose! The user does not need to
            # know we separated the installation in two steps to accommodate
            # for the pre-install scripts optionality
            path_choice.set('visible', 'false')
            path_choice.set('title', 'Apply {}'.format(info['name']))
            path_choice.set('enabled', 'false')
        elif ident.endswith('user_pre_install') and info.get('pre_install_desc'):
            path_choice.set('visible', 'true')
            path_choice.set('title', "Run the pre-install script")
            path_choice.set('description', ' '.join(info['pre_install_desc'].split()))
        elif ident.endswith('user_post_install') and info.get('post_install_desc'):
            path_choice.set('visible', 'true')
            path_choice.set('title', "Run the post-install script")
            path_choice.set('description', ' '.join(info['post_install_desc'].split()))
        elif ident.endswith('pathupdate'):
            has_conda = info.get('_has_conda', True)
            path_choice.set('visible', 'true' if has_conda else 'false')
            path_choice.set('start_selected', 'true' if has_conda and info.get(
                'initialize_by_default', True) else 'false')
            path_choice.set('title', "Add conda initialization to the shell")
            path_description = """
            If this box is checked, conda will be automatically activated in your
            preferred shell on startup. This will change the command prompt when
            activated. If your prefer that conda's base environment not be activated
            on startup, run `conda config --set auto_activate_base false`. You can
            undo this by running `conda init --reverse ${SHELL}`.
            If unchecked, you must this initialization yourself or activate the
            environment manually for each shell in which you wish to use it."""
            path_choice.set('description', ' '.join(path_description.split()))
        elif ident.endswith('cacheclean'):
            path_choice.set('visible', 'true')
            path_choice.set('title', "Clear the package cache")
            path_choice.set('start_selected', 'false' if info.get('keep_pkgs') else 'true')
            cache_size_mb = approx_size_kb(info, "tarballs") // 1024
            size_text = f"~{cache_size_mb}MB" if cache_size_mb > 0 else "some space"
            path_description = f"""
            If this box is checked, the package cache will be cleaned after the
            installer is complete, reclaiming {size_text}. If unchecked, the
            package cache contents will be preserved.
            """
            path_choice.set('description', ' '.join(path_description.split()))

    # The "customLocation" option is set above to "/", which
    # means that the installer defaults to the following locations:
    # - Install for all users: /<name>
    # - Install for this user: /Users/<username>/<name>
    # - Install on a specific disk: /<custom_root>/<name>
    # On modern Mac systems, installing in root is not allowed. So
    # we remove this option by not supplying enable_localSystem
    # below. Alternatively, we could have chosen not to set the
    # value of customLocation and we would have obtained this:
    # - Install for all users: /Applications/<name>
    # - Install for this user: /Users/<username>/Applications/<name>
    # - Install on a specific disk: /<custom_root>/<name>
    # We have chosen not to do this so that this installer
    # produces the same results as a shell install.
    domains = ET.Element('domains',
                         enable_anywhere='true',
                         enable_currentUserHome='true')
    root.append(domains)
    tree.write(xml_path)


def move_script(src, dst, info, ensure_shebang=False, user_script_type=None):
    """
    Fill template scripts checks_before_install.sh, prepare_installation.sh and others,
    and move them to the installer workspace.
    """
    assert user_script_type in (None, "pre_install", "post_install")
    with open(src) as fi:
        data = fi.read()

    # ppd hosts the conditions for the #if/#else/#endif preprocessors on scripts
    ppd = ns_platform(info['_platform'])
    ppd['check_path_spaces'] = bool(info.get("check_path_spaces", True))

    # This is necessary for when installing on case-sensitive macOS filesystems.
    pkg_name_lower = info.get("pkg_name", info['name']).lower()
    default_path_exists_error_text = (
        "'{CHOSEN_PATH}' already exists. Please, relaunch the installer and "
        "choose another location in the Destination Select step."
    )
    path_exists_error_text = info.get(
        "install_path_exists_error_text", default_path_exists_error_text
    ).format(CHOSEN_PATH=f"$2/{pkg_name_lower}")
    replace = {
        'NAME': info['name'],
        'NAME_LOWER': pkg_name_lower,
        'VERSION': info['version'],
        'PLAT': info['_platform'],
        'CHANNELS': ','.join(get_final_channels(info)),
        'WRITE_CONDARC': '\n'.join(add_condarc(info)),
        'PATH_EXISTS_ERROR_TEXT': path_exists_error_text,
        'PROGRESS_NOTIFICATIONS': str(info.get('progress_notifications', False)),
        'PRE_OR_POST': user_script_type or '__PRE_OR_POST__',
        'CONSTRUCTOR_VERSION': info['CONSTRUCTOR_VERSION'],
    }
    data = preprocess(data, ppd)
    custom_variables = info.get('extra_env_variables', {})
    data = fill_template(data, replace)

    data = data.replace("_EXTRA_ENV_VARIABLES_=''", '\n'.join([f'export {key}={value}' for key, value in custom_variables.items()]))


    with open(dst, 'w') as fo:
        if (
            ensure_shebang
            and os.path.splitext(dst)[1] in ('', '.sh')
            and not data.startswith(("#!/bin/bash", "#!/bin/sh"))
        ):
            # Shell scripts provided by the user require a shebang, otherwise it
            # will fail to start with error posix_spawn 8
            # We only handle shell scripts this way
            fo.write("#!/bin/bash\n")
        fo.write(data)
    os.chmod(dst, 0o755)


def fresh_dir(dir_path):
    rm_rf(dir_path)
    assert not exists(dir_path)
    os.mkdir(dir_path)


def pkgbuild(name, identifier=None, version=None, install_location=None):
    "see `man pkgbuild` for the meaning of optional arguments"
    if identifier is None:
        identifier = "io.continuum"
    args = [
        "pkgbuild",
        "--root", PACKAGE_ROOT,
        "--identifier", "%s.pkg.%s" % (identifier, name),
        "--ownership", "preserve",
    ]

    if isdir(SCRIPTS_DIR) and os.listdir(SCRIPTS_DIR):
        args += ["--scripts", SCRIPTS_DIR]
    if version:
        args += ["--version", version]
    if install_location is not None:
        args += ["--install-location", install_location]
    output = os.path.join(PACKAGES_DIR, f"{name}.pkg")
    args += [output]
    explained_check_call(args)
    return output


def pkgbuild_prepare_installation(info):
    pkg = pkgbuild(
        "prepare_installation",
        identifier=info.get("reverse_domain_identifier"),
        version=info["version"],
        install_location=info.get("default_location_pkg"),
    )

    approx_pkgs_size_kb = approx_size_kb(info, "pkgs")
    if approx_pkgs_size_kb <= 0:
        return pkg

    # We need to patch the estimated install size because it's initially
    # set to the sum of the compressed tarballs, which is not representative
    try:
        # expand to apply patches
        explained_check_call(["pkgutil", "--expand", pkg, f"{pkg}.expanded"])
        payload_xml = os.path.join(f"{pkg}.expanded", "PackageInfo")
        tree = ET.parse(payload_xml)
        root = tree.getroot()
        payload = root.find("payload")
        payload.set("installKBytes", str(approx_pkgs_size_kb))
        tree.write(payload_xml)
        # repack
        explained_check_call(["pkgutil", "--flatten", f"{pkg}.expanded", pkg])
        return pkg
    finally:
        shutil.rmtree(f"{pkg}.expanded")


def pkgbuild_script(name, info, src, dst='postinstall', **kwargs):
    fresh_dir(SCRIPTS_DIR)
    fresh_dir(PACKAGE_ROOT)
    move_script(join(OSX_DIR, src), join(SCRIPTS_DIR, dst), info, **kwargs)
    pkgbuild(
        name,
        identifier=info.get("reverse_domain_identifier"),
        install_location=info.get("default_location_pkg"),
    )
    rm_rf(SCRIPTS_DIR)


def create(info, verbose=False):
    # Do some configuration checks
    if info.get("check_path_spaces", True) is True:
        for key in "default_location_pkg", "pkg_name":
            if " " in info.get(key, ""):
                sys.exit(
                    f"ERROR: 'check_path_spaces' is enabled, but '{key}' "
                    "contains spaces. This will always result in a failed "
                    "installation! Aborting!"
                )

    global CACHE_DIR, PACKAGE_ROOT, PACKAGES_DIR, SCRIPTS_DIR

    CACHE_DIR = info['_download_dir']
    SCRIPTS_DIR = join(CACHE_DIR, "scripts")
    PACKAGE_ROOT = join(CACHE_DIR, "package_root")
    PACKAGES_DIR = join(CACHE_DIR, "built_pkgs")

    fresh_dir(PACKAGES_DIR)
    prefix = join(PACKAGE_ROOT, info.get("pkg_name", info['name']).lower())

    # We need to split tasks in sub-PKGs so the GUI allows the user to enable/disable
    # the ones marked as optional. Optionality is controlled in modify_xml() by
    # patching the XML blocks corresponding to each sub-PKG name.
    # See http://stackoverflow.com/a/11487658/161801 for how all this works.

    # 1. Prepare installation
    # The 'prepare_installation' package contains the prepopulated package cache, the modified
    # conda-meta metadata staged into pkgs/conda-meta, conda.exe,
    # Optionally, extra files and the user-provided scripts.
    # We first populate PACKAGE_ROOT with everything needed, and then run pkg build on that dir
    fresh_dir(PACKAGE_ROOT)
    fresh_dir(SCRIPTS_DIR)
    pkgs_dir = join(prefix, 'pkgs')
    os.makedirs(pkgs_dir)
    preconda.write_files(info, pkgs_dir)
    preconda.copy_extra_files(info.get("extra_files", []), prefix)
    # These are the user-provided scripts, maybe patched to have a shebang
    # They will be called by a wrapping script added later, if present
    if info.get('pre_install'):
        move_script(
            abspath(info['pre_install']),
            abspath(join(pkgs_dir, 'user_pre_install')),
            info,
            ensure_shebang=True,
        )
    if info.get('post_install'):
        move_script(
            abspath(info['post_install']),
            abspath(join(pkgs_dir, 'user_post_install')),
            info,
            ensure_shebang=True,
        )

    all_dists = info["_dists"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_dists += env_info["_dists"]
    all_dists = list({dist: None for dist in all_dists})  # de-duplicate
    for dist in all_dists:
        os.link(join(CACHE_DIR, dist), join(pkgs_dir, dist))

    shutil.copyfile(info['_conda_exe'], join(prefix, "conda.exe"))

    # Sign conda-standalone so it can pass notarization
    notarization_identity_name = info.get('notarization_identity_name')
    if notarization_identity_name:
        with NamedTemporaryFile(suffix=".plist", delete=False) as f:
            plist = {
                "com.apple.security.cs.allow-jit": True,
                "com.apple.security.cs.allow-unsigned-executable-memory": True,
                "com.apple.security.cs.disable-executable-page-protection": True,
                "com.apple.security.cs.disable-library-validation": True,
                "com.apple.security.cs.allow-dyld-environment-variables": True,
            }
            plist_dump(plist, f)
        explained_check_call(
            [
                # hardcode to system location to avoid accidental clobber in PATH
                "/usr/bin/codesign",
                "--verbose",
                '--sign', notarization_identity_name,
                "--prefix", info.get("reverse_domain_identifier", info['name']),
                "--options", "runtime",
                "--force",
                "--entitlements", f.name,
                join(prefix, "conda.exe"),
            ]
        )
        os.unlink(f.name)

    # This script checks to see if the install location already exists and/or contains spaces
    # Not to be confused with the user-provided pre_install!
    move_script(join(OSX_DIR, 'checks_before_install.sh'), join(SCRIPTS_DIR, 'preinstall'), info)
    # This script populates the cache, mainly
    move_script(join(OSX_DIR, 'prepare_installation.sh'), join(SCRIPTS_DIR, 'postinstall'), info)
    pkgbuild_prepare_installation(info)
    names = ['prepare_installation']

    # 2. (Optional) Run user-provided pre-install script
    # The preinstall script is run _after_ the tarballs have been extracted!
    if info.get('pre_install'):
        pkgbuild_script(
            'user_pre_install', info, 'run_user_script.sh', user_script_type='pre_install'
        )
        names.append('user_pre_install')

    # 3. Run the installation
    # This script-only package will run conda to link and install the packages
    pkgbuild_script('run_installation', info, 'run_installation.sh')
    names.append('run_installation')

    # 4. The user-supplied post-install script
    if info.get('post_install'):
        pkgbuild_script(
            'user_post_install', info, 'run_user_script.sh', user_script_type='post_install'
        )
        names.append('user_post_install')

    # 5. The script to run conda init
    if info.get('initialize_conda', True):
        pkgbuild_script('pathupdate', info, 'update_path.sh')
        names.append('pathupdate')

    # 6. The script to clear the package cache
    if not info.get('keep_pkgs'):
        pkgbuild_script('cacheclean', info, 'clean_cache.sh')
        names.append('cacheclean')

    # The default distribution file needs to be modified, so we create
    # it to a temporary location, edit it, and supply it to the final call.
    xml_path = join(PACKAGES_DIR, 'distribution.xml')
    # hardcode to system location to avoid accidental clobber in PATH
    args = ["/usr/bin/productbuild", "--synthesize"]
    for name in names:
        args.extend(['--package', join(PACKAGES_DIR, "%s.pkg" % name)])
    args.append(xml_path)
    explained_check_call(args)
    modify_xml(xml_path, info)

    identity_name = info.get('signing_identity_name')
    explained_check_call([
        "/usr/bin/productbuild",
        "--distribution", xml_path,
        "--package-path", PACKAGES_DIR,
        "--identifier", info.get("reverse_domain_identifier", info['name']),
        "tmp.pkg" if identity_name else info['_outpath']
    ])
    if identity_name:
        explained_check_call([
            # hardcode to system location to avoid accidental clobber in PATH
            '/usr/bin/productsign', '--sign', identity_name,
            "tmp.pkg",
            info['_outpath'],
        ])
        os.unlink("tmp.pkg")

    logger.info("done")
