
from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import json

from klein.plating import Plating
from twisted.web.template import tags, slot

from klein.test.test_resource import requestMock, _render
from klein.test.util import TestCase
from klein import Klein

plating = Plating(
    defaults=dict(
        title="JUST A TITLE",
        content="NEVER MIND THE CONTENT",
    ),
    tags=tags.html(
        tags.head(tags.title(slot("title"))),
        tags.body(
            tags.h1(slot("title")),
            tags.div(slot("content"),
                     Class="content")
        )
    ),
)

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
        @plating.routed(self.app.route("/"),
                        tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "test-data-present"}

        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn(b'<span>test-data-present</span>', written)
        self.assertIn(b'<title>JUST A TITLE</title>', written)

    def test_template_json(self):
        """
        Rendering a L{Plating.routed} decorated route with a query parameter
        asking for JSON will yield JSON instead.
        """
        @plating.routed(self.app.route("/"),
                        tags.span(slot("ok")))
        def plateMe(request):
            return {"ok": "an-plating-test"}

        request = requestMock(b"/?json=true")

        d = _render(self.kr, request)
        self.successResultOf(d)

        written = request.getWrittenData()
        self.assertEquals({"ok": "an-plating-test", "title": "JUST A TITLE"},
                          json.loads(written))

    def test_widget_html(self):
        """
        
        """
        @Plating(tags=tags.ul(tags.li(slot('item'), render="sequence")))
        def widgt(values):
            return {"sequence": values}
        @plating.routed(self.app.route("/"),
                        tags.span(slot("subplating")))
        def rsrc(request):
            return {"subplating": widgt([1, 2, 3, 4])}
        request = requestMock(b"/")
        d = _render(self.kr, request)
        self.successResultOf(d)
        written = request.getWrittenData()
        self.assertIn(b'<ul><li>1</li><li>2</li><li>3</li></ul>', written)
        self.assertIn(b'<title>JUST A TITLE</title>', written)

    def test_widget_json(self):
        """
        
        """
        

    def test_prime_directive_return(self):
        """
        Nothing within these Articles Of Federation shall authorize the United
        Federation of Planets to alter the return value of a callable by
        applying a decorator to it...
        """
        exact_result = {"ok": "some nonsense value"}
        @plating.routed(self.app.route("/"),
                        tags.span(slot("ok")))
        def plateMe(request):
            return exact_result
        self.assertIdentical(plateMe(None), exact_result)

    def test_prime_directive_arguments(self):
        """
        ... or shall require the function to modify its signature under these
        Articles Of Federation.
        """
        @plating.routed(self.app.route("/"),
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

