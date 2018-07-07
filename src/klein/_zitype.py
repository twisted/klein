"""
Workaround for the bridge between zope.interface until
https://github.com/python/mypy/issues/3960 can be resolved.
"""

from typing import Any, TYPE_CHECKING, Type, TypeVar, cast

from zope.interface.interfaces import IInterface

if TYPE_CHECKING:               # pragma: no cover
    IInterface, Type, Any

T = TypeVar("T")

def zcast(interface, provider):
    # type: (Type[T], Any) -> T
    """
    Combine ZI's run-time type checking with mypy-time type checking.
    """
    if not cast(Any, interface).providedBy(provider):
        raise NotImplementedError()
    return cast(T, provider)
