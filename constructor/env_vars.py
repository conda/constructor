# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""A local replacement for the deprecated ``conda.common.io.env_vars`` helper."""

from __future__ import annotations

from contextlib import contextmanager
from os import environ

_UNSET = object()


def _encode_env_value(value) -> str:
    """Environment names and values need to be strings, as conda's own helper also ensures."""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


@contextmanager
def env_vars(var_map=None, callback=None):
    """Temporarily set environment variables, restoring the previous values afterwards.

    ``conda.common.io.env_vars`` is pending deprecation (removed in conda 27.3) and its suggested
    replacement is pytest-only, so constructor keeps its own copy. ``callback`` runs once the
    variables are set and again once they are restored, which is what refreshes conda's context.
    """
    if var_map is None:
        var_map = {}

    new_var_map = {
        _encode_env_value(name): _encode_env_value(value) for name, value in var_map.items()
    }
    saved_vars = {}
    for name, value in new_var_map.items():
        saved_vars[name] = environ.get(name, _UNSET)
        environ[name] = value

    try:
        if callback is not None:
            callback()
        yield
    finally:
        for name, value in saved_vars.items():
            if value is _UNSET:
                del environ[name]
            else:
                environ[name] = value
        if callback is not None:
            callback()
