
from twisted.python.components import Componentized, registerAdapter
from twisted.internet.defer import inlineCallbacks, returnValue

from klein._decorators import modified
from klein._decorators import bindable
from klein._app import _call
from zope.interface import Interface

class  IProtoForm(object):
    """
    
    """
    

class ProtoForm(object):
    """
    
    """
    def __init__(self, componentized):
        """
        
        """
        self._finalForm = None
        self._parameters = []

    def finalize(self):
        """
        
        """
        

registerAdapter(ProtoForm, Componentized, IProtoForm)

@attr.s
class FormParameter(object):
    """
    A parameter for a form.
    """

    def registerInjector(self, registeredOn, parameterName):
        """
        Registered with the given injector.
        """
        protoForm = IProtoForm(registeredOn)
        protoForm._parameters.append()


    def injectValue(self, request):
        """
        
        """



def inject(routeDecorator, **dependencies):
    # type: (_routeT, **IDependencyInjector) -> _routeDecorator
    """
    Inject the given dependencies while running the given route.
    """
    def decorator(functionWithRequirements):
        injectionComponents = Componentized()

        for k, v in dependencies.items():
            v.registerInjector(injectionComponents, k)

        for v in dependencies.values():
            v.finalize()

        @modified("dependency-injecting route", routeDecorator)
        @bindable
        @inlineCallbacks
        def router(instance, request, *args, **kw):
            injected = {}
            for (k, injector) in dependencies.items():
                injected[k] = yield injector.injectValue(request)
            kw.update(injected)
            result = yield _call(instance, *args, **kw)
            returnValue(result)

        functionWithRequirements.injectionComponents = injectionComponents
        return functionWithRequirements

    return decorator
