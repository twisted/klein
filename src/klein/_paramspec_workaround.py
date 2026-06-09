"""
This module is mostly type gymnastics to work around a few issues:

    1. We want to ensure that we are faithfully I{relaying} the signature of
       L{werkzeug.routing.Rule} and type-checking against its underlying
       implementation, rather than blindly copying it, since that is what we
       are actually doing at runtime.

    2. Unfortunately for that first goal, U{we cannot add or remove
       keyword-only arguments with ParamSpec directly
       <https://discuss.python.org/t/allow-keyword-only-parameters-with-paramspec/39326>},
       which means that we need to save the actually-variable ParamSpec part of
       the signature for our keyword-only C{branch} argument, which means we
       I{do} need to copy/paste the signature for L{Rule}'s constructor with a
       few manual modifications, I{however} we still have some validation that
       it matches which will start failing if the underlying library is
       modified.

    3. U{Mypy has some type confusion about callables
       <https://github.com/python/mypy/issues/15189>} which makes these
       gymnastics produce the wrong type of decorator, so we need a decorator
       on top of that decorator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, TypeVar

from werkzeug.routing import Rule

from ._typing_compat import ParamSpec, Protocol


if TYPE_CHECKING:
    from ._app import Klein

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)


class _RuleCopy(Protocol[P, R_co]):
    """
    Workaround for the lack of U{keyword-only arguments with ParamSpec
    <https://discuss.python.org/t/allow-keyword-only-parameters-with-paramspec/39326>}.
    """

    def __call__(
        _self,
        self: Klein,
        # string: str,
        url: str,
        defaults: Mapping[str, Any] | None = None,
        subdomain: str | None = None,
        methods: Iterable[str] | None = None,
        build_only: bool = False,
        endpoint: Any | None = None,
        strict_slashes: bool | None = None,
        merge_slashes: bool | None = None,
        redirect_to: str | Callable[..., str] | None = None,
        alias: bool = False,
        host: str | None = None,
        websocket: bool = False,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R_co:
        """
        The constructor signature for L{Rule}, with the modifications described
        in L{_adjustArgs}.
        """


if TYPE_CHECKING:

    class WithStringArg(Protocol[P, R_co]):
        def __call__(
            self, string: str, *args: P.args, **kwargs: P.kwargs
        ) -> R_co: ...

    class WithURLArg(Protocol[P, R_co]):
        def __call__(
            _self, self: Klein, url: str, *args: P.args, **kwargs: P.kwargs
        ) -> R_co: ...

    def _adjustArgs(rule: WithStringArg[P, R]) -> WithURLArg[P, R]:
        """
        We call our equivalent to the C{string} argument to L{Rule} C{url}, and
        we need to add a L{Klein} C{self}.
        """

    """
    Ensure that we match L{Rule}'s signature precisely, by checking against the
    installed upstream library.
    """
    _checkRuleArgs: _RuleCopy[[], Rule] = _adjustArgs(Rule)


def kwOnlyBranchArg(*, branch: bool = False) -> None: ...


class _PartialRouteSignature(Protocol[R_co]):
    def __call__(
        _self,
        self: Klein,
        url: str,
        *args: Any,
        branch: bool = False,
        **kwargs: Any,
    ) -> R_co:
        """
        This is the portion of the signature of C{route} which Klein owns.
        """


def _routeArgsWith(
    argProvider: Callable[P, object],
) -> Callable[[_PartialRouteSignature[R]], _RuleCopy[P, R]]:
    def decorator(
        decoratee: _PartialRouteSignature[R],
    ) -> _RuleCopy[P, R]:
        # branch kw-only arg is encoded in `P` via kwOnlyBranchArg so we cannot
        # check it here.
        return decoratee  # type:ignore[return-value]

    return decorator


def _normalFunction(arg: Callable[P, R]) -> Callable[P, R]:
    """
    Indicate to Mypy that the decorated callable is in fact a normal
    user-defined function, so that it will be treated as a descriptor with a
    C{self} that binds as a method.

    @see: U{<mypy's confusing treatment of callables>
        https://github.com/python/mypy/issues/15189}
    """
    return arg


_werkzeugRuleArgs = _routeArgsWith(kwOnlyBranchArg)
