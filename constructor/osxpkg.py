import os
import shutil
from os.path import isdir, abspath, dirname, exists, join
from subprocess import check_call
import xml.etree.ElementTree as ET

import constructor.preconda as preconda
from constructor.utils import add_condarc, get_final_channels, rm_rf


OSX_DIR = join(dirname(__file__), "osx")
CACHE_DIR = PACKAGE_ROOT = PACKAGES_DIR = SCRIPTS_DIR = None


def write_readme(dst, info):

    src = join(OSX_DIR, 'readme_header.rtf')
    with open(src) as fi:
        data = fi.read()

    # This is necessary for when installing on case-sensitive macOS filesystems.
    data = data.replace('__NAME_LOWER__', info['name'].lower())
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

    background = ET.Element('background',
                            file=join(OSX_DIR, 'MacInstaller.png'),
                            scaling='proportional', alignment='center')
    root.append(background)

    conclusion = ET.Element('conclusion', file=join(OSX_DIR, 'acloud.rtf'),
                            attrib={'mime-type': 'richtext/rtf'})
    root.append(conclusion)

    readme_path = join(PACKAGES_DIR, "readme.rtf")
    write_readme(readme_path, info)
    readme = ET.Element('readme', file=readme_path,
                        attrib={'mime-type': 'richtext/rtf'})
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
            path_choice.set('visible', 'true')
            path_choice.set('start_selected', 'true' if info.get(
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
            path_description = """
            If this box is checked, the package cache will be cleaned after the
            installer is complete, reclaiming some disk space. If unchecked, the
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
    with open(src) as fi:
        data = fi.read()

    # This is necessary for when installing on case-sensitive macOS filesystems.
    data = data.replace('__NAME_LOWER__', info['name'].lower())
    data = data.replace('__NAME__', info['name'])
    data = data.replace('__CHANNELS__', ','.join(get_final_channels(info)))
    data = data.replace('__WRITE_CONDARC__', '\n'.join(add_condarc(info)))

    with open(dst, 'w') as fo:
        fo.write(data)
    os.chmod(dst, 0o755)


def fresh_dir(dir_path):
    rm_rf(dir_path)
    assert not exists(dir_path)
    os.mkdir(dir_path)


def pkgbuild(name):
    args = ["pkgbuild", "--root", PACKAGE_ROOT]
    if isdir(SCRIPTS_DIR) and os.listdir(SCRIPTS_DIR):
        args.extend(["--scripts", SCRIPTS_DIR])
    args.extend([
        "--identifier", "io.continuum.pkg.%s" % name,
        "--ownership", "preserve",
        "%s/%s.pkg" % (PACKAGES_DIR, name),
    ])
    check_call(args)


def pkgbuild_script(name, info, src, dst='postinstall'):
    fresh_dir(SCRIPTS_DIR)
    fresh_dir(PACKAGE_ROOT)
    move_script(join(OSX_DIR, src), join(SCRIPTS_DIR, dst), info)
    pkgbuild(name)
    rm_rf(SCRIPTS_DIR)


def create(info, verbose=False):
    global CACHE_DIR, PACKAGE_ROOT, PACKAGES_DIR, SCRIPTS_DIR

    CACHE_DIR = info['_download_dir']
    SCRIPTS_DIR = join(CACHE_DIR, "scripts")
    PACKAGE_ROOT = join(CACHE_DIR, "package_root")
    PACKAGES_DIR = join(CACHE_DIR, "built_pkgs")

    fresh_dir(PACKAGES_DIR)
    prefix = join(PACKAGE_ROOT, info['name'].lower())

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
    # This script checks to see if the install location already exists
    move_script(join(OSX_DIR, 'preinstall.sh'), join(SCRIPTS_DIR, 'preinstall'), info)
    # This script performs the full installation
    move_script(join(OSX_DIR, 'post_extract.sh'), join(SCRIPTS_DIR, 'postinstall'), info)
    pkgbuild('main')
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
        "--identifier", info['name'],
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
