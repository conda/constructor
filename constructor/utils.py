# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import re
import sys


def name_dist(dist):
    return dist.rsplit('-', 2)[0]


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


def test_preprocess():
    a = preprocess("""\
A
#if True
  always True
  another line
#endif
B
#if False
  never see this
#endif
C
#if x == 0
  x = 0
#else
  x != 0
#endif
D
#if x != 0
  x != 0
#endif
E
""", dict(x=1))
    b = """\
A
  always True
  another line
B
C
  x != 0
D
  x != 0
E
"""
    assert a == b


if __name__ == '__main__':
    test_preprocess()
