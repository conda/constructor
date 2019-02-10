import os
import shutil
import tarfile
from os.path import dirname, exists, join
from subprocess import check_call
from sys import argv, version_info
import xml.etree.ElementTree as ET

from constructor.install import rm_rf, name_dist
import constructor.preconda as preconda
from constructor.utils import add_condarc



OSX_DIR = join(dirname(__file__), "osx")
CACHE_DIR = PACKAGE_ROOT = PACKAGES_DIR = None



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
    # http://developer.apple.com/library/mac/#documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html#//apple_ref/doc/uid/TP40005370-CH100-SW20 for all the options you can put here.

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

    [options] = [i for i in root.findall('options')]
    options.set('customize', 'allow')
    options.set('customLocation', '/')

    [default_choice] = [i for i in root.findall('choice')
                        if i.get('id') == 'default']
    default_choice.set('title', info['name'])

    [path_choice] = [i for i in root.findall('choice')
                     if 'pathupdate' in i.get('id')]
    path_choice.set('visible', 'true')
    path_choice.set('title', "Modify PATH")
    path_description = """
    Whether to modify the bash profile file to append %s to the PATH
    variable.  If you do not do this, you will need to add ~/%s/bin
    to your PATH manually to run the commands, or run all %s commands
    explicitly from that path.
    """ % (info['name'], info['name'].lower(), info['name'])
    path_choice.set('description', ' '.join(path_description.split()))

    # TODO :: Check that varying these based on 'attempt_hardlinks' is the
    #         right thing to do.
    if bool(info.get('attempt_hardlinks')):
        enable_anywhere = 'true'
        enable_localSystem = 'false'
    else:
        enable_anywhere = 'false'
        enable_localSystem = 'true'
    domains = ET.Element('domains',
                         enable_anywhere=enable_anywhere,
                         enable_currentUserHome='true',
                         enable_localSystem=enable_localSystem)
    root.append(domains)

    tree.write(xml_path)


def move_script(src, dst, info):
    with open(src) as fi:
        data = fi.read()

    # This is necessary for when installing on case-sensitive macOS filesystems.
    data = data.replace('__NAME_LOWER__', info['name'].lower())
    data = data.replace('__NAME__', info['name'])
    data = data.replace('__VERSION__', info['version'])
    data = data.replace('__WRITE_CONDARC__', '\n'.join(add_condarc(info)))

    if isinstance(info['_dists'][0], str if version_info[0] >= 3 else basestring):
        dirname = info['_dists'][0][:-8]
    else:
        dirname = info['_dists'][0].dist_name
    data = data.replace('__PYTHON_DIST__', dirname)

    with open(dst, 'w') as fo:
        fo.write(data)
    os.chmod(dst, 0o755)


def fresh_dir(dir_path):
    rm_rf(dir_path)
    assert not exists(dir_path)
    os.mkdir(dir_path)


def pkgbuild(name, scripts=None):
    # Some packages like qt might have .app folders like qdbusviewer.app. The
    # installer by default makes this .app relocatable, so that if it is
    # already installed, it will upgrade it with the new one instead of just
    # installing the new one in the chosen installation directory. An example
    # log entry for this:

    # PackageKit:
    # /path_new/bin/qdbusviewer.app relocated to /path_old/bin/qdbusviewer.app

    # This can cause trouble, expesically if any of the files inside that
    # folder require prefix patching and the installer will fail, since it
    # won't find the file. A general practice was to rename <name>.app to
    # <name>app so that the installer would ignore analyzing it, but that was a
    # hack as it also required a post-link script to rename them back on
    # installation. To avoid such nastiness, we mark all components in the
    # plist file of the parent pkg file, (in this case, qt.pkg) as non-relocatable.

    # xref(s):
    #  - https://apple.stackexchange.com/a/219144/243863
    #  - https://stackoverflow.com/a/26202210/1005215
    #  - https://developer.apple.com/legacy/library/documentation/Darwin/Reference/ManPages/man1/pkgbuild.1.html
    #  - https://github.com/conda-forge/python.app-feedstock/blob/master/recipe/post-link.sh

    components_plist = '{}/{}.plist'.format(PACKAGES_DIR, name)

    check_call([
        'pkgbuild',
        '--root', PACKAGE_ROOT,
        '--analyze', components_plist])

    check_call([
        'plutil',
        '-replace', 'BundleIsRelocatable',
        '-bool', 'false',
        components_plist])

    args = [
        "pkgbuild",
        "--root", PACKAGE_ROOT,
    ]
    if scripts:
        args.extend([
            "--scripts", scripts,
        ])
    args.extend([
        "--component-plist", components_plist,
        "--identifier", "io.continuum.pkg.%s" % name,
        "--ownership", "preserve",
        "%s/%s.pkg" % (PACKAGES_DIR, name),
    ])
    check_call(args)

    os.remove(components_plist)


def pkgbuild_script(name, info, src, dst='postinstall'):
    scripts_dir = join(CACHE_DIR, "scripts")
    fresh_dir(scripts_dir)
    move_script(join(OSX_DIR, src),
                join(scripts_dir, dst),
                info)
    fresh_dir(PACKAGE_ROOT)  # --root <empty dir>
    pkgbuild(name, scripts_dir)


def create(info, verbose=False):
    global CACHE_DIR, PACKAGE_ROOT, PACKAGES_DIR

    CACHE_DIR = info['_download_dir']
    PACKAGE_ROOT = join(CACHE_DIR, "package_root")
    PACKAGES_DIR = join(CACHE_DIR, "built_pkgs")

    # See http://stackoverflow.com/a/11487658/161801 for how all this works.
    prefix = join(PACKAGE_ROOT, info['name'].lower())

    fresh_dir(PACKAGES_DIR)
    fresh_dir(PACKAGE_ROOT)
    pkgs_dir = join(prefix, 'pkgs')
    os.makedirs(pkgs_dir)
    preconda.write_files(info, pkgs_dir)

    # TODO: Refactor code such that the argument to preconda.write_files is
    # /path/to/base/env, so that such workarounds are not required.
    shutil.move(join(pkgs_dir, 'conda-meta'), prefix)

    pkgbuild('preconda')

    for dist in info['_dists']:
        if isinstance(dist, str if version_info[0] >= 3 else basestring):
           fn = dist
           dname = dist[:-8]
           ndist = name_dist(fn)
        else:
            fn = dist.fn
            dname = dist.dist_name
            ndist = dist.name
        fresh_dir(PACKAGE_ROOT)
        if bool(info.get('attempt_hardlinks')):
            t = tarfile.open(join(CACHE_DIR, fn), 'r:bz2')
            os.makedirs(join(pkgs_dir, dname))
            t.extractall(join(pkgs_dir, dname))
            t.close()
        else:
            t = tarfile.open(join(CACHE_DIR, fn), 'r:bz2')
            t.extractall(prefix)
            t.close()
            os.rename(join(prefix, 'info'), join(prefix, 'info-tmp'))
            os.mkdir(join(prefix, 'info'))
            os.rename(join(prefix, 'info-tmp'), join(prefix, 'info', fn[:-8]))
        pkgbuild(ndist)

    # Create special preinstall and postinstall packages to check if Anaconda
    # is already installed, build Anaconda, and to update the shell profile.

    # First script
    pkgbuild_script('postextract', info, 'post_extract.sh')

    # Next, the script to edit bashrc with the PATH.  This is separate so it
    # can be disabled.
    pkgbuild_script('pathupdate', info, 'update_path.sh')

    post_packages = ['postextract', 'pathupdate']

    # Next, the users post_install script, if specified
    if info.get('post_install', None) is not None:
        scripts_dir = join(CACHE_DIR, "scripts")
        fresh_dir(scripts_dir)
        move_script(info['post_install'], join(scripts_dir, 'postinstall'), info)
        fresh_dir(PACKAGE_ROOT)
        pkgbuild('user_postinstall', scripts_dir)
        post_packages.append('user_postinstall')

    # Next, the script to be run before everything, which checks if Anaconda
    # is already installed.
    pkgbuild_script('apreinstall', info, 'preinstall.sh', 'preinstall')

    # Now build the final package
    names = ['apreinstall', 'preconda']
    names.extend(name_dist(dist) for dist in info['_dists'])
    names.extend(post_packages)

    xml_path = join(PACKAGES_DIR, 'distribution.xml')
    args = ["productbuild", "--synthesize"]
    for name in names:
        args.extend(['--package', join(PACKAGES_DIR, "%s.pkg" % name)])
    args.append(xml_path)
    check_call(args)

    modify_xml(xml_path, info)

    check_call([
        "productbuild",
        "--distribution", xml_path,
        "--package-path", PACKAGES_DIR,
        "--identifier", info['name'],
        "tmp.pkg",
    ])

    identity_name = info.get('signing_identity_name')
    if identity_name:
        check_call([
            'productsign', '--sign',
            identity_name,
            "tmp.pkg",
            info['_outpath'],
        ])
        os.unlink("tmp.pkg")
    else:
        os.rename('tmp.pkg', info['_outpath'])

    print("done")
