# -*- test-case-name: klein.test.test_resource.GlobalAppTests.test_weird_resource_situation -*-

"""
This module, L{klein.resource}, serves two purposes:

    - It's the global C{resource()} method on the global L{klein.Klein}
      application.

    - It's the module where L{KleinResource} is defined.
"""

from ._resource import KleinResource, ensure_utf8_bytes
from ._app import resource
from sys import modules

class _SpecialModuleObject(object):
    """
    See the test in
    L{klein.test.test_resource.GlobalAppTests.test_weird_resource_situation}
    for an explanation.
    """

    __all__ = (
        "KleinResource",
        "ensure_utf8_bytes",
    )

    KleinResource = KleinResource

    @property
    def ensure_utf8_bytes(self):
        return ensure_utf8_bytes

    def __call__(self):
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """
        # Use the same docstring as the real implementation to reduce
        # confusion.
        return resource()


    def __repr__(self):
        """
        Give a special C{repr()} to make the dual purpose of this object clear.
        """
        return "<special bound method/module klein.resource>"


modules[__name__] = _SpecialModuleObject()
