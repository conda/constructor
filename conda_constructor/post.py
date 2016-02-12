import sys
from os.path import join

from install import (yield_lines, read_has_prefix, PaddingError,
                     update_prefix, create_meta, mk_menus, run_script)

prefix = sys.prefix
info_dir = join(prefix, 'info')


def post_extract(dist):
    files = list(yield_lines(join(info_dir, 'files')))
    has_prefix_files = read_has_prefix(join(info_dir, 'has_prefix'))

    for f in sorted(has_prefix_files):
        placeholder, mode = has_prefix_files[f]
        try:
            update_prefix(join(prefix, f), prefix, placeholder, mode)
        except PaddingError:
            sys.exit("ERROR: placeholder '%s' too short in: %s\n" %
                     (placeholder, dist))

    mk_menus(prefix, files, remove=False)
    run_script(prefix, dist, 'post-link')
    create_meta(prefix, dist, info_dir, {'files': files})


def main():
    if len(sys.argv) == 2:
        post_extract(sys.argv[1])
    else:
        print("Usage: %s DIST" % sys.argv[0])


if __name__ == '__main__':
    main()
