"""
This file contains code that should validate with type checking if type hints
are correct.

The code is not executed. Instead, the code should simply validate when checked
with mypy, or fail and require a `type: ignore` comment.

Because those comments produce an error if mypy thinks they are unnecessary,
they service to confirm that code that should fail to verify does so.
"""

from twisted.internet.defer import succeed
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.template import Element, Tag

from klein import Klein, KleinRenderable


class Application:
    router = Klein()

    # Ensure that various return object types for a route are valid.

    @router.route("/object")
    def returnsObject(self, request: IRequest) -> KleinRenderable:
        return object()  # type: ignore[return-value]

    @router.route("/str")
    def returnsStr(self, request: IRequest) -> KleinRenderable:
        return ""

    @router.route("/bytes")
    def returnsBytes(self, request: IRequest) -> KleinRenderable:
        return b""

    @router.route("/iresource")
    def returnsIResource(self, request: IRequest) -> KleinRenderable:
        return Resource()

    @router.route("/irenderable")
    def returnsIRenderable(self, request: IRequest) -> KleinRenderable:
        return Element()

    @router.route("/tag")
    def returnsTag(self, request: IRequest) -> KleinRenderable:
        return Tag("")

    @router.route("/none")
    def returnsNone(self, request: IRequest) -> KleinRenderable:
        return None

    # Ensure that same return object types for a route are valid when wrapped
    # in a Deferred object.

    @router.route("/deferred-object")
    def returnsDeferredObject(self, request: IRequest) -> KleinRenderable:
        return succeed(object())  # type: ignore[arg-type]

    @router.route("/deferred-str")
    def returnsDeferredStr(self, request: IRequest) -> KleinRenderable:
        return succeed("")

    @router.route("/deferred-bytes")
    def returnsDeferredBytes(self, request: IRequest) -> KleinRenderable:
        return succeed(b"")

    @router.route("/deferred-iresource")
    def returnsDeferredIResource(self, request: IRequest) -> KleinRenderable:
        return succeed(Resource())

    @router.route("/deferred-irenderable")
    def returnsDeferredIRenderable(self, request: IRequest) -> KleinRenderable:
        return succeed(Element())

    @router.route("/deferred-tag")
    def returnsDeferredTag(self, request: IRequest) -> KleinRenderable:
        return succeed(Tag(""))

    @router.route("/deferred-none")
    def returnsDeferredNone(self, request: IRequest) -> KleinRenderable:
        return succeed(None)

    # Ensure that same return object types for a route are valid in async
    # methods.

    @router.route("/async-object")
    async def asyncReturnsObject(self, request: IRequest) -> KleinRenderable:
        return object()  # type: ignore[arg-type]

    @router.route("/async-str")
    async def asyncReturnsStr(self, request: IRequest) -> KleinRenderable:
        return ""

    @router.route("/async-bytes")
    async def asyncReturnsBytes(self, request: IRequest) -> KleinRenderable:
        return b""

    @router.route("/async-iresource")
    async def asyncReturnsIResource(self, request: IRequest) -> KleinRenderable:
        return Resource()

    @router.route("/async-irenderable")
    async def asyncReturnsIRenderable(
        self, request: IRequest
    ) -> KleinRenderable:
        return Element()

    @router.route("/async-tag")
    async def asyncReturnsTag(self, request: IRequest) -> KleinRenderable:
        return Tag("")

    @router.route("/async-none")
    async def asyncReturnsNone(self, request: IRequest) -> KleinRenderable:
        return None
