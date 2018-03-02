# -*- test-case-name: klein.test.test_plating -*-

"""
Templating wrapper support for Klein.
"""

from functools import partial
from json import JSONEncoder
from operator import getitem, setitem
from typing import Any, Tuple, cast

import attr

from six import integer_types, string_types, text_type

from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.interfaces import IPushProducer
from twisted.internet.task import cooperate
from twisted.web.error import MissingRenderMethod
from twisted.web.server import NOT_DONE_YET
from twisted.web.template import Element, TagLoader

from zope.interface import implementer

from ._app import _call
from ._decorators import bindable, modified


# https://github.com/python/mypy/issues/224
ATOM_TYPES = (
    cast(Tuple[Any, ...], integer_types) +
    cast(Tuple[Any, ...], string_types) +
    cast(Tuple[Any, ...], (float, None.__class__))
)

def _should_return_json(request):
    """
    Should the given request result in a JSON entity-body?
    """
    return bool(request.args.get(b"json"))


@inlineCallbacks
def resolveDeferredObjects(root):
    """
    Wait on possibly nested L{Deferred}s that represent a JSON
    serializable object.

    @param root: A JSON-serializable object that may contain
        L{Deferred}s, or a Deferred that will resolve to a
        JSON-serializable object

    @return: A L{Deferred} that fires with a L{Deferred}-free version
        of C{root}, or that fails with the first exception
        encountered.
    """

    result = [None]
    setResult = partial(setitem, result, 0)
    stack = [(root, setResult)]

    while stack:
        mightBeDeferred, setter = stack.pop()
        obj = yield mightBeDeferred
        if isinstance(obj, ATOM_TYPES):
            setter(obj)
        elif isinstance(obj, list):
            parent = [None] * len(obj)
            setter(parent)
            stack.extend(
                reversed([
                    (child, partial(setitem, parent, i))
                    for i, child in enumerate(obj)
                ])
            )
        elif isinstance(obj, tuple):
            parent = [None] * len(obj)
            setter(tuple(parent))

            def setTupleItem(i, value, parent=parent, setter=setter):
                parent[i] = value
                setter(tuple(parent))

            stack.extend(
                reversed([
                    (child, partial(setTupleItem, i))
                    for i, child in enumerate(obj)
                ])
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
            raise TypeError("{input} not JSON serializable"
                            .format(input=obj))

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

        @inlineCallbacks
        def renderList(request, tag):
            data = yield maybeDeferred(getitem, self.slot_data, slot)
            returnValue(
                (tag.fillSlots(item=_extra_types(item)) for item in data)
            )

        types = {
            "list": renderList,
        }
        if type in types:
            return types[type]
        else:
            raise MissingRenderMethod(self, name)


@implementer(IPushProducer)
@attr.s
class ProduceJSON(object):
    """
    A push producer that accepts a JSON-serializable value and
    iteratively encodes it it to a consumer.

    @ivar _value: The value to serialize to JSON.

    @ivar _encoding: The encoding of the serialized JSON.

    @ivar _cooperate: A callable that cooperativel schedules an
        iterator.  See L{cooperate}.

    @see: U{http://as.ynchrono.us/2010/06/asynchronous-json_18.html}
    """

    _value = attr.ib()
    _encoding = attr.ib()
    _cooperate = attr.ib()


    def beginProducing(self, consumer):
        """
        Begin writing encoded JSON to a consumer.

        @return: A L{Deferred} that fires when all JSON has been written.
        """
        self._consumer = consumer
        self._jsonEncodingIterable = JSONEncoder().iterencode(self._value)
        self._task = self._cooperate(self._produce())
        done = self._task.whenDone()
        done.addBoth(self._unregister)
        self._consumer.registerProducer(self, True)
        return done


    def pauseProducing(self):
        """
        Suspend JSON encoding.
        """
        self._task.pause()


    def resumeProducing(self):
        """
        Resume JSON encoding.
        """
        self._task.resume()


    def stopProducing(self):
        """
        Stop JSON encoding.
        """
        self._task.stop()

    def _produce(self):
        """
        Iterate over the JSON encoder's encoding iterable and write
        the encoded results to the consumer.
        """
        for textChunk in self._jsonEncodingIterable:
            binaryChunk = textChunk.encode(self._encoding)
            self._consumer.write(binaryChunk)
            yield None

    def _unregister(self, passthrough):
        """
        Unregister this producer from its consumer.
        """
        self._consumer.unregisterProducer()
        return passthrough



class Plating(object):
    """
    A L{Plating} is a container which can be used to generate HTML from data.

    Its name is derived both from tem-I{plating} and I{chrome plating}.
    """

    CONTENT = "klein:plating:content"

    cooperate = staticmethod(cooperate)


    def __init__(self, defaults=None, tags=None,
                 presentation_slots=()):
        """
        """
        self._defaults = {} if defaults is None else defaults
        self._loader = TagLoader(tags)
        self._presentationSlots = {self.CONTENT} | set(presentation_slots)

    def routed(self, routing, tags):
        """
        """
        encoding = u'utf-8'

        def setContentType(request, text_type):
            request.setHeader(
                b'content-type', (u'text/{format}; charset={encoding}'
                                  .format(format=text_type, encoding=encoding)
                                  .encode("ascii"))
            )

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
                    ready = yield resolveDeferredObjects(json_data)
                    setContentType(request, u'json')
                    producer = ProduceJSON(ready, encoding, self.cooperate)
                    yield producer.beginProducing(request)
                    returnValue(NOT_DONE_YET)
                else:
                    data[self.CONTENT] = loader.load()
                    setContentType(request, u'html')
                    returnValue(self._elementify(instance, data))
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
        _plating = attr.ib()
        _function = attr.ib()
        _instance = attr.ib()

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
