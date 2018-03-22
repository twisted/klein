
from typing import Callable, List

import attr

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.components import Componentized

from zope.interface import implementer

from klein._app import _call
from klein._decorators import bindable, modified
from klein._interfaces import EarlyExit, IRequestLifecycle

@implementer(IRequestLifecycle)
@attr.s
class RequestLifecycle(object):
    """
    Before and after hooks.
    """
    _before = attr.ib(default=attr.Factory(list))
    _after = attr.ib(default=attr.Factory(list))

    def addBeforeHook(self, beforeHook, requires=(), provides=()):
        """
        Add a hook that promises to supply the given interfaces as components
        on the request, and requires the given requirements.
        """
        # TODO: topological requirements sort
        self._before.append(beforeHook)


    def addAfterHook(self, afterHook):
        """
        Add a hook that will execute after the request has completed.
        """
        self._after.append(afterHook)


    @inlineCallbacks
    def runBeforeHooks(self, instance, request):
        """
        Execute all the "before" hooks.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.
        """
        for hook in self._before:
            yield _call(instance, hook, request)

    @inlineCallbacks
    def runAfterHooks(self, instance, request, result):
        """
        Execute all "after" hooks.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.

        @param result: The result produced by the route.
        """
        for hook in self._after:
            yield _call(instance, hook, request, result)


_finalizish = List[Callable[[Componentized, RequestLifecycle], None]]

@attr.s
class Requirer(object):
    """
    Dependency injection for required parameters.
    """
    _prerequisites = attr.ib(
        default=attr.Factory(list))  # type: List[_finalizish]

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
            # type(Callable) -> Callable
            self._prerequisites.append(
                lambda lifecycle: lifecycle.addBeforeHook(
                    prerequisiteMethod, requires=requiresComponents,
                    provides=providesComponents
                )
            )
            return prerequisiteMethod
        return decorator


    def require(self, routeDecorator, **requiredParameters):
        # type: (_routeT, **IDependencyInjector) -> _routeDecorator
        """
        Inject the given dependencies while running the given route.
        """

        def decorator(functionWithRequirements):
            injectionComponents = Componentized()
            lifecycle = RequestLifecycle()
            injectionComponents.setComponent(IRequestLifecycle, lifecycle)

            injectors = {}

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
                injected = {}
                try:
                    yield lifecycle.runBeforeHooks(instance, request)
                    for (k, injector) in injectors.items():
                        injected[k] = yield injector.injectValue(request)
                except EarlyExit as ee:
                    return ee.alternateReturnValue
                kw.update(injected)
                result = yield _call(instance, functionWithRequirements,
                                     request, *args, **kw)
                lifecycle.runAfterHooks(instance, request, result)
                returnValue(result)

            functionWithRequirements.injectionComponents = injectionComponents
            routeDecorator(router)
            return functionWithRequirements

        return decorator
