# -*- test-case-name: klein.test.test_resource -*-

from typing import TYPE_CHECKING, Any, Optional, Sequence, Tuple, Union, cast

from werkzeug.exceptions import HTTPException

from twisted.internet import defer
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web import server
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import IResource, Resource, getChildForRequest
from twisted.web.server import NOT_DONE_YET
from twisted.web.template import renderElement

from ._dihttp import Response
from ._interfaces import IKleinRequest


if TYPE_CHECKING:
    from ._app import ErrorHandlers, Klein, KleinRenderable


def ensure_utf8_bytes(v: Union[str, bytes]) -> bytes:
    """
    Coerces a value which is either a C{str} or C{bytes} to a C{bytes}.
    If ``v`` is a C{str} object it is encoded as utf-8.
    """
    if isinstance(v, str):
        v = v.encode("utf-8")
    return v


class _StandInResource:
    """
    A standin for a Resource.

    This is a sentinel value for L{KleinResource}, to say that we are rendering
    a L{Resource}, which may close the connection itself later.
    """


StandInResource = cast("KleinResource", _StandInResource())


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
    if (bool(request.isSecure()), server_port) not in [
        (True, 443),
        (False, 80),
        (False, 0),
        (True, 0),
    ]:
        server_name = b"%s:%d" % (server_name, server_port)

    script_name = b""
    if request.prepath:
        script_name = b"/".join(request.prepath)

        if not script_name.startswith(b"/"):
            script_name = b"/" + script_name

    path_info = b""
    if request.postpath:
        path_info = b"/".join(request.postpath)

        if not path_info.startswith(b"/"):
            path_info = b"/" + path_info

    url_scheme = "https" if request.isSecure() else "http"

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


class KleinResource(Resource):
    """
    A ``Resource`` that can do URL routing.
    """

    isLeaf = True

    def __init__(self, app: "Klein") -> None:
        Resource.__init__(self)
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

    def render(self, request: IRequest) -> "KleinRenderable":
        # Stuff we need to know for the mapper.
        try:
            (
                url_scheme,
                server_name,
                server_port,
                path_info,
                script_name,
            ) = extractURLparts(request)
        except URLDecodeError as e:
            for what, fail in e.errors:
                log.err(fail, f"Invalid encoding in {what}.")
            request.setResponseCode(400)
            return b"Non-UTF-8 encoding in URL."

        # Bind our mapper.
        mapper = self._app.url_map.bind(
            server_name,
            script_name,
            path_info=path_info,
            default_method=request.method,
            url_scheme=url_scheme,
        )
        # Make the mapper available to the view.
        kleinRequest = IKleinRequest(request)
        kleinRequest.mapper = mapper

        # Make sure we'll notice when the connection goes away unambiguously.
        request_finished = [False]

        def _finish(result: object) -> None:
            request_finished[0] = True

        def _execute() -> Deferred:
            # Actually doing the match right here. This can cause an exception
            # to percolate up. If that happens it will be handled below in
            # processing_failed, either by a user-registered error handler or
            # one of our defaults.
            (rule, kwargs) = mapper.match(return_rule=True)
            endpoint = rule.endpoint

            # Try pretty hard to fix up prepath and postpath.
            segment_count = self._app.endpoints[
                endpoint
            ].segment_count  # type: ignore[union-attr]
            request.prepath.extend(request.postpath[:segment_count])
            request.postpath = request.postpath[segment_count:]

            request.notifyFinish().addBoth(  # type: ignore[attr-defined]
                _finish,
            )

            # Standard Twisted Web stuff. Defer the method action, giving us
            # something renderable or printable. Return NOT_DONE_YET and set up
            # the incremental renderer.
            d = maybeDeferred(
                self._app.execute_endpoint, endpoint, request, **kwargs
            )

            request.notifyFinish().addErrback(  # type: ignore[attr-defined]
                lambda _: d.cancel(),
            )

            return d

        d = maybeDeferred(_execute)

        # typing note: returns Any because Response._applyToRequest returns Any
        def process(r: object) -> Any:
            """
            Recursively go through r and any child Resources until something
            returns an IRenderable, then render it and let the result of that
            bubble back up.
            """
            if isinstance(r, Response):
                r = r._applyToRequest(request)

            if IResource.providedBy(r):
                request.render(  # type: ignore[attr-defined]
                    getChildForRequest(r, request)
                )
                return StandInResource

            if IRenderable.providedBy(r):
                renderElement(request, r)
                return StandInResource

            return r

        d.addCallback(process)

        def processing_failed(
            failure: Failure, error_handlers: "ErrorHandlers"
        ) -> Optional[Deferred]:
            # The failure processor writes to the request.  If the
            # request is already finished we should suppress failure
            # processing.  We don't return failure here because there
            # is no way to surface this failure to the user if the
            # request is finished.
            if request_finished[0]:
                if not failure.check(defer.CancelledError):
                    log.err(failure, "Unhandled Error Processing Request.")
                return None

            # If there are no more registered handlers, apply some defaults
            if len(error_handlers) == 0:
                if failure.check(HTTPException):
                    he = failure.value
                    assert isinstance(he, HTTPException)
                    request.setResponseCode(he.code)
                    resp = he.get_response({})

                    for header, value in resp.headers:
                        request.setHeader(
                            ensure_utf8_bytes(header), ensure_utf8_bytes(value)
                        )

                    return ensure_utf8_bytes(
                        b"".join(
                            resp.iter_encoded(),  # type: ignore[attr-defined]
                        ),
                    )  # type: ignore[attr-defined, return-value]
                else:
                    request.processingFailed(  # type: ignore[attr-defined]
                        failure,
                    )
                    return None

            error_handler = error_handlers[0]

            # Each error handler is a tuple of
            # (list_of_exception_types, handler_fn)
            if failure.check(*error_handler[0]):
                d = maybeDeferred(
                    self._app.execute_error_handler,
                    error_handler[1],
                    request,
                    failure,
                )

                d.addCallback(process)

                return d.addErrback(processing_failed, error_handlers[1:])

            return processing_failed(failure, error_handlers[1:])

        d.addErrback(processing_failed, self._app._error_handlers)

        def write_response(r: object) -> None:
            if r is not StandInResource:
                if isinstance(r, str):
                    r = r.encode("utf-8")

                if (r is not None) and (r != NOT_DONE_YET):
                    request.write(r)

                if not request_finished[0]:
                    request.finish()

        d.addCallback(write_response)
        d.addErrback(log.err, _why="Unhandled Error writing response")

        return server.NOT_DONE_YET  # type: ignore[return-value]
