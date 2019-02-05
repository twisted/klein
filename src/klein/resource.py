# -*- test-case-name: klein.test.test_resource.GlobalAppTests -*-

"""
This module, L{klein.resource}, serves two purposes:

    - It's the global C{resource()} method on the global L{klein.Klein}
      application.

    - It's the module where L{KleinResource} is defined.
"""
from sys import modules
from typing import TYPE_CHECKING

from ._app import resource as _globalResourceMethod
from ._resource import KleinResource as _KleinResource, ensure_utf8_bytes

if TYPE_CHECKING:
    from typing import AnyStr, Callable, Text
    AnyStr, Callable, Text
    KleinResource = _KleinResource

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

    KleinResource = _KleinResource

    @property
    def ensure_utf8_bytes(self):
        # type: () -> Callable[[AnyStr], Text]
        return ensure_utf8_bytes

    def __call__(self):
        # type: () -> _KleinResource
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """
        # Use the same docstring as the real implementation to reduce
        # confusion.
        return _globalResourceMethod()


    def __repr__(self):
        # type: () -> str
        """
        Give a special C{repr()} to make the dual purpose of this object clear.
        """
        return "<special bound method/module klein.resource>"


preserve = modules[__name__]
modules[__name__] = _SpecialModuleObject()  # type: ignore
modules[__name__].__preserve__ = preserve   # type: ignore
