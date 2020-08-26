from typing import Callable, TYPE_CHECKING, Union

try:
    from typing import Awaitable
except ImportError:
    Awaitable = Union  # type: ignore[assignment,misc]


__all__ = ()


def _ifmethod(method: Callable) -> Callable:
    return method


if TYPE_CHECKING:  # pragma: no cover
    from mypy_extensions import Arg, DefaultNamedArg, KwArg, NoReturn, VarArg

    ifmethod = staticmethod
else:
    Arg = KwArg = VarArg = lambda t, *x: t

    def DefaultNamedArg(*ignore):
        pass

    NoReturn = None

    ifmethod = _ifmethod
