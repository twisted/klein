# -*- test-case-name: klein.test.test_plating -*-

"""
Templating wrapper support for Klein.
"""

from functools import wraps
from json import dumps

from six import text_type, integer_types

from twisted.internet.defer import inlineCallbacks, returnValue

from twisted.web.template import TagLoader, Element
from twisted.web.error import MissingRenderMethod

from klein.app import _call

def _should_return_json(request):
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get(b"json"))


def json_serialize(item):
    """
    A function similar to L{dumps}.
    """
    def helper(unknown):
        if isinstance(unknown, PlatedElement):
            return unknown.slot_data
        else:
            raise TypeError("{input} not JSON serializable"
                            .format(input=unknown))
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

    def __init__(self, slot_data, preloaded, renderers, bound_instance):
        """
        @param slot_data: A dictionary mapping names to values.

        @param preloaded: The pre-loaded data.
        """
        self.slot_data = slot_data
        self._renderers = renderers
        self._bound_instance = bound_instance
        super(PlatedElement, self).__init__(
            loader=TagLoader(preloaded.fillSlots(
                **{k: _extra_types(v) for k, v in slot_data.items()}
            ))
        )

    def lookupRenderMethod(self, name):
        """
        @return: a renderer.
        """
        print("renderers?", self._renderers)
        if name in self._renderers:
            wrapped = self._renderers[name]
            @wraps(wrapped)
            def renderWrapper(request, tag, *args, **kw):
                return _call(self._bound_instance, wrapped,
                             request, tag, *args, **kw)
            renderWrapper.__klein_bound__ = True
            return renderWrapper
        if ":" not in name:
            raise MissingRenderMethod(self, name)
        slot, type = name.split(":", 1)

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

    CONTENT = "klein:plating:content"

    def __init__(self, defaults=None, tags=None,
                 presentation_slots=frozenset()):
        """
        
        """
        self._defaults = {} if defaults is None else defaults
        self._loader = TagLoader(tags)
        self._presentation_slots = {self.CONTENT} | set(presentation_slots)
        self._renderers = {}

    def render(self, renderer):
        """
        
        """
        self._renderers[text_type(renderer.__name__)] = renderer
        return renderer

    def routed(self, routing, content_template):
        """
        
        """
        def mydecorator(method):
            loader = TagLoader(content_template)
            @inlineCallbacks
            def mymethod(instance, request, *args, **kw):
                data = yield _call(instance, method, request, *args, **kw)
                if _should_return_json(request):
                    json_data = self._defaults.copy()
                    json_data.update(data)
                    for ignored in self._presentation_slots:
                        json_data.pop(ignored, None)
                    request.setHeader(b'content-type',
                                      b'text/json; charset=utf-8')
                    returnValue(json_serialize(json_data))
                else:
                    request.setHeader(b'content-type',
                                      b'text/html; charset=utf-8')
                    data[self.CONTENT] = loader.load()
                    returnValue(self._elementify(instance, data))
            mymethod.__name__ = "plating renderer for " + method.__name__
            routing(mymethod)
            method.__dict__.update(mymethod.__dict__)
            mymethod.__klein_bound__ = True
            return method
        return mydecorator

    def _elementify(self, instance, to_fill_with):
        """
        
        """
        slot_data = self._defaults.copy()
        slot_data.update(to_fill_with)
        [loaded] = self._loader.load()
        loaded = loaded.clone()
        return PlatedElement(slot_data=slot_data,
                             preloaded=loaded,
                             renderers=self._renderers,
                             bound_instance=instance)

    def widgeted(self, function):
        """
        
        """
        @wraps(function)
        def wrapper(instance, *a, **k):
            data = _call(instance, function, *a, **k)
            return self._elementify(instance, data)
        wrapper.__name__ += ".widget"
        wrapper.__klein_bound__ = True
        function.widget = wrapper
        return function
