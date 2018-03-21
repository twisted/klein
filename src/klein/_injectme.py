
import attr

from twisted.python.components import Componentized
from twisted.internet.defer import inlineCallbacks, returnValue

from klein._decorators import modified
from klein._decorators import bindable
from klein._app import _call

@attr.s
class RequestLifecycle(object):
    """
    Before and after hooks.
    """
    before = attr.ib(default=attr.Factory(list))
    after = attr.ib(default=attr.Factory(list))

def inject(routeDecorator, **requiredParameters):
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
                beforeHook(request)
            for (k, injector) in injectors.items():
                injected[k] = yield injector.injectValue(request)
            kw.update(injected)
            result = yield _call(instance, *args, **kw)
            for afterHook in lifecycle.after:
                afterHook(request, result)
            returnValue(result)

        functionWithRequirements.injectionComponents = injectionComponents
        return functionWithRequirements

    return decorator
