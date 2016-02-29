from constructor.utils import fill_template, preprocess


def test_fill_template():
    template = """\
My name is __NAME__!
I am __AGE__ years old.
Sincerely __NAME__
"""
    res = """\
My name is Hugo!
I am 44 years old.
Sincerely Hugo
"""
    info = {'NAME': 'Hugo', 'AGE': '44', 'SEX': 'male'}
    assert fill_template(template, info) == res


def test_preprocess():
    code = """\
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
"""
    res = """\
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
    assert preprocess(code, dict(x=1)) == res


def main():
    test_fill_template()
    test_preprocess()


if __name__ == '__main__':
    main()
