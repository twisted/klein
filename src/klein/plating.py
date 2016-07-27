# -*- test-case-name: klein.test.test_plating -*-

from functools import wraps
from json import dumps as json_serialize

from twisted.web.template import TagLoader, Element, renderer


def _should_return_json(request):
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get("json"))



class PlatedElement(Element):
    """
    The element type returned by L{Plating}.  This contains several utility
    renderers.
    """

    def __init__(self, slot_data, preloaded):
        """
        
        """
        self.slot_data = slot_data
        super(PlatedElement, self).__init__(
            loader=TagLoader(preloaded.fillSlots(**slot_data))
        )

    @renderer
    def sequence(self, request, tag):
        """
        The 'sequence' renderer will render items from the slot data 'sequence'
        into the tag-slot 'item'.
        """
        for item in self.slot_data["sequence"]:
            yield tag.fillSlots(item=item)



class Plating(object):
    """
    
    """
    def __init__(self, defaults=None, tags=None):
        """
        
        """
        if defaults is None:
            defaults = {}
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
                    data.update(content=Element(loader=loader))
                    return self._elementify(data)
            return method
        return mydecorator

    def _elementify(self, to_fill_with):
        """
        
        """
        slot_data = self._defaults.copy()
        slot_data.update(to_fill_with)
        [loaded] = self._loader.load()
        loaded = loaded.clone()
        return PlatedElement(slot_data=slot_data,
                             preloaded=loaded)

    def __call__(self, function):
        """
        
        """
        @wraps(function)
        def wrapper(*a, **k):
            data = function(*a, **k)
            return self._elementify(data)
        return wrapper
