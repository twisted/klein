"""
Tests for L{klein.plating}.
"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import json
from functools import partial
from string import printable

import attr

from constantly import NamedConstant, Names

from hypothesis import given, settings, strategies as st

from twisted.internet.defer import Deferred, succeed
from twisted.internet.task import Clock, Cooperator, TaskStopped
from twisted.test.proto_helpers import StringTransport
from twisted.trial import unittest
from twisted.web.error import FlattenerError, MissingRenderMethod
from twisted.web.template import slot, tags

from .test_resource import _render, requestMock
from .util import TestCase
from .. import Klein, Plating
from .._plating import (
    ATOM_TYPES,
    PlatedElement,
    ProduceJSON,
    resolveDeferredObjects
)

page = Plating(
    defaults={
        "title": "default title unchanged",
        Plating.CONTENT: "NEVER MIND THE CONTENT",
    },
    tags=tags.html(
        tags.head(tags.title(slot("title"))),
        tags.body(
            tags.h1(slot("title")),
            tags.div(slot(Plating.CONTENT), Class="content"),
        ),
    ),
)

element = Plating(
    defaults={
        "a": "NO VALUE FOR A",
        "b": "NO VALUE FOR B",
    },
    tags=tags.div(
        tags.span("a: ", slot("a")),
        tags.span("b: ", slot("b")),
    ),
)

@element.widgeted
def enwidget(a, b):
    """
    Provide some values for the L{element} template.
    """
    return {"a": a, "b": b}


@element.widgeted
def deferredEnwidget(a, b):
    """
    Provide some L{Deferred} values for the L{element} template.
    """
    return {"a": succeed(a), "b": succeed(b)}


class InstanceWidget(object):
    """
    A class with a method that's a L{Plating.widget}.
    """

    @element.widgeted
    def enwidget(self, a, b):
        """
        Provide some values for the L{element} template.
        """
        return {"a": a, "b": b}

    @element.widgeted
    def deferredEnwidget(self, a, b):
        """
        Provide some L{Deferred} values for the L{element} template.
        """
        return {"a": succeed(a), "b": succeed(b)}


@attr.s
class DeferredValue(object):
    """
    A value within a JSON serializable object that is deferred.

    @param value: The value.

    @param deferred: The L{Deferred} representing the value.
    """
    value = attr.ib()
    deferred = attr.ib(attr.Factory(Deferred))

    def resolve(self):
        """
        Resolve the L{Deferred} that represents the value with the
        value itself.
        """
        self.deferred.callback(self.value)


jsonAtoms = (st.none() |
             st.booleans() |
             st.integers() |
             st.floats(allow_nan=False) |
             st.text(printable))


def jsonComposites(children, withTuples=True):
    """
    Creates a Hypothesis strategy that constructs composite
    JSON-serializable objects (e.g., lists).

    @param children: A strategy from which each composite object's
        children will be drawn.

    @return: The composite objects strategy.
    """
    composites = (st.lists(children) |
                  st.dictionaries(st.text(printable), children))
    if withTuples:
        return composites | st.tuples(children)
    else:
        return composites

jsonObjects = st.recursive(jsonAtoms, jsonComposites, max_leaves=200)
jsonObjectsWithoutTuples = st.recursive(
    jsonAtoms,
    partial(jsonComposites, withTuples=False),
)


def transformJSONObject(jsonObject, transformer):
    """
    Recursively apply a transforming function to a JSON serializable
    object, returning a new, transformed object.

    @param json_object: A JSON serializable object to transform.

    @param transformer: A one-argument callable that will be applied
        to each member of the object.

    @return: A transformed copy of C{jsonObject}.
    """

    def visit(obj):
        """
        Recur through the object, sometimes replacing values with
        L{Deferred}s
        """
        if isinstance(obj, ATOM_TYPES):
            return transformer(obj)
        elif isinstance(obj, tuple):
            return tuple(transformer(child) for child in obj)
        elif isinstance(obj, list):
            return [transformer(child) for child in obj]
        elif isinstance(obj, dict):
            return {transformer(k): transformer(v) for k, v in obj.items()}
        else:
            assert False, "Object of unknown type {!r}".format(obj)

    return visit(jsonObject)


class TransformJSONObjectTests(unittest.SynchronousTestCase):
    """
    Tests for L{transform_json_object}.
    """

    def test_transform_atom(self):
        """
        L{transform_json_object} transforms a representative atomic
        JSON data types.
        """
        def inc(value):
            return value + 1

        self.assertEqual(transformJSONObject(1, inc), 2)

    def test_transform_tuple(self):
        """
        L{transformJSONObject} transforms L{tuple}s.
        """
        def inc(value):
            return value + 1

        self.assertEqual(transformJSONObject((1, 1), inc), (2, 2))

    def test_transform_list(self):
        """
        L{transformJSONObject} transforms L{list}s.
        """
        def inc(value):
            return value + 1

        self.assertEqual(transformJSONObject([1, 1], inc), [2, 2])

    def test_transform_dict(self):
        """
        L{transformJSONObject} transforms L{dict}s.
        """
        def inc(value):
            return value + 1

        self.assertEqual(transformJSONObject({2: 2}, inc), {3: 3})

    def test_transform_unserializable(self):
        """
        L{transformJSONObject} will not transform objects that are
        not JSON serializable.
        """
        self.assertRaises(AssertionError,
                          transformJSONObject,
                          set(), lambda: None)


class ResolveDeferredObjectsTests(unittest.SynchronousTestCase):
    """
    Tests for L{resolve_deferred_objects}.
    """

    @settings(max_examples=500)
    @given(
        jsonObject=jsonObjects,
        data=st.data(),
    )
    def test_resolveObjects(self, jsonObject, data):
        """
        A JSON serializable object that may contain L{Deferred}s or a
        L{Deferred} that resolves to a JSON serializable object
        resolves to an object that contains no L{Deferred}s.
        """
        deferredValues = []
        choose = st.booleans()

        def maybeWrapInDeferred(value):
            if data.draw(choose):
                deferredValues.append(DeferredValue(value))
                return deferredValues[-1].deferred
            else:
                return value

        deferredJSONObject = transformJSONObject(
            jsonObject,
            maybeWrapInDeferred,
        )

        resolved = resolveDeferredObjects(deferredJSONObject)

        for value in deferredValues:
            value.resolve()

        self.assertEqual(self.successResultOf(resolved), jsonObject)


    @given(
        jsonObject=jsonObjects,
        data=st.data(),
    )
    def test_elementSerialized(self, jsonObject, data):
        """
        A L{PlatedElement} within a JSON serializable object replaced
        by its JSON representation.
        """
        choose = st.booleans()

        def injectPlatingElements(value):
            if data.draw(choose) and isinstance(value, dict):
                return PlatedElement(slot_data=value,
                                     preloaded=tags.html(),
                                     boundInstance=None,
                                     presentationSlots={})
            else:
                return value

        withPlatingElements = transformJSONObject(
            jsonObject,
            injectPlatingElements,
        )

        resolved = resolveDeferredObjects(withPlatingElements)

        self.assertEqual(self.successResultOf(resolved), jsonObject)


    def test_unserializableObject(self):
        """
        An object that cannot be serialized causes the L{Deferred} to
        fail with an informative L{TypeError}.

        """
        exception = self.failureResultOf(
            resolveDeferredObjects(frozenset())
        ).value
        self.assertIsInstance(exception, TypeError)
        self.assertIn("frozenset([]) not JSON serializable", str(exception))


class ProduceJSONTests(unittest.SynchronousTestCase):
    """
    Tests for L{ProduceJSON}.
    """

    def setUp(self):
        self.clock = Clock()
        self.interval = 1
        self.cooperate = Cooperator(
            scheduler=partial(self.clock.callLater, self.interval),
        ).cooperate
        self.consumer = StringTransport()

    def writeAllPending(self, maxTicks=16384):
        """
        Schedule all pending producer writes.
        """
        for _ in range(16384):
            self.clock.advance(self.interval)
        self.assertFalse(self.clock.getDelayedCalls())

    @given(jsonObject=jsonObjectsWithoutTuples)
    def test_writeValidJSON(self, jsonObject):
        """
        The producer writes valid JSON to its consumer, stopping and
        unregistering itself on completion.
        """
        self.setUp()
        producer = ProduceJSON(jsonObject, "utf-8", cooperate=self.cooperate)
        done = producer.beginProducing(self.consumer)

        self.writeAllPending()
        self.successResultOf(done)

        written = self.consumer.value()
        self.assertEqual(json.loads(written.decode("utf-8")), jsonObject)
        self.assertIsNone(self.consumer.producer)

    def test_stopOnEncodingFailure(self):
        """
        An encoding failure stops and unregisters the producer.
        """
        unserializable = {"a": [1, 2, set()]}
        producer = ProduceJSON(
            unserializable, "utf-8", cooperate=self.cooperate
        )
        done = producer.beginProducing(self.consumer)

        self.writeAllPending()

        self.assertIsInstance(self.failureResultOf(done).value, TypeError)
        self.assertIsNone(self.consumer.producer)


    def test_pauseProducing(self):
        """
        A paused producer makes no progress but remains registered
        with its consumer.
        """
        producer = ProduceJSON(
            {"some": "data"}, "utf-8", cooperate=self.cooperate
        )
        done = producer.beginProducing(self.consumer)
        producer.pauseProducing()

        self.writeAllPending()

        self.assertFalse(self.consumer.value())
        self.assertNoResult(done)
        self.assertIsNotNone(self.consumer.producer)


    def test_stopProducing(self):
        """
        A stopped producer writes no data and terminates the
        L{Deferred} returned by L{ProduceJSON.beginProducing}.
        """
        producer = ProduceJSON(
            {"some": "data"}, "utf-8", cooperate=self.cooperate
        )
        done = producer.beginProducing(self.consumer)
        producer.stopProducing()

        self.writeAllPending()

        self.assertFalse(self.consumer.value())
        self.assertIs(self.failureResultOf(done).type, TaskStopped)


    class ACTIONS(Names):
        PAUSE = NamedConstant()
        RESUME = NamedConstant()
        WRITE = NamedConstant()

    @given(
        jsonObject=jsonObjectsWithoutTuples,
        actions=st.lists(
            st.sampled_from(list(ACTIONS.iterconstants())),
            min_size=32,
            max_size=128,
        ),
    )
    def test_flowControl(self, jsonObject, actions):
        """
        The consumer can pause and resume the producer to control the
        flow of data.
        """
        self.setUp()
        producer = ProduceJSON(
            jsonObject, "utf-8", cooperate=self.cooperate
        )
        done = producer.beginProducing(self.consumer)

        def isExhausted():
            # The iterator has been exhausted so the producer
            # unregistered itself.
            return self.consumer.producer is None

        paused = False
        for action in actions:
            if isExhausted():
                break
            elif action is self.ACTIONS.PAUSE and not paused:
                paused = True
                producer.pauseProducing()
            elif action is self.ACTIONS.RESUME and paused:
                paused = False
                producer.resumeProducing()
            elif action is self.ACTIONS.WRITE:
                self.clock.advance(self.interval)

        if paused:
            producer.resumeProducing()

        if not isExhausted():
            self.writeAllPending()

        written = self.consumer.value()
        self.assertEqual(json.loads(written.decode("utf-8")), jsonObject)
        self.successResultOf(done)
        self.assertIsNone(self.consumer.producer)


class PlatingTests(TestCase):
    """
    Tests for L{Plating}.
    """

    def setUp(self):
        """
        Create an app and a resource wrapping that app for this test.
        """
        self.app = Klein()
        self.kr = self.app.resource()

        self.clock = Clock()
        self.interval = 1
        self.cooperate = Cooperator(
            scheduler=partial(self.clock.callLater, self.interval),
        ).cooperate
        self.patch(page, "_cooperate", self.cooperate)
        self.patch(element, "_cooperate", self.cooperate)

    def get(self, uri):
        """
        Issue a virtual GET request to the given path that is expected to
        succeed synchronously, and return the generated request object and
        written bytes.
        """
        request = requestMock(uri)
        d = _render(self.kr, request)
        # Sufficient to write at least 16k of JSON.
        self.clock.advance(self.interval * 16384)
        self.successResultOf(d)
        return request, request.getWrittenData()

    def test_template_html(self):
        """
        Rendering a L{Plating.routed} decorated route results in templated
        HTML.
        """
        @page.routed(self.app.route("/"), tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "test-data-present"}

        request, written = self.get(b"/")

        self.assertIn(b'<span>test-data-present</span>', written)
        self.assertIn(b'<title>default title unchanged</title>', written)

    def test_selfhood(self):
        """
        Rendering a L{Plating.routed} decorated route on a method still results
        in the decorated method receiving the appropriate C{self}.
        """
        class AppObj(object):
            app = Klein()

            def __init__(self, x):
                self.x = x

            @page.routed(app.route("/"), tags.span(slot('yeah')))
            def plateInstance(self, request):
                return {"yeah": "test-instance-data-" + self.x}

        obj = AppObj("confirmed")
        self.kr = obj.app.resource()
        request, written = self.get(b"/")

        self.assertIn(b'<span>test-instance-data-confirmed</span>', written)
        self.assertIn(b'<title>default title unchanged</title>', written)

    def test_template_json(self):
        """
        Rendering a L{Plating.routed} decorated route with a query parameter
        asking for JSON will yield JSON instead.
        """
        @page.routed(self.app.route("/"), tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "an-plating-test"}

        request, written = self.get(b"/?json=true")
        self.assertEqual(
            request.responseHeaders.getRawHeaders(b'content-type')[0],
            b'text/json; charset=utf-8'
        )
        self.assertEquals({"ok": "an-plating-test",
                           "title": "default title unchanged"},
                          json.loads(written.decode('utf-8')))


    def test_template_json_contains_deferred(self):
        """
        Rendering a L{Plating.routed} decorated route with a query
        parameter asking for JSON waits until the L{Deferred}s
        returned by the route have fired.
        """
        @page.routed(self.app.route("/"), tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": succeed("an-plating-test")}

        request, written = self.get(b"/?json=true")
        self.assertEqual(
            request.responseHeaders.getRawHeaders(b'content-type')[0],
            b'text/json; charset=utf-8'
        )
        self.assertEquals({"ok": "an-plating-test",
                           "title": "default title unchanged"},
                          json.loads(written.decode('utf-8')))


    def test_template_numbers(self):
        """
        Data returned from a plated method may include numeric types (integers,
        floats, and possibly longs), which although they are not normally
        serializable by twisted.web.template, will be converted by plating into
        their decimal representation.
        """
        @page.routed(
            self.app.route("/"),
            tags.div(
                tags.span(slot("anInteger")),
                tags.i(slot("anFloat")),
                tags.b(slot("anLong")),
            ),
        )
        def plateMe(result):
            return {"anInteger": 7,
                    "anFloat": 3.2,
                    "anLong": 0x10000000000000001}

        request, written = self.get(b"/")

        self.assertIn(b"<span>7</span>", written)
        self.assertIn(b"<i>3.2</i>", written)
        self.assertIn(b"<b>18446744073709551617</b>", written)

    def test_render_list(self):
        """
        The C{:list} renderer suffix will render the slot named by the renderer
        as a list, filling each slot.
        """
        @page.routed(
            self.app.route("/"),
            tags.ul(tags.li(slot("item"), render="subplating:list"))
        )
        def rsrc(request):
            return {"subplating": [1, 2, 3]}

        request, written = self.get(b"/")

        self.assertIn(b'<ul><li>1</li><li>2</li><li>3</li></ul>', written)
        self.assertIn(b'<title>default title unchanged</title>', written)

    def test_widget_function(self):
        """
        A function decorated with L{Plating.wigeted} can be directly
        invoked.
        """
        self.assertEqual(enwidget(5, 6), {"a": 5, "b": 6})
        self.assertEqual(InstanceWidget().enwidget(7, 8), {"a": 7, "b": 8})

    def test_widget_html(self):
        """
        When L{Plating.widgeted} is applied as a decorator, it gives the
        decorated function a C{widget} attribute which is a version of the
        function with a modified return type that turns it into a renderable
        HTML sub-element that may fill a slot.
        """
        @page.routed(self.app.route("/"),
                     tags.div(tags.div(slot("widget")),
                              tags.div(slot("instance-widget"))))
        def rsrc(request):
            return {"widget": enwidget.widget(a=3, b=4),
                    "instance-widget": InstanceWidget().enwidget.widget(5, 6)}

        request, written = self.get(b"/")

        self.assertIn(b"<span>a: 3</span>", written)
        self.assertIn(b"<span>b: 4</span>", written)
        self.assertIn(b"<span>a: 5</span>", written)
        self.assertIn(b"<span>b: 6</span>", written)

    def test_widget_json(self):
        """
        When L{Plating.widgeted} is applied as a decorator, and the result is
        serialized to JSON, it appears the same as the returned value despite
        the HTML-friendly wrapping described above.
        """
        @page.routed(self.app.route("/"),
                     tags.div(tags.div(slot("widget")),
                              tags.div(slot("instance-widget"))))
        def rsrc(request):
            return {"widget": enwidget.widget(a=3, b=4),
                    "instance-widget": InstanceWidget().enwidget.widget(5, 6)}

        request, written = self.get(b"/?json=1")
        self.assertEqual(json.loads(written.decode('utf-8')),
                         {"widget": {"a": 3, "b": 4},
                          "instance-widget": {"a": 5, "b": 6},
                          "title": "default title unchanged"})

    def test_widget_json_deferred(self):
        """
        When L{Plating.widgeted} is applied as a decorator, and the result is
        serialized to JSON, it appears the same as the returned value despite
        the HTML-friendly wrapping described above.
        """

        @page.routed(self.app.route("/"),
                     tags.div(tags.div(slot("widget")),
                              tags.div(slot("instance-widget"))))
        def rsrc(request):
            instance = InstanceWidget()
            return {"widget": deferredEnwidget.widget(a=3, b=4),
                    "instance-widget": instance.deferredEnwidget.widget(5, 6)}

        request, written = self.get(b"/?json=1")
        self.assertEqual(json.loads(written.decode('utf-8')),
                         {"widget": {"a": 3, "b": 4},
                          "instance-widget": {"a": 5, "b": 6},
                          "title": "default title unchanged"})

    def test_prime_directive_return(self):
        """
        Nothing within these Articles Of Federation shall authorize the United
        Federation of Planets to alter the return value of a callable by
        applying a decorator to it...
        """
        exact_result = {"ok": "some nonsense value"}

        @page.routed(self.app.route("/"), tags.span(slot("ok")))
        def plateMe(request):
            return exact_result

        self.assertIdentical(plateMe(None), exact_result)

    def test_prime_directive_arguments(self):
        """
        ... or shall require the function to modify its signature under these
        Articles Of Federation.
        """
        @page.routed(self.app.route("/"), tags.span(slot("ok")))
        def plateMe(request, one, two, three):
            return (one, two, three)

        exact_one = {"one": "and"}
        exact_two = {"two": "and"}
        exact_three = {"three": "and"}
        result_one, result_two, result_three = plateMe(
            None, exact_one, exact_two, three=exact_three
        )

        self.assertIdentical(result_one, exact_one)
        self.assertIdentical(result_two, exact_two)
        self.assertIdentical(result_three, exact_three)

    def test_presentation_only_json(self):
        """
        Slots marked as "presentation only" will not be reflected in the
        output.
        """
        plating = Plating(
            tags=tags.span(slot("title")),
            presentation_slots={"title"}
        )
        plating._cooperate = self.cooperate

        @plating.routed(self.app.route("/"), tags.span(slot("data")))
        def justJson(request):
            return {"title": "uninteresting", "data": "interesting"}

        request, written = self.get(b"/?json=1")

        self.assertEqual(json.loads(written.decode("utf-8")),
                         {"data": "interesting"})

    def test_missing_renderer(self):
        """
        Missing renderers will result in an exception during rendering.
        """
        def test(missing):
            plating = Plating(tags=tags.span(slot(Plating.CONTENT)))

            @plating.routed(
                self.app.route("/"),
                tags.span(tags.span(render=missing))
            )
            def no(request):
                return {}

            self.get(b"/")
            [fe] = self.flushLoggedErrors(FlattenerError)
            self.assertIsInstance(fe.value.args[0], MissingRenderMethod)

        test("garbage")
        test("garbage:missing")
