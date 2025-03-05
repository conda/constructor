# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import json
import logging
import re
import sys
from functools import partial
from os.path import dirname
from pathlib import Path

from jsonschema import Draft202012Validator, validators
from jsonschema.exceptions import ValidationError
from ruamel.yaml import YAMLError

from constructor.exceptions import UnableToParse, UnableToParseMissingJinja2, YamlParsingError
from constructor.utils import yaml

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "data" / "constructor.schema.json"


def ns_platform(platform):
    p = platform
    return dict(
        linux=p.startswith("linux-"),
        linux32=bool(p == "linux-32"),
        linux64=bool(p == "linux-64"),
        armv7l=bool(p == "linux-armv7l"),
        aarch64=bool(p == "linux-aarch64"),
        ppc64le=bool(p == "linux-ppc64le"),
        arm64=bool(p == "osx-arm64"),
        s390x=bool(p == "linux-s390x"),
        x86=p.endswith(("-32", "-64")),
        x86_64=p.endswith("-64"),
        osx=p.startswith("osx-"),
        unix=p.startswith(("linux-", "osx-")),
        win=p.startswith("win-"),
        win32=bool(p == "win-32"),
        win64=bool(p == "win-64"),
    )


# This regex is taken from https://github.com/conda/conda_build/metadata.py
# The following function "select_lines" is also a slightly modified version of
# the function of the same name from conda_build/metadata.py
sel_pat = re.compile(r"(.+?)\s*(#.*)?\[([^\[\]]+)\](?(2)[^\(\)]*)$")


def select_lines(data, namespace):
    lines = []

    for i, line in enumerate(data.splitlines()):
        line = line.rstrip()

        trailing_quote = ""
        if line and line[-1] in ("'", '"'):
            trailing_quote = line[-1]

        if line.lstrip().startswith("#"):
            # Don't bother with comment only lines
            continue
        m = sel_pat.match(line)
        if m:
            cond = m.group(3)
            try:
                if eval(cond, namespace, {}):
                    lines.append(m.group(1) + trailing_quote)
            except Exception as e:
                sys.exit(
                    """\
Error: Invalid selector in meta.yaml line %d:
offending line:
%s
exception:
%s
"""
                    % (i + 1, line, str(e))
                )
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


# adapted from conda-build
def yamlize(data, directory, content_filter):
    data = content_filter(data)
    try:
        return yaml.load(data)
    except YAMLError as e:
        if ("{{" not in data) and ("{%" not in data):
            raise UnableToParse(original=e)
        try:
            from constructor.jinja import render_jinja_for_input_file
        except ImportError as ex:
            raise UnableToParseMissingJinja2(original=ex)
        data = render_jinja_for_input_file(data, directory, content_filter)
        return yaml.load(data)


def parse(path, platform):
    try:
        with open(path) as fi:
            data = fi.read()
    except OSError:
        sys.exit("Error: could not open '%s' for reading" % path)
    directory = dirname(path)
    content_filter = partial(select_lines, namespace=ns_platform(platform))
    try:
        res = yamlize(data, directory, content_filter)
    except YamlParsingError as e:
        sys.exit(e.error_msg())

    try:
        res["version"] = str(res["version"])
    except KeyError:
        pass

    for key in list(res):
        if res[key] is None:
            del res[key]

    return res


# this is actually not an error, therefore the naming is okay
class DeprecatedFieldWarning(ValidationError):  # noqa: N818
    pass


def deprecated_validator(validator, value, instance, schema):
    if value and instance is not None:
        print(value)
        print(instance)
        print(schema)
        yield DeprecatedFieldWarning(f"'{schema['title']}' is deprecated.\n{schema['description']}")


def get_validator_class():
    all_validators = dict(Draft202012Validator.VALIDATORS)
    all_validators["deprecated"] = deprecated_validator

    return validators.create(
        meta_schema=Draft202012Validator.META_SCHEMA, validators=all_validators
    )


def verify(info):
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = get_validator_class()(schema)
    errors = []
    for error_or_warning in validator.iter_errors(info):
        if isinstance(error_or_warning, DeprecatedFieldWarning):
            print("Warning:", error_or_warning, file=sys.stderr)
        else:
            errors.append(error_or_warning)
    if errors:
        msg = ["Configuration has validation errors:"]
        for error in errors:
            msg.append(f"- {error}")
        sys.exit("\n".join(msg))

    for key in "name", "version":
        value = info[key]
        if value.endswith((".", "-")):
            sys.exit(f"Error: invalid {key} '{value}'. Cannot end with '.' or '-'.")

    if signtool := info.get("windows_signing_tool"):
        need_cert_file = ["signtool", "signtool.exe"]
        if signtool in need_cert_file and not info.get("signing_certificate"):
            sys.exit(f"The signing tool '{signtool}' requires 'signing_certificate' to be set.")
