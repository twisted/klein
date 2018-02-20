"""
Workaround for the bridge between zope.interface until
https://github.com/python/mypy/issues/3960 can be resolved.
"""

from zope.interface import IInterface
from typing import cast, TYPE_CHECKING, Type, TypeVar, Any
if TYPE_CHECKING:
    IInterface, Type, Any

I = TypeVar("I")
def zcast(interface, provider):
    # type: (Type[I], Any) -> I
    """
    Combine ZI's run-time type checking with mypy-time type checking.
    """
    if not cast(Any, interface).providedBy(provider):
        raise NotImplementedError()
    return cast(I, provider)
