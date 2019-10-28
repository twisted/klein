from typing import Callable, TYPE_CHECKING


__all__ = ()


def _ifmethod(method):
    # type: (Callable) -> Callable
    return method


if TYPE_CHECKING:  # pragma: no cover
    ifmethod = staticmethod
else:
    ifmethod = _ifmethod
