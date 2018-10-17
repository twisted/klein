
from typing import Any, Callable, List, TYPE_CHECKING

import attr

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python.components import Componentized
from twisted.python.failure import Failure

from zope.interface import implementer

from ._app import _call
from ._decorators import bindable, modified
from .interfaces import EarlyExit, IRequestLifecycle

if TYPE_CHECKING:               # pragma: no cover
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
    _prepareHooks = attr.ib(type=List, default=attr.Factory(list))
    _commitHooks = attr.ib(type=List, default=attr.Factory(list))
    _failureHooks = attr.ib(type=List, default=attr.Factory(list))

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


    def addCommitHook(self, afterHook):
        # type: (Callable) -> None
        """
        Add a hook that will execute after the route has been successfully
        invoked.  It is I{intended} to be invoked at the point after the
        response has been computed, but before it has been sent to the client.
        The name "commit" has a double meaning here:

            - we are "committed" to sending the response at this point - it has
              been computed by the routing layer, and all that remains is to
              render it.

            - this is the point at which where framework code might want to
              "commit" any results to a backing store, such as committing a
              database transaction started in a prepare hook.

        However, given the wide API surface of Twisted's API request, it is
        unfortunately impossible to provide strong guarantees about the timing
        of this hook with respect to the HTTP protocol.  Application code
        I{may} have written the headers and started the repsonse with
        C{response.write}.
        """
        self._commitHooks.append(afterHook)


    def addFailureHook(self, failureHook):
        # type: (Callable) -> None
        """
        Add a hook that will execute after a route has exited with some kind of
        exception.  This is for performing any cleanup or reporting which needs
        to happen after the fact in an error case.
        """
        self._failureHooks.append(failureHook)


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


    @inlineCallbacks
    def runCommitHooks(self, instance, request, result):
        # type: (Any, IRequest, Any) -> Deferred
        """
        Execute all the hooks added with L{RequestLifecycle.addCommitHook}.
        This is invoked by the L{requires} route machinery.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.

        @param result: The result produced by the route.
        """
        for hook in self._commitHooks:
            yield _call(instance, hook, request, result)


    @inlineCallbacks
    def runFailureHooks(self, instance, request, failure):
        # type: (Any, IRequest, Failure) -> Deferred
        """
        Execute all the hooks added with L{RequestLifecycle.addFailureHook}
        This is invoked by the L{requires} route machinery.

        @param instance: The instance bound to the Klein route.

        @param request: The IRequest being processed.

        @param failure: The failure which caused an error.
        """
        for hook in self._failureHooks:
            yield _call(instance, hook, request, failure)



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
                lifecycle.addPrepareHook(
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
            def router(instance, request, *args, **routeParams):
                # type: (Any, IRequest, *Any, **Any) -> Any
                injected = routeParams.copy()
                try:
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
                            instance, functionWithRequirements, *args,
                            **injected
                        )
                except Exception:
                    lifecycle.runFailureHooks(instance, request, Failure())
                    raise
                else:
                    lifecycle.runCommitHooks(instance, request, result)
                    returnValue(result)

            functionWithRequirements.injectionComponents = injectionComponents
            routeDecorator(router)
            return functionWithRequirements

        return decorator
