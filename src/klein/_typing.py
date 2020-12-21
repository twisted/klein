from typing import Callable, TYPE_CHECKING


__all__ = ()


if TYPE_CHECKING:  # pragma: no cover
    ifmethod = staticmethod

else:

    def ifmethod(method: Callable) -> Callable:
        return method
