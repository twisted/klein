# -*- test-case-name: klein.test.test_plating -*-

"""
Templating wrapper support for Klein.
"""

from json import dumps

from six import integer_types, text_type

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.error import MissingRenderMethod
from twisted.web.template import Element, TagLoader

from ._decorators import bindable, modified
from .app import _call


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
            return unknown._asJSON()
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

    def __init__(self, slot_data, preloaded, boundInstance, presentationSlots):
        """
        @param slot_data: A dictionary mapping names to values.

        @param preloaded: The pre-loaded data.
        """
        self.slot_data = slot_data
        self._boundInstance = boundInstance
        self._presentationSlots = presentationSlots
        super(PlatedElement, self).__init__(
            loader=TagLoader(preloaded.fillSlots(
                **{k: _extra_types(v) for k, v in slot_data.items()}
            ))
        )


    def _asJSON(self):
        """
        Render this L{PlatedElement} as JSON-serializable data.
        """
        json_data = self.slot_data.copy()
        for ignored in self._presentationSlots:
            json_data.pop(ignored, None)
        return json_data


    def lookupRenderMethod(self, name):
        """
        @return: a renderer.
        """
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
        self._presentationSlots = {self.CONTENT} | set(presentation_slots)

    def routed(self, routing, tags):
        """
        """
        def mydecorator(method):
            loader = TagLoader(tags)

            @modified("plating route renderer", method, routing)
            @bindable
            @inlineCallbacks
            def mymethod(instance, request, *args, **kw):
                data = yield _call(instance, method, request, *args, **kw)
                if _should_return_json(request):
                    json_data = self._defaults.copy()
                    json_data.update(data)
                    for ignored in self._presentationSlots:
                        json_data.pop(ignored, None)
                    text_type = u'json'
                    result = json_serialize(json_data)
                else:
                    data[self.CONTENT] = loader.load()
                    text_type = u'html'
                    result = self._elementify(instance, data)
                request.setHeader(
                    b'content-type', (u'text/{format}; charset=utf-8'
                                      .format(format=text_type)
                                      .encode("charmap"))
                )
                returnValue(result)
            return method
        return mydecorator


    def _elementify(self, instance, to_fill_with):
        """
        Convert this L{Plating} into a L{PlatedElement}.
        """
        slot_data = self._defaults.copy()
        slot_data.update(to_fill_with)
        [loaded] = self._loader.load()
        loaded = loaded.clone()
        return PlatedElement(slot_data=slot_data,
                             preloaded=loaded,
                             boundInstance=instance,
                             presentationSlots=self._presentationSlots)

    def widgeted(self, function):
        @modified("Plating.widget renderer", function)
        @bindable
        def wrapper(instance, *a, **k):
            data = _call(instance, function, *a, **k)
            return self._elementify(instance, data)
        function.widget = wrapper
        return function
