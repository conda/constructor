try:
    from ._version import version as __version__
except ImportError:
    try:
        from importlib.metadata import version

        __version__ = version("constructor")
        del version
    except ImportError:
        __version__ = "0.0.0.unknown"
