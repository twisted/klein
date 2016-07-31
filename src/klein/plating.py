# -*- test-case-name: klein.test.test_plating -*-

"""
Templating wrapper support for Klein.
"""

from functools import wraps
from json import dumps

from six import text_type, integer_types

from twisted.web.template import TagLoader, Element
from twisted.web.error import MissingRenderMethod

CONTENT = "klein:plating:content"


def _should_return_json(request):
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get("json"))


def json_serialize(item):
    """
    A function similar to L{dumps}.
    """
    def helper(unknown):
        if isinstance(unknown, PlatedElement):
            return unknown.slot_data
    return dumps(item, default=helper)


def _extra_types(input):
    """
    Renderability for a few additional types.
    """
    if isinstance(input, (float,) + integer_types):
        return text_type(input)
    return input


class PlatedElement(Element):
    """
    The element type returned by L{Plating}.  This contains several utility
    renderers.
    """

    def __init__(self, slot_data, preloaded):
        """
        @param slot_data: A dictionary mapping names to values.

        @param preloaded: The pre-loaded data.
        """
        self.slot_data = slot_data
        super(PlatedElement, self).__init__(
            loader=TagLoader(preloaded.fillSlots(
                **{k: _extra_types(v) for k, v in slot_data.items()}
            ))
        )

    def lookupRenderMethod(self, name):
        """
        @return: a renderer.
        """
        slot, type = name.split(":")

        def renderList(request, tag):
            for item in self.slot_data[slot]:
                yield tag.fillSlots(item=_extra_types(item))
        types = {
            "list": renderList,
        }
        if type in types:
            return types[type]
        else:
            raise MissingRenderMethod(self, name)


class Plating(object):
    """
    A L{Plating} is a container which can be used to generate HTML from data.

    Its name is derived both from tem-I{plating} and I{chrome plating}.
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
                    del json_data[CONTENT]
                    json_data.update(data)
                    return json_serialize(json_data)
                else:
                    data[CONTENT] = loader.load()
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

    def widgeted(self, function):
        """
        
        """
        @wraps(function)
        def wrapper(*a, **k):
            data = function(*a, **k)
            return self._elementify(data)
        wrapper.__name__ += ".widget"
        function.widget = wrapper
        return function
