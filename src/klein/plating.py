# -*- test-case-name: klein.test.test_plating -*-

from functools import wraps
from json import dumps as json_serialize

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

    def routed(self, routing, content_template):
        """
        
        """
        @wraps(routing)
        def mydecorator(method):
            loader = TagLoader(content_template)
            @routing
            @wraps(method)
            def mymethod(request, *args, **kw):
                data = method(request, *args, **kw)
                if _should_return_json(request):
                    json_data = self._defaults.copy()
                    del json_data["content"]
                    json_data.update(data)
                    return json_serialize(json_data)
                else:
                    return self._elementify(loader, data)
            return method
        return mydecorator

    def _elementify(self, loader, toFillWith):
        """
        
        """
        slotData = self._defaults.copy()
        slotData.update(toFillWith)
        slotData.update(content=Element(loader=loader))
        [loaded] = self._loader.load()
        loaded = loaded.clone()
        return Element(loader=TagLoader(loaded.fillSlots(**slotData)))
