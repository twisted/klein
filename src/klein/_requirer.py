
from typing import Any, Callable, List, TYPE_CHECKING

import attr

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.components import Componentized

from zope.interface import implementer

from ._app import _call
from ._decorators import bindable, modified
from .interfaces import EarlyExit, IRequestLifecycle

if TYPE_CHECKING:
    from typing import Dict, Tuple, Sequence
    from twisted.web.iweb import IRequest
    from twisted.internet.defer import Deferred
    from zope.interface.interfaces import IInterface
    from .interfaces import IDependencyInjector, IRequiredParameter
    IDependencyInjector, IRequiredParameter, IRequest, Dict, Tuple
    Deferred, IInterface, Sequence

@implementer(IRequestLifecycle)
@attr.s
class RequestLifecycle(object):
    """
    Before and after hooks.
    """
    _before = attr.ib(type=List, default=attr.Factory(list))
    _after = attr.ib(type=List, default=attr.Factory(list))

    def addBeforeHook(self, beforeHook, requires=(), provides=()):
        # type: (Callable, Sequence[IInterface], Sequence[IInterface]) -> None
        """
        Add a hook that promises to supply the given interfaces as components
        on the request, and requires the given requirements.
        """
        # TODO: topological requirements sort
        self._before.append(beforeHook)


    def addAfterHook(self, afterHook):
        # type: (Callable) -> None
        """
        Add a hook that will execute after the request has completed.
        """
        self._after.append(afterHook)


    @inlineCallbacks
    def runBeforeHooks(self, instance, request):
        # type: (Any, IRequest) -> Deferred
        """
        Execute all the "before" hooks.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.
        """
        for hook in self._before:
            yield _call(instance, hook, request)

    @inlineCallbacks
    def runAfterHooks(self, instance, request, result):
        # type: (Any, IRequest, Any) -> Deferred
        """
        Execute all "after" hooks.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.

        @param result: The result produced by the route.
        """
        for hook in self._after:
            yield _call(instance, hook, request, result)

_routeDecorator = Any           # a decorator like @route
_routeT = Any                   # a thing decorated by a decorator like @route

_prerequisiteCallback = Callable[[IRequestLifecycle], None]

@attr.s
class Requirer(object):
    """
    Dependency injection for required parameters.
    """
    _prerequisites = attr.ib(
        type=List[_prerequisiteCallback],
        default=attr.Factory(list)
    )

    def prerequisite(
            self,
            providesComponents,   # type: Sequence[IInterface]
            requiresComponents=()  # type: Sequence[IInterface]
    ):
        # type: (...) -> Callable[[Callable], Callable]
        """
        Prerequisite.
        """
        def decorator(prerequisiteMethod):
            # type: (Callable) -> Callable
            def oneHook(lifecycle):
                # type: (IRequestLifecycle) -> None
                lifecycle.addBeforeHook(
                    prerequisiteMethod, requires=requiresComponents,
                    provides=providesComponents
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
            # type: (Any) -> Callable
            injectionComponents = Componentized()
            lifecycle = RequestLifecycle()
            injectionComponents.setComponent(IRequestLifecycle, lifecycle)

            injectors = {}      # type: Dict[str, IDependencyInjector]

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
            def router(instance, request, *args, **kw):
                # type: (Any, IRequest, *Any, **Any) -> Any
                injected = {}
                try:
                    yield lifecycle.runBeforeHooks(instance, request)
                    for (k, injector) in injectors.items():
                        injected[k] = yield injector.injectValue(request)
                except EarlyExit as ee:
                    returnValue(ee.alternateReturnValue)
                kw.update(injected)
                result = yield _call(instance, functionWithRequirements,
                                     request, *args, **kw)
                lifecycle.runAfterHooks(instance, request, result)
                returnValue(result)

            functionWithRequirements.injectionComponents = injectionComponents
            routeDecorator(router)
            return functionWithRequirements

        return decorator
