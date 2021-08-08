from typing import Any, Callable, Dict, Generator, List, Sequence, Type

import attr
from zope.interface import Interface, implementer

from twisted.internet.defer import inlineCallbacks
from twisted.python.components import Componentized
from twisted.web.iweb import IRequest

from ._app import _call
from ._decorators import bindable, modified
from .interfaces import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
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
        requires: Sequence[Type[Interface]] = (),
        provides: Sequence[Type[Interface]] = (),
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


_routeDecorator = Any  # a decorator like @route
_routeT = Any  # a thing decorated by a decorator like @route

_prerequisiteCallback = Callable[[IRequestLifecycle], None]


@attr.s(auto_attribs=True)
class Requirer:
    """
    Dependency injection for required parameters.
    """

    _prerequisites: List[_prerequisiteCallback] = attr.ib(factory=list)

    def prerequisite(
        self,
        providesComponents: Sequence[Type[Interface]],
        requiresComponents: Sequence[Type[Interface]] = (),
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
            @inlineCallbacks
            def router(
                instance: Any, request: IRequest, *args: Any, **routeParams: Any
            ) -> Any:
                injected = routeParams.copy()
                try:
                    yield lifecycle.runPrepareHooks(instance, request)
                    for (k, injector) in injectors.items():
                        injected[k] = yield injector.injectValue(
                            instance, request, routeParams
                        )
                except EarlyExit as ee:
                    result = ee.alternateReturnValue
                else:
                    result = yield _call(
                        instance, functionWithRequirements, *args, **injected
                    )
                return result

            fWR, iC = functionWithRequirements, injectionComponents
            fWR.injectionComponents = iC  # type: ignore[attr-defined]
            routeDecorator(router)
            return functionWithRequirements

        return decorator
