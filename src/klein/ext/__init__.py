# -*- test-case-name: klein.test.test_ext -*-

"""Dynamic extension grabbing module."""

def load_extensions():
    """Load extensions.

    Returns dictionary of extension modules.
    Keys of the dictionary are the named under which given modules should be made available in this package.
    """
    import pkgutil

    prefix = "klein_"
    rv = {}

    for (loader, name, ispkg) in pkgutil.iter_modules():
        if name.startswith(prefix):
            local_name = name[len(prefix):]
            module = __import__(name)
            rv[local_name] = module

    return rv

exts = load_extensions()
globals().update(exts)
del load_extensions
del exts