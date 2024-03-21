from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Coroutine, TypeVar

from twisted.internet.defer import Deferred

from ._typing_compat import ParamSpec


_T = TypeVar("_T")
_P = ParamSpec("_P")

if TYPE_CHECKING:  # pragma: no cover
    # https://github.com/twisted/twisted/issues/11862
    def deferToThread(f: Callable[[], _T]) -> Deferred[_T]:
        ...

else:
    from twisted.internet.threads import deferToThread


def eagerDeferredCoroutine(
    f: Callable[_P, Coroutine[Deferred[object], object, _T]]
) -> Callable[_P, Deferred[_T]]:
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> Deferred[_T]:
        return Deferred.fromCoroutine(f(*args, **kwargs))

    return inner


def threadedDeferredFunction(f: Callable[_P, _T]) -> Callable[_P, Deferred[_T]]:
    """
    When the decorated function is called, always run it in a thread.
    """

    def inner(*args: _P.args, **kwargs: _P.kwargs) -> Deferred[_T]:
        return deferToThread(lambda: f(*args, **kwargs))

    return inner


__all__ = [
    "eagerDeferredCoroutine",
    "deferToThread",
    "threadedDeferredFunction",
]
