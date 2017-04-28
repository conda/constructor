# adapted from conda-build

import textwrap
SEPARATOR = "-" * 70

indent = lambda s: textwrap.fill(textwrap.dedent(s))


class YamlParsingError(Exception):
    pass


class UnableToParse(YamlParsingError):
    def __init__(self, original, *args, **kwargs):
        super(UnableToParse, self).__init__(*args, **kwargs)
        self.original = original

    def error_msg(self):
        return "\n".join([
            SEPARATOR,
            self.error_body(),
            self.indented_exception(),
        ])

    def error_body(self):
        return "\n".join([
            "Unable to parse meta.yaml file\n",
        ])

    def indented_exception(self):
        orig = str(self.original)
        indent = lambda s: s.replace("\n", "\n--> ")
        return "Error Message:\n--> {}\n\n".format(indent(orig))


class UnableToParseMissingJinja2(UnableToParse):
    def error_body(self):
        return "\n".join([
            super(UnableToParseMissingJinja2, self).error_body(),
            indent("""\
                It appears you are missing jinja2.  Please install that
                package, then attempt to build.
            """),
        ])
