import unittest


from ..install import (
    PaddingError, binary_replace, name_dist, url_pat,
    link_idists, duplicates_to_remove,
)



class TestBinaryReplace(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(
            binary_replace(b'xxxaaaaaxyz\x00zz', b'aaaaa', b'bbbbb'),
            b'xxxbbbbbxyz\x00zz')

    def test_shorter(self):
        self.assertEqual(
            binary_replace(b'xxxaaaaaxyz\x00zz', b'aaaaa', b'bbbb'),
            b'xxxbbbbxyz\x00\x00zz')

    def test_too_long(self):
        self.assertRaises(PaddingError, binary_replace,
                          b'xxxaaaaaxyz\x00zz', b'aaaaa', b'bbbbbbbb')

    def test_no_extra(self):
        self.assertEqual(binary_replace(b'aaaaa\x00', b'aaaaa', b'bbbbb'),
                         b'bbbbb\x00')

    def test_two(self):
        self.assertEqual(
            binary_replace(b'aaaaa\x001234aaaaacc\x00\x00', b'aaaaa',
                           b'bbbbb'),
            b'bbbbb\x001234bbbbbcc\x00\x00')

    def test_spaces(self):
        self.assertEqual(
            binary_replace(b' aaaa \x00', b'aaaa', b'bbbb'),
            b' bbbb \x00')

    def test_multiple(self):
        self.assertEqual(
            binary_replace(b'aaaacaaaa\x00', b'aaaa', b'bbbb'),
            b'bbbbcbbbb\x00')
        self.assertEqual(
            binary_replace(b'aaaacaaaa\x00', b'aaaa', b'bbb'),
            b'bbbcbbb\x00\x00\x00')
        self.assertRaises(PaddingError, binary_replace,
                          b'aaaacaaaa\x00', b'aaaa', b'bbbbb')


class duplicates_to_remove_TestCase(unittest.TestCase):

    def test_0(self):
        linked = ['conda-3.18.8-py27_0', 'python-2.7.11-0', 'zlib-1.2.8-0']
        keep = linked
        self.assertEqual(duplicates_to_remove(linked, keep), [])

    def test_1(self):
        linked = ['conda-3.18.8-py27_0', 'conda-3.19.0',
                  'python-2.7.10-2', 'python-2.7.11-0',
                  'zlib-1.2.8-0']
        keep = ['conda-3.19.0', 'python-2.7.11-0']
        self.assertEqual(duplicates_to_remove(linked, keep),
                         ['conda-3.18.8-py27_0', 'python-2.7.10-2'])

    def test_2(self):
        linked = ['conda-3.19.0',
                  'python-2.7.10-2', 'python-2.7.11-0',
                  'zlib-1.2.7-1', 'zlib-1.2.8-0', 'zlib-1.2.8-4']
        keep = ['conda-3.19.0', 'python-2.7.11-0']
        self.assertEqual(duplicates_to_remove(linked, keep),
                         ['python-2.7.10-2', 'zlib-1.2.7-1', 'zlib-1.2.8-0'])

    def test_3(self):
        linked = ['python-2.7.10-2', 'python-2.7.11-0', 'python-3.4.3-1']
        keep = ['conda-3.19.0', 'python-2.7.11-0']
        self.assertEqual(duplicates_to_remove(linked, keep),
                         ['python-2.7.10-2', 'python-3.4.3-1'])

    def test_nokeep(self):
        linked = ['python-2.7.10-2', 'python-2.7.11-0', 'python-3.4.3-1']
        self.assertEqual(duplicates_to_remove(linked, []),
                         ['python-2.7.10-2', 'python-2.7.11-0'])

    def test_misc(self):
        d1 = 'a-1.3-0'
        self.assertEqual(duplicates_to_remove([], []), [])
        self.assertEqual(duplicates_to_remove([], [d1]), [])
        self.assertEqual(duplicates_to_remove([d1], [d1]), [])
        self.assertEqual(duplicates_to_remove([d1], []), [])
        d2 = 'a-1.4-0'
        self.assertEqual(duplicates_to_remove([d1], [d2]), [])
        li = set([d1, d2])
        self.assertEqual(duplicates_to_remove(li, [d2]), [d1])
        self.assertEqual(duplicates_to_remove(li, [d1]), [d2])
        self.assertEqual(duplicates_to_remove(li, []), [d1])
        self.assertEqual(duplicates_to_remove(li, [d1, d2]), [])


class URLPatter_TestCase(unittest.TestCase):

    def test_1(self):
        line = 'https://repo.io/osx-64/pip-7.1-0.tar.bz2'
        m = url_pat.match(line)
        self.assertEqual(m.group('baseurl'), 'https://repo.io/osx-64/')
        self.assertEqual(m.group('fn'), 'pip-7.1-0.tar.bz2')
        self.assertEqual(m.group('md5'), None)

    def test_md5(self):
        line = ('https://repo.io/osx-64/pip-7.1-0.tar.bz2'
                '#2e61152595f223038c811cd479d0cea1')
        m = url_pat.match(line)
        self.assertEqual(m.group('baseurl'), 'https://repo.io/osx-64/')
        self.assertEqual(m.group('fn'), 'pip-7.1-0.tar.bz2')
        self.assertEqual(m.group('md5'),
                         '2e61152595f223038c811cd479d0cea1')

    def test_invalid(self):
        m = url_pat.match('pip-7.1-0.tar.bz2')
        self.assertEqual(m, None)


class Misc_TestCase(unittest.TestCase):

    def test_name_dist(self):
        self.assertEqual(name_dist('pip-7.1-py27_0'), 'pip')
        self.assertEqual(name_dist('conda-build-1.21.6-py35_0'),
                         'conda-build')


def run():
    suite = unittest.TestSuite()
    for cls in (TestBinaryReplace, duplicates_to_remove_TestCase,
                URLPatter_TestCase, Misc_TestCase):
        suite.addTest(unittest.makeSuite(cls))
    runner = unittest.TextTestRunner()
    return runner.run(suite)


if __name__ == '__main__':
    run()
