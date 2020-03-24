from typing import Any, Callable, Dict, List, Sequence

import attr

from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.python.components import Componentized
from twisted.web.iweb import IRequest

from zope.interface import implementer
from zope.interface.interfaces import IInterface

from ._app import _call
from ._decorators import bindable, modified
from .interfaces import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
)


@implementer(IRequestLifecycle)  # type: ignore[misc]
@attr.s
class RequestLifecycle(object):
    """
    Mechanism to run hooks at the start of a request managed by a L{Requirer}.
    """

    _prepareHooks = attr.ib(type=List, default=attr.Factory(list))

    def addPrepareHook(self, beforeHook, requires=(), provides=()):
        # type: (Callable, Sequence[IInterface], Sequence[IInterface]) -> None
        """
        Add a hook that promises to prepare the request by supplying the given
        interfaces as components on the request, and requires the given
        requirements.

        Prepare hooks are run I{before any} L{IDependencyInjector}s I{inject
        their values}.
        """
        # TODO: topological requirements sort
        self._prepareHooks.append(beforeHook)

    @inlineCallbacks
    def runPrepareHooks(self, instance, request):
        # type: (Any, IRequest) -> Deferred
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


@attr.s
class Requirer(object):
    """
    Dependency injection for required parameters.
    """

    _prerequisites = attr.ib(
        type=List[_prerequisiteCallback], default=attr.Factory(list)
    )

    def prerequisite(
        self,
        providesComponents,  # type: Sequence[IInterface]
        requiresComponents=(),  # type: Sequence[IInterface]
    ):
        # type: (...) -> Callable[[Callable], Callable]
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

        def decorator(prerequisiteMethod):
            # type: (Callable) -> Callable
            def oneHook(lifecycle):
                # type: (IRequestLifecycle) -> None
                lifecycle.addPrepareHook(
                    prerequisiteMethod,
                    requires=requiresComponents,
                    provides=providesComponents,
                )

            self._prerequisites.append(oneHook)
            return prerequisiteMethod

        return decorator

    def require(self, routeDecorator, **requiredParameters):
        # type: (_routeT, **IRequiredParameter) -> _routeDecorator
        """
        Inject the given dependencies while running the given route.
        """

        def decorator(functionWithRequirements):
            # type: (Callable) -> Callable
            injectionComponents = Componentized()
            lifecycle = RequestLifecycle()
            injectionComponents.setComponent(
                IRequestLifecycle, lifecycle  # type: ignore[misc]
            )

            injectors = {}  # type: Dict[str, IDependencyInjector]

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
            def router(instance, request, *args, **routeParams):
                # type: (Any, IRequest, *Any, **Any) -> Any
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
                returnValue(result)

            fWR, iC = functionWithRequirements, injectionComponents
            fWR.injectionComponents = iC  # type: ignore[attr-defined]
            routeDecorator(router)
            return functionWithRequirements

        return decorator
