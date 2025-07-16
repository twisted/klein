# -*- test-case-name: klein.test.test_resource -*-
"""
Implementation of Klein L{Resource}-rendering behavior.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Tuple, Union

from werkzeug.exceptions import HTTPException
from werkzeug.wrappers.response import Response as WerkResponse

from twisted.internet.defer import CancelledError, Deferred, maybeDeferred
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web import server
from twisted.web.http import BAD_REQUEST, NOT_FOUND
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import IResource, Resource, getChildForRequest
from twisted.web.server import Request
from twisted.web.template import renderElement


if TYPE_CHECKING:
    from ._app import KleinRenderable, ErrorMethods

from ._dihttp import Response
from ._interfaces import IKleinRequest


if TYPE_CHECKING:
    # NB: circular import, must not be imported at runtime.
    from ._app import (
        Klein,
        KleinRouteHandler,
        RouteMetadata,
    )


def route_metadata(handler: KleinRouteHandler) -> RouteMetadata:
    return handler  # type:ignore[return-value]


def ensure_utf8_bytes(v: Union[str, bytes]) -> bytes:
    """
    Coerces a value which is either a C{str} or C{bytes} to a C{bytes}.
    If ``v`` is a C{str} object it is encoded as utf-8.
    """
    if isinstance(v, str):
        v = v.encode("utf-8")
    return v


class URLDecodeError(Exception):
    """
    Raised if one or more string parts of the URL could not be decoded.
    """

    __slots__ = ["errors"]

    def __init__(self, errors: Sequence[Tuple[str, Failure]]) -> None:
        """
        @param errors: Sequence of decoding errors, expressed as tuples
            of names and an associated failure.
        """
        self.errors = errors

    def __repr__(self) -> str:
        return f"<URLDecodeError(errors={self.errors!r})>"


def extractURLparts(request: IRequest) -> Tuple[str, str, int, str, str]:
    """
    Extracts and decodes URI parts from C{request}.

    All strings must be UTF8-decodable.

    @param request: A Twisted Web request.

    @raise URLDecodeError: If one of the parts could not be decoded as UTF-8.

    @return: L{tuple} of the URL scheme, the server name, the server port, the
        path info and the script name.
    """
    server_name = request.getRequestHostname()
    if hasattr(request.getHost(), "port"):
        server_port = request.getHost().port
    else:
        server_port = 0
    is_secure = bool(request.isSecure())
    if (is_secure, server_port) not in [
        (True, 443),
        (False, 80),
    ] or server_port == 0:
        server_name = b"%s:%d" % (server_name, server_port)

    script_name = b""
    if request.prepath:
        script_name = b"/".join(request.prepath)

        # TODO: coverage
        if not script_name.startswith(b"/"):  # pragma: no branch
            script_name = b"/" + script_name

    path_info = b""
    # TODO: coverage
    if request.postpath:  # pragma: no branch
        path_info = b"/".join(request.postpath)

        # TODO: coverage
        if not path_info.startswith(b"/"):  # pragma: no branch
            path_info = b"/" + path_info

    url_scheme = "https" if is_secure else "http"

    utf8Failures = []
    try:
        server_name = server_name.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("SERVER_NAME", Failure()))
    try:
        path_text = path_info.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("PATH_INFO", Failure()))
    try:
        script_text = script_name.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("SCRIPT_NAME", Failure()))

    if utf8Failures:
        raise URLDecodeError(utf8Failures)

    return url_scheme, server_name, server_port, path_text, script_text


def _werkzeugHandler(
    self: object, request: IRequest, failure: Failure
) -> bytes:
    """
    This is the fallback response handler for Werkzeug exceptions, invoked when
    no application-level handler is registered with
    L{klein.Klein.handle_errors} for those exceptions, to relay Werkzeug's
    internal error code and response content.
    """
    he: HTTPException = failure.value  # type:ignore[assignment]
    request.setResponseCode(he.code if he.code is not None else 500)

    # we need to call iter_encoded later so we need to include an explicit
    # workaround for https://github.com/pallets/werkzeug/issues/3056
    resp: WerkResponse = he.get_response({})  # type:ignore[assignment]

    for header, value in resp.headers:
        request.setHeader(ensure_utf8_bytes(header), ensure_utf8_bytes(value))

    encoded = resp.iter_encoded()
    return ensure_utf8_bytes(b"".join(encoded))


def _isWritable(request: Request) -> bool:
    """
    Is the given request still writable?
    """
    return (getattr(request, "channel", None) is not None) and (
        not request.finished
    )


def _unknownHandler(request: Request, failure: Failure) -> None:
    """
    This is the fallback error handler for arbitrary exception types, invoked
    when a route handler raises an exception (not from Werkzeug, see
    L{_werkzeugHandler} for those) and there is no handler registered.

    It delegates to L{Request.processingFailed}.
    """
    if not failure.check(CancelledError):
        log.err(failure, "while processing route")
    if _isWritable(request):
        request.processingFailed(failure)


def applyResponse(
    request: Request, response: KleinRenderable | Response
) -> None:
    """
    Apply a response, or L{KleinRenderable}, to a request, setting its response
    code and content, and finishing the request if necessary.

    @note: C{response} is in fact a L{KleinSynchronousRenderable}, but it's not
        possible to represent it as such here, because of a bunch of type
        complexity around L{maybeDeferred}, L{Awaitable}, and methods on
        L{Deferred} itself.  In brief, you can't actually have a
        C{Deferred[Awaitable[...]]} but the type system cannot know that.
    """
    # NB: many of the 'if' statements below fall through quite intentionally,
    # so although this appears to be a slam dunk for a match statement, it is
    # very much not.

    if isinstance(response, Response):
        # If it's a Response object, we apply some headers, then revert to
        # previous case.
        response = response._applyToRequest(request)

    if response is None:
        # If the response is None, that's a no-content 404.
        request.setResponseCode(NOT_FOUND)
        response = b""

    if isinstance(response, str):
        # If it's a string, encode it.
        response = response.encode("utf-8")

    if isinstance(response, bytes):
        # If it's bytes, write it to the response and finish the response.
        if _isWritable(request):
            request.write(response)
            request.finish()
        return

    if IResource.providedBy(response):
        # Resource.render return-value handling / calling .finish()
        # appropriately is built in to Request.render. Delegate to it, and
        # we're done.
        ultimateResource = getChildForRequest(response, request)
        request.render(ultimateResource)
        return

    if IRenderable.providedBy(response):
        # renderElement generates a Deferred internally, and calls finish();
        # we're done.
        renderElement(request, response)
        return


async def respondTo(app: Klein, request: Request) -> None:
    """
    Respond to the given twisted.web request by looking up and executing the
    given Klein route and rendering any errors.
    """
    try:
        try:
            (url_scheme, server_name, server_port, path_info, script_name) = (
                extractURLparts(request)
            )
        except URLDecodeError as e:
            for what, fail in e.errors:
                log.err(fail, f"Invalid encoding in {what}.")
            request.setResponseCode(BAD_REQUEST)
            request.write(b"Non-UTF-8 encoding in URL.")
            request.finish()
            return

        # Bind our mapper to the information from the request.
        mapper = app.url_map.bind(
            server_name,
            script_name,
            path_info=path_info,
            default_method=request.method.decode("utf-8"),
            url_scheme=url_scheme,
        )
        # Make the bound mapper available to the view.
        kleinRequest = IKleinRequest(request)
        kleinRequest.mapper = mapper

        # Actually doing the match right here. This can cause an
        # exception to percolate up. If that happens it will be handled
        # below in processing_failed, either by a user-registered error
        # handler or one of our defaults.
        (rule, kwargs) = mapper.match(return_rule=True)
        endpoint = rule.endpoint

        # Try pretty hard to fix up prepath and postpath.
        segment_count = route_metadata(app.endpoints[endpoint]).segment_count

        assert request.prepath is not None
        assert request.postpath is not None
        request.prepath.extend(request.postpath[:segment_count])
        request.postpath = request.postpath[segment_count:]

        response = await maybeDeferred(
            app.execute_endpoint, endpoint, request, **kwargs
        )
        applyResponse(request, response)
    except Exception:
        failure = Failure()
        handlers: ErrorMethods = app._error_handlers + [
            ([HTTPException], _werkzeugHandler)
        ]
        for excTypes, handler in handlers:
            if not failure.check(*excTypes):
                continue
            response = await maybeDeferred(
                app.execute_error_handler, handler, request, failure
            )
            applyResponse(request, response)
            return

        _unknownHandler(request, failure)


class KleinResource(Resource):
    """
    A ``Resource`` that can do URL routing.
    """

    isLeaf = True

    def __init__(self, app: Klein) -> None:
        super().__init__()
        self._app = app

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KleinResource):
            return vars(self) == vars(other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def render(self, request: Request) -> int:
        """
        Render the response to the given request based on the underlying
        L{Klein} application.
        """
        # Respond to the request.
        responseCoroutine = respondTo(self._app, request)

        # Kick off the coroutine which will respond to the request.
        inProgress = Deferred.fromCoroutine(responseCoroutine)

        # Hook up app-logic cancellation to when the request is terminated.
        request.notifyFinish().addErrback(lambda _: inProgress.cancel())

        # We will call .write() and .finish() on the request when necessary -
        # see applyResponse - so always be async here.
        return server.NOT_DONE_YET
