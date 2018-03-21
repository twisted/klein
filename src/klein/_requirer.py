
import attr

from twisted.python.components import Componentized
from twisted.internet.defer import inlineCallbacks, returnValue

from klein._decorators import modified
from klein._decorators import bindable
from klein._app import _call

from typing import List, Callable

@attr.s
class RequestLifecycle(object):
    """
    Before and after hooks.
    """
    before = attr.ib(default=attr.Factory(list))
    after = attr.ib(default=attr.Factory(list))


_finalizish = List[Callable[Componentized, [RequestLifecycle], None]]

@attr.s
class Requirer(object):
    """
    Dependency injection for required parameters.
    """
    _prerequisites = attr.ib()  # type: _finalizish

    def prerequisite(self, requiredRequestComponent):
        # type: (_finalizish) -> _finalizish
        """
        Prerequisite.
        """
        def decorator(prerequisiteMethod):
            self._prerequisites.append(prerequisiteMethod)
            return prerequisiteMethod
        return decorator


    def require(self, routeDecorator, **requiredParameters):
        # type: (_routeT, **IDependencyInjector) -> _routeDecorator
        """
        Inject the given dependencies while running the given route.
        """

        def decorator(functionWithRequirements):
            injectionComponents = Componentized()

            injectors = {}
            for parameterName, required in requiredParameters.items():
                injectors[parameterName] = required.registerInjector(
                    injectionComponents, parameterName
                )

            lifecycle = RequestLifecycle()

            for v in injectors.values():
                v.finalize(lifecycle)

            @modified("dependency-injecting route", routeDecorator)
            @bindable
            @inlineCallbacks
            def router(instance, request, *args, **kw):
                injected = {}
                for beforeHook in lifecycle.before:
                    beforeHook(instance, request)
                for (k, injector) in injectors.items():
                    injected[k] = yield injector.injectValue(request)
                kw.update(injected)
                result = yield _call(instance, *args, **kw)
                for afterHook in lifecycle.after:
                    afterHook(instance, request, result)
                returnValue(result)

            functionWithRequirements.injectionComponents = injectionComponents
            return functionWithRequirements

        return decorator
