# -*- test-case-name: klein.test.test_plating -*-

from functools import wraps

from twisted.web.template import TagLoader, Element



def _should_return_json(request):
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get("json"))


class Plating(object):
    """
    
    """
    def __init__(self, defaults, tags):
        """
        
        """
        self._defaults = defaults
        self._loader = TagLoader(tags)

    def routed(self, routing, content_template, *args):
        """
        
        """
        @wraps(routing)
        def mydecorator(method):
            return routing(self.content(content_template, *args)(method))
        return mydecorator

    def content(self, content_template):
        """
        
        """
        loader = TagLoader(content_template)
        def decorate(thunk):
            @wraps(thunk)
            def decorator(*a, **k):
                slotData = self._defaults.copy()
                toFillWith = thunk(*a, **k)
                slotData.update(toFillWith)
                slotData.update(content=Element(loader=loader))
                [loaded] = self._loader.load()
                loaded = loaded.clone()
                return Element(loader=TagLoader(loaded.fillSlots(**slotData)))
            return decorator
        return decorate
