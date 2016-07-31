"""
Tests for L{klein.plating}.
"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import json

from klein.plating import Plating, CONTENT
from twisted.web.template import tags, slot

from klein.test.test_resource import requestMock, _render
from klein.test.util import TestCase
from klein import Klein

page = Plating(
    defaults={
        "title": "default title unchanged",
        CONTENT: "NEVER MIND THE CONTENT",
    },
    tags=tags.html(
        tags.head(tags.title(slot("title"))),
        tags.body(
            tags.h1(slot("title")),
            tags.div(slot(CONTENT),
                     Class="content")
        )
    ),
)

element = Plating(
    defaults={
        "a": "NO VALUE FOR A",
        "b": "NO VALUE FOR B",
    },
    tags=tags.div(tags.span("a: ", slot("a")),
                  tags.span("b: ", slot("b"))),
)

@element.widgeted
def enwidget(a, b):
    """
    Provide some values for the L{widget} template.
    """
    return {"a": a, "b": b}


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

    def test_template_html(self):
        """
        Rendering a L{Plating.routed} decorated route results in templated
        HTML.
        """
        @page.routed(self.app.route("/"),
                     tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "test-data-present"}

        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn(b'<span>test-data-present</span>', written)
        self.assertIn(b'<title>default title unchanged</title>', written)

    def test_template_json(self):
        """
        Rendering a L{Plating.routed} decorated route with a query parameter
        asking for JSON will yield JSON instead.
        """
        @page.routed(self.app.route("/"),
                     tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "an-plating-test"}

        request = requestMock(b"/?json=true")

        d = _render(self.kr, request)
        self.successResultOf(d)

        written = request.getWrittenData()
        self.assertEquals({"ok": "an-plating-test",
                           "title": "default title unchanged"},
                          json.loads(written))

    def test_template_numbers(self):
        """
        Data returned from a plated method may include numeric types (integers,
        floats, and possibly longs), which although they are not normally
        serializable by twisted.web.template, will be converted by plating into
        their decimal representation.
        """
        @page.routed(self.app.route("/"),
                     tags.div(tags.span(slot("anInteger")),
                              tags.i(slot("anFloat")),
                              tags.b(slot("anLong")),
                     ))
        def plateMe(result):
            return {"anInteger": 7,
                    "anFloat": 3.2,
                    "anLong": 0x10000000000000001}
        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn("<span>7</span>", written)
        self.assertIn("<i>3.2</i>", written)
        self.assertIn("<b>18446744073709551617</b>", written)

    def test_render_list(self):
        """
        The C{:list} renderer suffix will render the slot named by the renderer
        as a list, filling each slot.
        """
        @page.routed(self.app.route("/"),
                     tags.ul(tags.li(slot("item"),
                                     render="subplating:list")))
        def rsrc(request):
            return {"subplating": [1, 2, 3]}
        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn(b'<ul><li>1</li><li>2</li><li>3</li></ul>', written)
        self.assertIn(b'<title>default title unchanged</title>', written)

    def test_widget_html(self):
        """
        When L{Plating.widgeted} is applied as a decorator, it gives the
        decorated function a C{widget} attribute which is a version of the
        function with a modified return type that turns it into a renderable
        HTML sub-element that may fill a slot.
        """
        @page.routed(self.app.route("/"),
                     tags.div(slot("widget")))
        def rsrc(request):
            return {"widget": enwidget.widget(3, 4)}
        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn(b"<span>a: 3</span>", written)
        self.assertIn(b"<span>b: 4</span>", written)

    def test_widget_json(self):
        """
        When L{Plating.widgeted} is applied as a decorator, and the result is
        serialized to JSON, it appears the same as the returned value despite
        the HTML-friendly wrapping described above.
        """
        @page.routed(self.app.route("/"),
                     tags.div(slot("widget")))
        def rsrc(request):
            return {"widget": enwidget.widget(3, 4)}
        request = requestMock(b"/?json=1")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertEqual(json.loads(written),
                         {"widget": {"a": 3, "b": 4},
                          "title": "default title unchanged"})

    def test_prime_directive_return(self):
        """
        Nothing within these Articles Of Federation shall authorize the United
        Federation of Planets to alter the return value of a callable by
        applying a decorator to it...
        """
        exact_result = {"ok": "some nonsense value"}
        @page.routed(self.app.route("/"),
                     tags.span(slot("ok")))
        def plateMe(request):
            return exact_result
        self.assertIdentical(plateMe(None), exact_result)

    def test_prime_directive_arguments(self):
        """
        ... or shall require the function to modify its signature under these
        Articles Of Federation.
        """
        @page.routed(self.app.route("/"),
                     tags.span(slot("ok")))
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

