from typing import TYPE_CHECKING


__all__ = ()


if TYPE_CHECKING:               # pragma: no cover
    ifmethod = staticmethod
else:
    def ifmethod(method):
        return method
