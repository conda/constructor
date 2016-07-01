# (c) 2012-2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
'''
These API functions have argument names referring to:

    dist:        canonical package name (e.g. 'numpy-1.6.2-py26_0')

    PKGS_DIR:    the "packages directory" (e.g. '/opt/anaconda/pkgs')

    PREFIX:      the prefix of a particular environment, which may also
                 be the "default" environment (i.e. sys.prefix)

Also, this module is directly invoked by the (self extracting) tarball
installer to create the initial environment, therefore it needs to be
standalone, i.e. not import any other parts of `conda` (only depend on
the standard library).
'''
from __future__ import print_function, division, absolute_import

import os
import sys
import json
import shutil
import stat
from os.path import dirname, isdir, isfile, islink, join


on_win = bool(sys.platform == 'win32')

LINK_HARD = 1
LINK_SOFT = 2
LINK_COPY = 3
link_name_map = {
    LINK_HARD: 'hard-link',
    LINK_SOFT: 'soft-link',
    LINK_COPY: 'copy',
}

# may be changed in main()
PREFIX = sys.prefix
PKGS_DIR = join(PREFIX, 'pkgs')


def _link(src, dst, linktype=LINK_HARD):
    if on_win:
        raise NotImplementedError

    if linktype == LINK_HARD:
        os.link(src, dst)
    elif linktype == LINK_SOFT:
        os.symlink(src, dst)
    elif linktype == LINK_COPY:
        # copy relative symlinks as symlinks
        if islink(src) and not os.readlink(src).startswith('/'):
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
    else:
        raise Exception("Did not expect linktype=%r" % linktype)


def rm_rf(path):
    """
    Completely delete path
    """
    if islink(path) or isfile(path):
        # Note that we have to check if the destination is a link because
        # exists('/path/to/dead-link') will return False, although
        # islink('/path/to/dead-link') is True.
        try:
            os.unlink(path)
            return
        except (OSError, IOError):
            return

    elif isdir(path):
        shutil.rmtree(path)


def rm_empty_dir(path):
    """
    Remove the directory `path` if it is a directory and empty.
    If the directory does not exist or is not empty, do nothing.
    """
    try:
        os.rmdir(path)
    except OSError: # directory might not exist or not be empty
        pass


def yield_lines(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line


prefix_placeholder = ('/opt/anaconda1anaconda2'
                      # this is intentionally split into parts,
                      # such that running this program on itself
                      # will leave it unchanged
                      'anaconda3')

def read_has_prefix(path):
    """
    reads `has_prefix` file and return dict mapping filenames to
    tuples(placeholder, mode)
    """
    import shlex

    res = {}
    try:
        for line in yield_lines(path):
            try:
                placeholder, mode, f = [x.strip('"\'') for x in
                                        shlex.split(line, posix=False)]
                res[f] = (placeholder, mode)
            except ValueError:
                res[line] = (prefix_placeholder, 'text')
    except IOError:
        pass
    return res


class PaddingError(Exception):
    pass


def binary_replace(data, a, b):
    """
    Perform a binary replacement of `data`, where the placeholder `a` is
    replaced with `b` and the remaining string is padded with null characters.
    All input arguments are expected to be bytes objects.
    """
    import re

    def replace(match):
        occurances = match.group().count(a)
        padding = (len(a) - len(b)) * occurances
        if padding < 0:
            raise PaddingError(a, b, padding)
        return match.group().replace(a, b) + b'\0' * padding
    pat = re.compile(re.escape(a) + b'([^\0]*?)\0')
    res = pat.sub(replace, data)
    assert len(res) == len(data)
    return res


def update_prefix(path, new_prefix, placeholder=prefix_placeholder,
                  mode='text'):
    if on_win and (placeholder != prefix_placeholder) and ('/' in placeholder):
        # original prefix uses unix-style path separators
        # replace with unix-style path separators
        new_prefix = new_prefix.replace('\\', '/')

    path = os.path.realpath(path)
    with open(path, 'rb') as fi:
        data = fi.read()
    if mode == 'text':
        new_data = data.replace(placeholder.encode('utf-8'),
                                new_prefix.encode('utf-8'))
    elif mode == 'binary':
        new_data = binary_replace(data, placeholder.encode('utf-8'),
                                  new_prefix.encode('utf-8'))
    else:
        sys.exit("Invalid mode:" % mode)

    if new_data == data:
        return
    st = os.lstat(path)
    # remove file before rewriting to avoid destroying hard-linked cache.
    os.remove(path)
    with open(path, 'wb') as fo:
        fo.write(new_data)
    os.chmod(path, stat.S_IMODE(st.st_mode))


def name_dist(dist):
    return dist.rsplit('-', 2)[0]


def create_meta(dist, info_dir, extra_info):
    """
    Create the conda metadata, in a given prefix, for a given package.
    """
    # read info/index.json first
    with open(join(info_dir, 'index.json')) as fi:
        meta = json.load(fi)
    # add extra info
    meta.update(extra_info)
    # write into <prefix>/conda-meta/<dist>.json
    meta_dir = join(PREFIX, 'conda-meta')
    if not isdir(meta_dir):
        os.makedirs(meta_dir)
    with open(join(meta_dir, dist + '.json'), 'w') as fo:
        json.dump(meta, fo, indent=2, sort_keys=True)


def mk_menus(files, remove=False):
    """
    Create cross-platform menu items (e.g. Windows Start Menu)

    Passes all menu config files %PREFIX%/Menu/*.json to ``menuinst.install``.
    ``remove=True`` will remove the menu items.
    """
    menu_files = [f for f in files
                  if f.lower().startswith('menu/')
                  and f.lower().endswith('.json')]
    if not menu_files:
        return

    try:
        import menuinst
    except:
        return

    for f in menu_files:
        try:
            menuinst.install(join(PREFIX, f), remove, PREFIX)
        except:
            import traceback
            sys.stdout.write("menuinst Exception: %s" % traceback.format_exc())


def run_script(dist, action='post-link'):
    """
    call the post-link (or pre-unlink) script, and return True on success,
    False on failure
    """
    path = join(PREFIX, 'Scripts' if on_win else 'bin', '.%s-%s.%s' % (
            name_dist(dist),
            action,
            'bat' if on_win else 'sh'))
    if not isfile(path):
        return True
    if on_win:
        try:
            args = [os.environ['COMSPEC'], '/c', path]
        except KeyError:
            return False
    else:
        shell_path = '/bin/sh' if 'bsd' in sys.platform else '/bin/bash'
        args = [shell_path, path]
    env = os.environ
    env['ROOT_PREFIX'] = env['PREFIX'] = str(PREFIX)
    env['PKG_NAME'], env['PKG_VERSION'], env['PKG_BUILDNUM'] = \
                str(dist).rsplit('-', 2)

    import subprocess
    try:
        subprocess.check_call(args, env=env)
    except subprocess.CalledProcessError:
        return False
    return True


def read_url(dist):
    try:
        data = open(join(PKGS_DIR, 'urls.txt')).read()
        urls = data.split()
        for url in urls[::-1]:
            if url.endswith('/%s.tar.bz2' % dist):
                return url
    except IOError:
        pass
    return None


def read_no_link(info_dir):
    res = set()
    for fn in 'no_link', 'no_softlink':
        try:
            res.update(set(yield_lines(join(info_dir, fn))))
        except IOError:
            pass
    return res


def try_hard_link(dist):
    src = join(PKGS_DIR, dist, 'info', 'index.json')
    dst = join(PREFIX, '.tmp-%s' % dist)
    assert isfile(src), src
    assert not isfile(dst), dst
    try:
        _link(src, dst, LINK_HARD)
        return True
    except OSError:
        return False
    finally:
        rm_rf(dst)


def extracted():
    """
    return the (set of canonical names) of all extracted packages
    """
    if not isdir(PKGS_DIR):
        return set()
    return set(dn for dn in os.listdir(PKGS_DIR)
               if (isfile(join(PKGS_DIR, dn, 'info', 'files')) and
                   isfile(join(PKGS_DIR, dn, 'info', 'index.json'))))


def linked():
    """
    Return the (set of canonical names) of linked packages in prefix.
    """
    meta_dir = join(PREFIX, 'conda-meta')
    if not isdir(meta_dir):
        return set()
    return set(fn[:-5] for fn in os.listdir(meta_dir) if fn.endswith('.json'))


def link(dist, linktype=LINK_HARD):
    '''
    Set up a package in a specified (environment) prefix.  We assume that
    the package has been extracted (using extract() above).
    '''
    if linktype:
        source_dir = join(PKGS_DIR, dist)
        info_dir = join(source_dir, 'info')
        no_link = read_no_link(info_dir)
    else:
        info_dir = join(PREFIX, 'info')

    files = list(yield_lines(join(info_dir, 'files')))
    has_prefix_files = read_has_prefix(join(info_dir, 'has_prefix'))

    if linktype:
        for f in files:
            src = join(source_dir, f)
            dst = join(PREFIX, f)
            dst_dir = dirname(dst)
            if not isdir(dst_dir):
                os.makedirs(dst_dir)
            if os.path.exists(dst):
                rm_rf(dst)
            lt = linktype
            if f in has_prefix_files or f in no_link or islink(src):
                lt = LINK_COPY
            try:
                _link(src, dst, lt)
            except OSError:
                pass

    for f in sorted(has_prefix_files):
        placeholder, mode = has_prefix_files[f]
        try:
            update_prefix(join(PREFIX, f), PREFIX, placeholder, mode)
        except PaddingError:
            sys.exit("ERROR: placeholder '%s' too short in: %s\n" %
                     (placeholder, dist))

    mk_menus(files, remove=False)

    if not run_script(dist, 'post-link'):
        sys.exit("Error: post-link failed for: %s" % dist)

    meta_dict = {
        'files': files,
        'url': read_url(dist),
        'link': ({'source': source_dir,
                  'type': link_name_map.get(linktype)}
                 if linktype else None),
    }
    create_meta(dist, info_dir, meta_dict)


def unlink(dist):
    '''
    Remove a package from the specified environment, it is an error if the
    package does not exist in the prefix.
    '''
    run_script(dist, 'pre-unlink')

    meta_path = join(PREFIX, 'conda-meta', dist + '.json')
    with open(meta_path) as fi:
        meta = json.load(fi)

    mk_menus(PREFIX, meta['files'], remove=True)
    dst_dirs1 = set()

    for f in meta['files']:
        dst = join(PREFIX, f)
        dst_dirs1.add(dirname(dst))
        rm_rf(dst)

    # remove the meta-file last
    os.unlink(meta_path)

    dst_dirs2 = set()
    for path in dst_dirs1:
        while len(path) > len(PREFIX):
            dst_dirs2.add(path)
            path = dirname(path)
    # in case there is nothing left
    dst_dirs2.add(join(PREFIX, 'conda-meta'))
    dst_dirs2.add(PREFIX)

    for path in sorted(dst_dirs2, key=len, reverse=True):
        rm_empty_dir(path)


def messages():
    path = join(PREFIX, '.messages.txt')
    try:
        with open(path) as fi:
            sys.stdout.write(fi.read())
    except IOError:
        pass
    finally:
        rm_rf(path)


def duplicates_to_remove(linked_dists, keep_dists):
    """
    Returns the (sorted) list of distributions to be removed, such that
    only one distribution (for each name) remains.  `keep_dists` is an
    interable of distributions (which are not allowed to be removed).
    """
    from collections import defaultdict

    keep_dists = set(keep_dists)
    ldists = defaultdict(set) # map names to set of distributions
    for dist in linked_dists:
        name = name_dist(dist)
        ldists[name].add(dist)

    res = set()
    for dists in ldists.values():
        # `dists` is the group of packages with the same name
        if len(dists) == 1:
            # if there is only one package, nothing has to be removed
            continue
        if dists & keep_dists:
            # if the group has packages which are have to be kept, we just
            # take the set of packages which are in group but not in the
            # ones which have to be kept
            res.update(dists - keep_dists)
        else:
            # otherwise, we take lowest (n-1) (sorted) packages
            res.update(sorted(dists)[:-1])
    return sorted(res)


def post_extract(dist):
    """
    assuming that the package is extracted in prefix itself, this function
    does everything link() does except the actual linking, i.e.
    update prefix files, run 'post-link', creates the conda metadata
    """
    link(dist, linktype=0)


def main():
    global PREFIX, PKGS_DIR

    from optparse import OptionParser

    p = OptionParser(description="conda link tool used by installer")

    p.add_option('--file',
                 action="store",
                 help="path of a file containing distributions to link, "
                      "by default all packages extracted in the cache are "
                      "linked")

    p.add_option('--prefix',
                 action="store",
                 default=sys.prefix,
                 help="prefix (defaults to %default)")

    p.add_option('--post',
                 action="store",
                 help="perform post extract for DIST",
                 metavar='DIST')

    p.add_option('-v', '--verbose',
                 action="store_true")

    opts, args = p.parse_args()
    if args:
        p.error('no arguments expected')
    if opts.file and opts.post:
        p.error("--file and --post exclude each other")

    PREFIX = opts.prefix
    PKGS_DIR = join(PREFIX, 'pkgs')
    if opts.verbose:
        print("PREFIX: %r" % PREFIX)

    if opts.post:
        post_extract(opts.post)
        return

    if opts.file:
        idists = list(yield_lines(join(PREFIX, opts.file)))
    else:
        idists = sorted(extracted())

    linktype = (LINK_HARD if try_hard_link() else LINK_COPY)
    if opts.verbose:
        print("linktype: %s" % link_name_map[linktype])

    for dist in idists:
        if opts.verbose:
            print("linking: %s" % dist)
        link(dist, linktype)

    messages()

    for dist in duplicates_to_remove(linked(), idists):
        meta_path = join(PREFIX, 'conda-meta', dist + '.json')
        print("WARNING: unlinking: %s" % meta_path)
        try:
            os.rename(meta_path, meta_path + '.bak')
        except OSError:
            rm_rf(meta_path)


if __name__ == '__main__':
    main()
