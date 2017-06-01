# -*- test-case-name: klein.test.test_resource -*-

from __future__ import absolute_import, division

from twisted.internet import defer
from twisted.python import failure, log
from twisted.python.compat import intToBytes, unicode
from twisted.web import server
from twisted.web.iweb import IRenderable
from twisted.web.resource import IResource, Resource, getChildForRequest
from twisted.web.server import NOT_DONE_YET
from twisted.web.template import renderElement

from werkzeug.exceptions import HTTPException

from klein.interfaces import IKleinRequest



__all__ = (
    "KleinResource",
    "ensure_utf8_bytes",
)



def ensure_utf8_bytes(v):
    """
    Coerces a value which is either a C{unicode} or C{str} to a C{str}.
    If ``v`` is a C{unicode} object it is encoded as utf-8.
    """
    if isinstance(v, unicode):
        v = v.encode("utf-8")
    return v



class _StandInResource(object):
    """
    A standin for a Resource.

    This is a sentinel value for L{KleinResource}, to say that we are rendering
    a L{Resource}, which may close the connection itself later.
    """



class _URLDecodeError(Exception):
    """
    Raised if one or more string parts of the URL could not be decoded.
    """
    __slots__ = ["errors"]

    def __init__(self, errors):
        """
        @param errors: List of decoding errors.
        @type errors: L{list} of L{tuple} of L{str},
            L{twisted.python.failure.Failure}
        """
        self.errors = errors

    def __repr__(self):
        return "<URLDecodeError(errors={0!r})>".format(self.errors)



def _extractURLparts(request):
    """
    Extracts and decodes URI parts from C{request}.

    All strings must be UTF8-decodable.

    @param request: A Twisted Web request.
    @type request: L{twisted.web.iweb.IRequest}

    @raise URLDecodeError: If one of the parts could not be decoded as UTF-8.

    @return: L{tuple} of the URL scheme, the server name, the server port, the
        path info and the script name.
    @rtype: L{tuple} of L{unicode}, L{unicode}, L{int}, L{unicode}, L{unicode}
    """
    server_name = request.getRequestHostname()
    if hasattr(request.getHost(), 'port'):
        server_port = request.getHost().port
    else:
        server_port = 0
    if (bool(request.isSecure()), server_port) not in [
            (True, 443), (False, 80), (False, 0), (True, 0)]:
        server_name = server_name + b":" + intToBytes(server_port)

    script_name = b''
    if request.prepath:
        script_name = b'/'.join(request.prepath)

        if not script_name.startswith(b'/'):
            script_name = b'/' + script_name

    path_info = b''
    if request.postpath:
        path_info = b'/'.join(request.postpath)

        if not path_info.startswith(b'/'):
            path_info = b'/' + path_info

    url_scheme = u'https' if request.isSecure() else u'http'

    utf8Failures = []
    try:
        server_name = server_name.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("SERVER_NAME", failure.Failure()))
    try:
        path_info = path_info.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("PATH_INFO", failure.Failure()))
    try:
        script_name = script_name.decode("utf-8")
    except UnicodeDecodeError:
        utf8Failures.append(("SCRIPT_NAME", failure.Failure()))

    if utf8Failures:
        raise _URLDecodeError(utf8Failures)

    return url_scheme, server_name, server_port, path_info, script_name



class KleinResource(Resource):
    """
    A ``Resource`` that can do URL routing.
    """
    isLeaf = True


    def __init__(self, app):
        Resource.__init__(self)
        self._app = app


    def __eq__(self, other):
        if isinstance(other, KleinResource):
            return vars(self) == vars(other)
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def render(self, request):
        # Stuff we need to know for the mapper.
        try:
            url_scheme, server_name, server_port, path_info, script_name = (
                _extractURLparts(request)
            )
        except _URLDecodeError as e:
            for what, fail in e.errors:
                log.err(fail, "Invalid encoding in {what}.".format(what=what))
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

        def _finish(result):
            request_finished[0] = True

        def _execute():
            # Actually doing the match right here. This can cause an exception
            # to percolate up. If that happens it will be handled below in
            # processing_failed, either by a user-registered error handler or
            # one of our defaults.
            (rule, kwargs) = mapper.match(return_rule=True)
            endpoint = rule.endpoint

            # Try pretty hard to fix up prepath and postpath.
            segment_count = self._app.endpoints[endpoint].segment_count
            request.prepath.extend(request.postpath[:segment_count])
            request.postpath = request.postpath[segment_count:]

            request.notifyFinish().addBoth(_finish)

            # Standard Twisted Web stuff. Defer the method action, giving us
            # something renderable or printable. Return NOT_DONE_YET and set up
            # the incremental renderer.
            d = defer.maybeDeferred(self._app.execute_endpoint,
                                    endpoint,
                                    request,
                                    **kwargs)

            request.notifyFinish().addErrback(lambda _: d.cancel())

            return d

        d = defer.maybeDeferred(_execute)

        def process(r):
            """
            Recursively go through r and any child Resources until something
            returns an IRenderable, then render it and let the result of that
            bubble back up.
            """

            if IResource.providedBy(r):
                request.render(getChildForRequest(r, request))
                return _StandInResource

            if IRenderable.providedBy(r):
                renderElement(request, r)
                return _StandInResource

            return r

        d.addCallback(process)

        def processing_failed(failure, error_handlers):
            # The failure processor writes to the request.  If the
            # request is already finished we should suppress failure
            # processing.  We don't return failure here because there
            # is no way to surface this failure to the user if the
            # request is finished.
            if request_finished[0]:
                if not failure.check(defer.CancelledError):
                    log.err(failure, "Unhandled Error Processing Request.")
                return

            # If there are no more registered handlers, apply some defaults
            if len(error_handlers) == 0:
                if failure.check(HTTPException):
                    he = failure.value
                    request.setResponseCode(he.code)
                    resp = he.get_response({})

                    for header, value in resp.headers:
                        request.setHeader(
                            ensure_utf8_bytes(header), ensure_utf8_bytes(value)
                        )

                    return ensure_utf8_bytes(b''.join(resp.iter_encoded()))
                else:
                    request.processingFailed(failure)
                    return

            error_handler = error_handlers[0]

            # Each error handler is a tuple of
            # (list_of_exception_types, handler_fn)
            if failure.check(*error_handler[0]):
                d = defer.maybeDeferred(self._app.execute_error_handler,
                                        error_handler[1],
                                        request,
                                        failure)

                d.addCallback(process)

                return d.addErrback(processing_failed, error_handlers[1:])

            return processing_failed(failure, error_handlers[1:])

        d.addErrback(processing_failed, self._app._error_handlers)

        def write_response(r):
            if r is not _StandInResource:
                if isinstance(r, unicode):
                    r = r.encode('utf-8')

                if (r is not None) and (r != NOT_DONE_YET):
                    request.write(r)

                if not request_finished[0]:
                    request.finish()

        d.addCallback(write_response)
        d.addErrback(log.err, _why="Unhandled Error writing response")

        return server.NOT_DONE_YET
