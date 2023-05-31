# -*- test-case-name: klein.test.test_requirer -*-
from contextlib import AsyncExitStack
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Sequence,
    Type,
    TypeVar,
    Union,
)

import attr
from zope.interface import implementer

from twisted.internet.defer import inlineCallbacks
from twisted.python.components import Componentized
from twisted.web.iweb import IRequest
from twisted.web.server import Request

from ._app import _call
from ._decorators import bindable, modified
from ._util import eagerDeferredCoroutine
from .interfaces import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
    IRequirementContext,
)


@implementer(IRequestLifecycle)
@attr.s(auto_attribs=True)
class RequestLifecycle:
    """
    Mechanism to run hooks at the start of a request managed by a L{Requirer}.
    """

    _prepareHooks: List = attr.ib(factory=list)

    def addPrepareHook(
        self,
        beforeHook: Callable,
        requires: Sequence[Type[object]] = (),
        provides: Sequence[Type[object]] = (),
    ) -> None:
        # TODO: topological requirements sort
        self._prepareHooks.append(beforeHook)

    @inlineCallbacks
    def runPrepareHooks(
        self, instance: Any, request: IRequest
    ) -> Generator[Any, object, None]:
        """
        Execute all the hooks added with L{RequestLifecycle.addPrepareHook}.
        This is invoked by the L{requires} route machinery.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.
        """
        for hook in self._prepareHooks:
            yield _call(instance, hook, request)


@implementer(IRequirementContext)
class RequirementContext(AsyncExitStack):
    """
    Subclass only to mark the implementation of this interface; this is in
    every way an C{ExitStack}.
    """


_routeDecorator = Any  # a decorator like @route
_routeT = Any  # a thing decorated by a decorator like @route

_prerequisiteCallback = Callable[[IRequestLifecycle], None]

T = TypeVar("T")


async def _maybeAsync(v: Union[T, Awaitable[T]]) -> T:
    if isinstance(v, Awaitable):
        return await v
    return v


@attr.s(auto_attribs=True)
class Requirer:
    """
    Dependency injection for required parameters.
    """

    _prerequisites: List[_prerequisiteCallback] = attr.ib(factory=list)

    def prerequisite(
        self,
        providesComponents: Sequence[Type[object]],
        requiresComponents: Sequence[Type[object]] = (),
    ) -> Callable[[Callable], Callable]:
        """
        Specify a component that is a pre-requisite of every request routed
        through this requirer's C{require} method.  Used like so::

            requirer = Requirer()

            @requirer.prerequisite([IFoo])
            @inlineCallbacks
            def fooForRequest(request):
                request.setComponent(IFoo, someFooComponent)

        @note: C{requiresComponents} is, at this point, for the reader's
            interest only, the framework will not topologically sort
            dependencies; you must presently register prerequisites in the
            order you want them to be called.
        """

        def decorator(prerequisiteMethod: Callable) -> Callable:
            def oneHook(lifecycle: IRequestLifecycle) -> None:
                lifecycle.addPrepareHook(
                    prerequisiteMethod,
                    requires=requiresComponents,
                    provides=providesComponents,
                )

            self._prerequisites.append(oneHook)
            return prerequisiteMethod

        return decorator

    def require(
        self, routeDecorator: _routeT, **requiredParameters: IRequiredParameter
    ) -> _routeDecorator:
        """
        Inject the given dependencies while running the given route.
        """

        def decorator(functionWithRequirements: Callable) -> Callable:
            injectionComponents = Componentized()
            lifecycle = RequestLifecycle()
            injectionComponents.setComponent(IRequestLifecycle, lifecycle)

            injectors: Dict[str, IDependencyInjector] = {}

            for parameterName, required in requiredParameters.items():
                injectors[parameterName] = required.registerInjector(
                    injectionComponents, parameterName, lifecycle
                )

            for prereq in self._prerequisites:
                prereq(lifecycle)

            for v in injectors.values():
                v.finalize()

            @modified("dependency-injecting route", functionWithRequirements)
            @bindable
            @eagerDeferredCoroutine
            async def router(
                instance: Any, request: Request, *args: Any, **routeParams: Any
            ) -> Any:
                try:
                    async with RequirementContext() as stack:
                        request.setComponent(IRequirementContext, stack)
                        injected = routeParams.copy()
                        await lifecycle.runPrepareHooks(instance, request)
                        for k, injector in injectors.items():
                            injected[k] = await _maybeAsync(
                                injector.injectValue(
                                    instance, request, routeParams
                                )
                            )
                        return await _maybeAsync(
                            _call(
                                instance,
                                functionWithRequirements,
                                *args,
                                **injected,
                            )
                        )
                except EarlyExit as ee:
                    return ee.alternateReturnValue

            fWR, iC = functionWithRequirements, injectionComponents
            fWR.injectionComponents = iC  # type: ignore[attr-defined]
            routeDecorator(router)
            return functionWithRequirements

        return decorator
