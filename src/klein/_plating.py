# -*- test-case-name: klein.test.test_plating -*-

"""
Templating wrapper support for Klein.
"""

from functools import partial
from json import dumps
from operator import setitem
from typing import Any, Callable, TYPE_CHECKING, Tuple, cast

import attr

from six import integer_types, string_types, text_type

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.error import MissingRenderMethod
from twisted.web.template import Element, TagLoader

from ._app import _call
from ._decorators import bindable, modified, originalName

if TYPE_CHECKING:  # pragma: no cover
    from twisted.internet.defer import Deferred
    from twisted.web.iweb import IRequest
    from twisted.web.template import Tag
    from typing import List

    Deferred, IRequest, Tag
    StackType = List[Tuple[Any, Callable[[Any], None]]]

# https://github.com/python/mypy/issues/224
ATOM_TYPES = (
    cast(Tuple[Any, ...], integer_types)
    + cast(Tuple[Any, ...], string_types)
    + cast(Tuple[Any, ...], (float, None.__class__))
)


def _should_return_json(request):
    # type: (IRequest) -> bool
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get(b"json"))


@inlineCallbacks
def resolveDeferredObjects(root):
    # type: (Any) -> Deferred
    """
    Wait on possibly nested L{Deferred}s that represent a JSON
    serializable object.

    @param root: JSON-serializable object that may contain
        L{Deferred}s that resolve to JSON-serializable objects, or a
        L{Deferred} that resolves to one.

    @return: A L{Deferred} that fires with a L{Deferred}-free version
        of C{root}, or that fails with the first exception
        encountered.
    """

    result = [None]
    setResult = partial(setitem, result, 0)
    stack = [(root, setResult)]  # type: StackType

    while stack:
        mightBeDeferred, setter = stack.pop()
        # inlineCallbacks pauses the generator only on yielded
        # Deferreds. It's resumed immediately with any other object.
        # Consequently coroutines must be wrapped in ensureDeferred.
        obj = yield mightBeDeferred
        if isinstance(obj, ATOM_TYPES):
            setter(obj)
        elif isinstance(obj, list):
            parent = [None] * len(obj)  # type: Any
            setter(parent)
            stack.extend(
                reversed(
                    [
                        (child, partial(setitem, parent, i))
                        for i, child in enumerate(obj)
                    ]
                )
            )
        elif isinstance(obj, tuple):
            parent = [None] * len(obj)
            setter(tuple(parent))

            def setTupleItem(i, value, parent=parent, setter=setter):
                parent[i] = value
                setter(tuple(parent))

            stack.extend(
                reversed(
                    [
                        (child, partial(setTupleItem, i))
                        for i, child in enumerate(obj)
                    ]
                )
            )
        elif isinstance(obj, dict):
            parent = {}
            setter(parent)
            for key, value in reversed(list(obj.items())):
                pair = [None, None]
                setKey = partial(setitem, pair, 0)

                def setValue(value, pair=pair, parent=parent):
                    pair[1] = value
                    parent.update([pair])

                stack.append((value, setValue))
                stack.append((key, setKey))
        elif isinstance(obj, PlatedElement):
            stack.append((obj._asJSON(), setter))
        else:
            raise TypeError(
                obj, "{input} not JSON serializable".format(input=obj),
            )

    returnValue(result[0])


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

    def __init__(
        self, slot_data, preloaded, boundInstance, presentationSlots, renderers
    ):
        """
        @param slot_data: A dictionary mapping names to values.

        @param preloaded: The pre-loaded data.
        """
        self.slot_data = slot_data
        self._boundInstance = boundInstance
        self._presentationSlots = presentationSlots
        self._renderers = renderers
        super(PlatedElement, self).__init__(
            loader=TagLoader(
                preloaded.fillSlots(
                    **{k: _extra_types(v) for k, v in slot_data.items()}
                )
            )
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
        if name in self._renderers:
            wrapped = self._renderers[name]

            @modified("plated render wrapper", wrapped)
            def renderWrapper(request, tag, *args, **kw):
                # type: (IRequest, Tag, *Any, **Any) -> Any
                return _call(
                    self._boundInstance, wrapped, request, tag, *args, **kw
                )

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

    def __init__(self, defaults=None, tags=None, presentation_slots=()):
        """
        """
        self._defaults = {} if defaults is None else defaults
        self._loader = TagLoader(tags)
        self._presentationSlots = {self.CONTENT} | set(presentation_slots)
        self._renderers = {}

    def renderMethod(self, renderer):
        """
        Add a render method to this L{Plating} object that can be used in the
        top-level template.

        The name of the renderer to use within the template is the name of the
        decorated function.
        """
        self._renderers[text_type(originalName(renderer))] = renderer
        return renderer

    def routed(self, routing, tags):
        """
        """

        def mydecorator(method):
            loader = TagLoader(tags)

            @modified("plating route renderer", method, routing)
            @bindable
            @inlineCallbacks
            def mymethod(instance, request, *args, **kw):
                # type: (Any, IRequest, *Any, **Any) -> Any
                data = yield _call(instance, method, request, *args, **kw)
                if _should_return_json(request):
                    json_data = self._defaults.copy()
                    json_data.update(data)
                    for ignored in self._presentationSlots:
                        json_data.pop(ignored, None)
                    text_type = u"json"
                    ready = yield resolveDeferredObjects(json_data)
                    result = dumps(ready)
                else:
                    data[self.CONTENT] = loader.load()
                    text_type = u"html"
                    result = self._elementify(instance, data)
                request.setHeader(
                    b"content-type",
                    (
                        u"text/{format}; charset=utf-8".format(
                            format=text_type
                        ).encode("charmap")
                    ),
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
        return PlatedElement(
            slot_data=slot_data,
            preloaded=loaded,
            renderers=self._renderers,
            boundInstance=instance,
            presentationSlots=self._presentationSlots,
        )

    @attr.s
    class _Widget(object):
        """
        Implementation of L{Plating.widgeted}.  This is a L{callable}
        descriptor that records the instance to which its wrapped
        function is bound, if any.  Its L{widget} method then passes
        that instance or L{None} and the result of invoking the
        function (or now bound method) to the creating L{Plating}
        instance's L{Plating._elementify} to construct a
        L{PlatedElement}.
        """

        _plating = attr.ib(type="Plating")
        _function = attr.ib(type=Callable[..., Any])
        _instance = attr.ib(type=object)

        def __call__(self, *args, **kwargs):
            return self._function(*args, **kwargs)

        def __get__(self, instance, owner=None):
            return self.__class__(
                self._plating,
                self._function.__get__(instance, owner),
                instance=instance,
            )

        def widget(self, *args, **kwargs):
            """
            Construct a L{PlatedElement} the rendering of this widget.
            """
            data = self._function(*args, **kwargs)
            return self._plating._elementify(self._instance, data)

        def __getattr__(self, attr):
            return getattr(self._function, attr)

    def widgeted(self, function):
        """
        A decorator that turns a function into a renderer for an
        element without a L{Klein.route}.  Use this to create reusable
        template elements.
        """
        return self._Widget(self, function, None)
