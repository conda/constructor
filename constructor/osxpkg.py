import os
import shutil
from os.path import isdir, abspath, dirname, exists, join
from subprocess import check_call
import xml.etree.ElementTree as ET
from pathlib import Path
from plistlib import dump as plist_dump
from tempfile import NamedTemporaryFile

import constructor.preconda as preconda
from constructor.imaging import write_images
from constructor.utils import add_condarc, get_final_channels, rm_rf, approx_size_kb


OSX_DIR = join(dirname(__file__), "osx")
CACHE_DIR = PACKAGE_ROOT = PACKAGES_DIR = SCRIPTS_DIR = None


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
        for dist in sorted(info['_dists']):
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
    title.text = info['name']
    root.append(title)

    license = ET.Element('license', file=info.get('license_file',
                                                  'No license'))
    root.append(license)

    ### BACKGROUND ###
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
        print("Using background image", background_path)
        for key in ("background", "background-darkAqua"):
            background = ET.Element(key,
                                    file=background_path,
                                    scaling='proportional',
                                    alignment='center')
            root.append(background)

    ### WELCOME ###
    if "welcome_file" in info:
        welcome_path = info["welcome_file"]
    elif "welcome_text" in info and info["welcome_text"]:
        welcome_path = join(PACKAGES_DIR, "welcome.txt")
        with open(welcome_path, "w") as f:
            f.write(info["welcome_text"])
    else:
        welcome_path = None

    if welcome_path:
        welcome = ET.Element(
            'welcome', file=welcome_path,
            attrib={'mime-type': _detect_mimetype(welcome_path)}
        )
        root.append(welcome)

    ### CONCLUSION ###
    if "conclusion_file" in info:
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

    if conclusion_path:
        conclusion = ET.Element(
            'conclusion', file=conclusion_path,
            attrib={'mime-type': _detect_mimetype(conclusion_path)}
        )
        root.append(conclusion)
    # when not provided, conclusion defaults to a system message

    ### README ###
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
        elif ident.endswith('main'):
            path_choice.set('visible', 'true')
            path_choice.set('title', 'Install {}'.format(info['name']))
            path_choice.set('enabled', 'false')
        elif ident.endswith('postinstall') and info.get('post_install_desc'):
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
            If this box is checked, "conda init" will be executed to ensure that
            conda is available in your preferred shell upon startup. If unchecked,
            you must this initialization yourself or activate the environment
            manually for each shell in which you wish to use it."""
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


def move_script(src, dst, info):
    """
    Fill template scripts preinstall.sh, post_extract.sh and others,
    and move them to the installer workspace.
    """
    with open(src) as fi:
        data = fi.read()

    # This is necessary for when installing on case-sensitive macOS filesystems.
    pkg_name_lower = info.get("pkg_name", info['name']).lower()
    data = data.replace('__NAME_LOWER__', pkg_name_lower)
    data = data.replace('__VERSION__', info['version'])
    data = data.replace('__NAME__', info['name'])
    data = data.replace('__CHANNELS__', ','.join(get_final_channels(info)))
    data = data.replace('__WRITE_CONDARC__', '\n'.join(add_condarc(info)))

    default_path_exists_error_text = (
        "'{CHOSEN_PATH}' already exists. Please, relaunch the installer and "
        "choose another location in the Destination Select step."
    )
    path_exists_error_text = info.get(
        "install_path_exists_error_text", default_path_exists_error_text
    ).format(CHOSEN_PATH=f"$2/{pkg_name_lower}")
    data = data.replace('__PATH_EXISTS_ERROR_TEXT__', path_exists_error_text)

    with open(dst, 'w') as fo:
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
    check_call(args)
    return output


def pkgbuild_main(info):
    pkg = pkgbuild(
        "main",
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
        check_call(["pkgutil", "--expand", pkg, f"{pkg}.expanded"])
        payload_xml = os.path.join(f"{pkg}.expanded", "PackageInfo")
        tree = ET.parse(payload_xml)
        root = tree.getroot()
        payload = root.find("payload")
        payload.set("installKBytes", str(approx_pkgs_size_kb))
        tree.write(payload_xml)
        # repack
        check_call(["pkgutil", "--flatten", f"{pkg}.expanded", pkg])
        return pkg
    finally:
        shutil.rmtree(f"{pkg}.expanded")


def pkgbuild_script(name, info, src, dst='postinstall'):
    fresh_dir(SCRIPTS_DIR)
    fresh_dir(PACKAGE_ROOT)
    move_script(join(OSX_DIR, src), join(SCRIPTS_DIR, dst), info)
    pkgbuild(
        name,
        identifier=info.get("reverse_domain_identifier"),
        install_location=info.get("default_location_pkg"),
    )
    rm_rf(SCRIPTS_DIR)


def create(info, verbose=False):
    global CACHE_DIR, PACKAGE_ROOT, PACKAGES_DIR, SCRIPTS_DIR

    CACHE_DIR = info['_download_dir']
    SCRIPTS_DIR = join(CACHE_DIR, "scripts")
    PACKAGE_ROOT = join(CACHE_DIR, "package_root")
    PACKAGES_DIR = join(CACHE_DIR, "built_pkgs")

    fresh_dir(PACKAGES_DIR)
    prefix = join(PACKAGE_ROOT, info.get("pkg_name", info['name']).lower())

    # See http://stackoverflow.com/a/11487658/161801 for how all this works.

    # The main package contains the prepopulated package cache, the modified
    # conda-meta metadata staged into pkgs/conda-meta, and conda.exe
    fresh_dir(PACKAGE_ROOT)
    fresh_dir(SCRIPTS_DIR)
    pkgs_dir = join(prefix, 'pkgs')
    os.makedirs(pkgs_dir)
    preconda.write_files(info, pkgs_dir)
    for dist in info['_dists']:
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
        check_call(
            [
                'codesign',
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

    # This script checks to see if the install location already exists
    move_script(join(OSX_DIR, 'preinstall.sh'), join(SCRIPTS_DIR, 'preinstall'), info)
    # This script performs the full installation
    move_script(join(OSX_DIR, 'post_extract.sh'), join(SCRIPTS_DIR, 'postinstall'), info)
    pkgbuild_main(info)
    names = ['main']

    # The next three packages contain nothing but scripts to execute a
    # particular optional task. The Mac installer GUI will allow each of
    # these scripts to be enabled or disabled by the user in the GUI
    # The user-supplied post-install script
    if info.get('post_install'):
        pkgbuild_script('postinstall', info, abspath(info['post_install']))
        names.append('postinstall')
    # The script to run conda init
    pkgbuild_script('pathupdate', info, 'update_path.sh')
    names.append('pathupdate')
    # The script to clear the package cache
    pkgbuild_script('cacheclean', info, 'clean_cache.sh')
    names.append('cacheclean')

    # The default distribution file needs to be modified, so we create
    # it to a temporary location, edit it, and supply it to the final call.
    xml_path = join(PACKAGES_DIR, 'distribution.xml')
    args = ["productbuild", "--synthesize"]
    for name in names:
        args.extend(['--package', join(PACKAGES_DIR, "%s.pkg" % name)])
    args.append(xml_path)
    check_call(args)
    modify_xml(xml_path, info)

    identity_name = info.get('signing_identity_name')
    check_call([
        "productbuild",
        "--distribution", xml_path,
        "--package-path", PACKAGES_DIR,
        "--identifier", info.get("reverse_domain_identifier", info['name']),
        "tmp.pkg" if identity_name else info['_outpath']
    ])
    if identity_name:
        check_call([
            'productsign', '--sign', identity_name,
            "tmp.pkg",
            info['_outpath'],
        ])
        os.unlink("tmp.pkg")

    print("done")
