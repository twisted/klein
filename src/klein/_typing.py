from typing import Any, Callable, TYPE_CHECKING, Type


__all__ = ()


def _ifmethod(method: Callable) -> Callable:
    return method


if TYPE_CHECKING:  # pragma: no cover
    from mypy_extensions import Arg, KwArg, VarArg

    ifmethod = staticmethod

else:

    def _arg(type: Type[Any], name: str) -> Type[Any]:
        return type

    Arg = KwArg = VarArg = _arg

    ifmethod = _ifmethod
