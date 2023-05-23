"""
This file contains code that should validate with type checking if type hints
are correct.
"""

from twisted.internet.defer import succeed
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.template import Element, Tag

from klein import Klein, KleinRenderable


class Application:
    router = Klein()

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
