# -*- test-case-name: klein.test.test_resource.GlobalAppTests -*-

"""
This module, L{klein.resource}, serves two purposes:

    - It's the global C{resource()} method on the global L{klein.Klein}
      application.

    - It's the module where L{KleinResource} is defined.
"""

from sys import modules
from typing import Any, Callable, Union

from ._app import resource as _globalResourceMethod
from ._resource import KleinResource as _KleinResource
from ._resource import ensure_utf8_bytes


KleinResource = _KleinResource


class _SpecialModuleObject:
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

    def __init__(self, preserve: Any) -> None:
        self.__preserve__ = preserve

    @property
    def ensure_utf8_bytes(self) -> Callable[[Union[str, bytes]], bytes]:
        return ensure_utf8_bytes

    def __call__(self) -> _KleinResource:
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """
        # Use the same docstring as the real implementation to reduce
        # confusion.
        return _globalResourceMethod()

    def __repr__(self) -> str:
        """
        Give a special C{repr()} to make the dual purpose of this object clear.
        """
        return "<special bound method/module klein.resource>"


module = _SpecialModuleObject(modules[__name__])
modules[__name__] = module  # type: ignore[assignment]
