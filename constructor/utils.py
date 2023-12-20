# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import hashlib
import logging
import math
import re
import sys
from os import sep, unlink
from os.path import basename, isdir, isfile, islink, join, normpath
from shutil import rmtree
from subprocess import check_call, check_output

from ruamel import yaml

logger = logging.getLogger(__name__)


def explained_check_call(args):
    """
    Execute a system process and debug the invocation
    """
    logger.debug("Executing: %s", " ".join(args))
    return check_call(args)


def filename_dist(dist):
    """ Return the filename of a distribution. """
    if hasattr(dist, 'to_filename'):
        return dist.to_filename()
    else:
        return dist


def fill_template(data, d, exceptions=[]):
    pat = re.compile(r'__(\w+)__')

    def replace(match):
        key = match.group(1)
        return key if key in exceptions else d[key]

    return pat.sub(replace, data)


def hash_files(paths, algorithm='md5'):
    h = hashlib.new(algorithm)
    for path in paths:
        with open(path, 'rb') as fi:
            while True:
                chunk = fi.read(262144)
                if not chunk:
                    break
                h.update(chunk)
    return h.hexdigest()


def make_VIProductVersion(version):
    """
    always create a version of the form X.X.X.X
    """
    pat = re.compile(r'\d+$')
    res = []
    for part in version.split('.'):
        if pat.match(part):
            res.append(part)
    while len(res) < 4:
        res.append('0')
    return '.'.join(res[:4])


def read_ascii_only(path):
    with open(path) as fi:
        data = fi.read()
    for c in data:
        if ord(c) > 127:
            sys.exit("Error: unexpected non-ASCII character '%s' in: %s" %
                     (c, path))
    return data


if_pat = re.compile(r'^#if ([ \S]+)$\n'
                    r'(.*?)'
                    r'(^#else\s*$\n(.*?))?'
                    r'^#endif\s*$\n', re.M | re.S)


def preprocess(data, namespace):

    def if_repl(match):
        cond = match.group(1).strip()
        if eval(cond, namespace, {}):
            return match.group(2)
        else:
            return match.group(4) or ''

    return if_pat.sub(if_repl, data)


def add_condarc(info):
    condarc = info.get('condarc')
    if condarc is None:
        # The legacy approach
        write_condarc = info.get('write_condarc')
        default_channels = info.get('conda_default_channels')
        channel_alias = info.get('conda_channel_alias')
        channels = info.get('channels')
        if not (write_condarc and (default_channels or channels or channel_alias)):
            return
        condarc = {}
        if default_channels:
            condarc['default_channels'] = default_channels
        if channels:
            condarc['channels'] = channels
        if channel_alias:
            condarc['channel_alias'] = channel_alias
    if isinstance(condarc, dict):
        condarc = yaml.dump(condarc, default_flow_style=False)
    yield '# ----- add condarc'
    if info['_platform'].startswith('win'):
        yield 'Var /Global CONDARC'
        yield 'FileOpen $CONDARC "$INSTDIR\\.condarc" w'
        for line in condarc.splitlines():
            yield 'FileWrite $CONDARC "%s$\\r$\\n"' % line
        yield 'FileClose $CONDARC'
    else:
        yield 'cat <<EOF >"$PREFIX/.condarc"'
        for line in condarc.splitlines():
            yield line
        yield 'EOF'


def ensure_transmuted_ext(info, url):
    """
    If transmuting, micromamba won't find the dist in the preconda tarball
    unless it has the (correct and transmuted) extension. Otherwise, the command
    `micromamba constructor --extract-tarballs` fails.
    Unfortunately this means the `urls` file might end up containing
    fake URLs, since those .conda archives might not really exist online,
    and they were only created locally.
    """
    if (
        info.get("transmute_file_type") == ".conda"
        and "micromamba" in basename(info.get("_conda_exe", ""))
    ):
        if url.lower().endswith(".tar.bz2"):
            url = url[:-8] + ".conda"
    return url


def get_final_url(info, url):
    mapping = info.get('channels_remap', [])
    for entry in mapping:
        src = entry['src']
        dst = entry['dest']
        if url.startswith(src):
            new_url = url.replace(src, dst)
            if url.endswith(".tar.bz2"):
                logger.warning("You need to make the package %s available "
                               "at %s", url.rsplit('/', 1)[1], new_url)
            return new_url
    return url


def get_final_channels(info):
    mapped_channels = []
    for channel in info.get('channels', []):
        url = get_final_url(info, channel)
        if url.startswith("file://"):
            logger.warning("local channel %s does not have a remap. "
                           "It will not be included in the installer", url)
            continue
        mapped_channels.append(url)
    return mapped_channels


def normalize_path(path):
    new_path = normpath(path)
    return new_path.replace(sep + sep, sep)


def rm_rf(path):
    """
    try to delete path, but never fail
    """
    try:
        if islink(path) or isfile(path):
            # Note that we have to check if the destination is a link because
            # exists('/path/to/dead-link') will return False, although
            # islink('/path/to/dead-link') is True.
            unlink(path)
        elif isdir(path):
            rmtree(path)
    except OSError:
        pass


def yield_lines(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line


def shortcuts_flags(info, conda_exe=None):
    menu_packages = info.get("menu_packages")
    conda_exe = conda_exe or info.get("_conda_exe", "")
    is_micromamba = "micromamba" in basename(conda_exe).lower()
    if menu_packages is None:
        # not set: we create all shortcuts (default behaviour)
        return ""
    if menu_packages:
        if is_micromamba:
            logger.warning(
                "Micromamba does not support '--shortcuts-only'. "
                "Will install all shortcuts."
            )
            return ""
        # set and populated: we only create shortcuts for some
        # NOTE: This syntax requires conda 23.11 or above
        return " ".join([f"--shortcuts-only={pkg.strip()}" for pkg in menu_packages])
    # set but empty: disable all shortcuts
    return "--no-shortcuts"


def approx_size_kb(info, which="pkgs"):
    valid = ("pkgs", "tarballs", "total")
    assert which in valid, f"'which' must be one of {valid}"
    size_pkgs = info.get('_approx_pkgs_size', 0)
    size_tarballs = info.get('_approx_tarballs_size', 0)
    if which == "pkgs":
        size_bytes = size_pkgs
    elif which == "tarballs":
        size_bytes = size_tarballs
    else:
        size_bytes = size_pkgs + size_tarballs

    # division by 10^3 instead of 2^10 is deliberate here. gives us more room
    return int(math.ceil(size_bytes/1000))


def identify_conda_exe(conda_exe=None):
    if conda_exe is None:
        conda_exe = normalize_path(join(sys.prefix, "standalone_conda", "conda.exe"))
    output = check_output([conda_exe, "--version"], text=True)
    output = output.strip()
    fields = output.split()
    if "conda" in fields:
        name = "conda-standalone"
        version = fields[1]
    else:
        name = "micromamba"
        version = output.strip()
    return name, version
