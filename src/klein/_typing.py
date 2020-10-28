from typing import Any, Callable, Optional, TYPE_CHECKING, Type, Union

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

    # Match signatures from:
    # https://github.com/python/mypy_extensions/blob/master/mypy_extensions.py#L109
    def _argumentConstructor(
        type=Type[Any], name: Optional[str] = None
    ) -> Type[Any]:
        return type

    Arg = KwArg = VarArg = DefaultNamedArg = _argumentConstructor

    NoReturn = None

    ifmethod = _ifmethod
