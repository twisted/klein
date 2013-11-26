from twisted.web.resource import Resource, IResource, getChildForRequest
from twisted.web.iweb import IRenderable
from twisted.web.template import flattenString
from twisted.web import server

from twisted.python import log

from twisted.internet import defer


from werkzeug.exceptions import HTTPException

from klein.interfaces import IKleinRequest

__all__ = ["KleinResource", "ensure_utf8_bytes"]


def ensure_utf8_bytes(v):
    """
    Coerces a value which is either a C{unicode} or C{str} to a C{str}.
    If ``v`` is a C{unicode} object it is encoded as utf-8.
    """
    if isinstance(v, unicode):
        v = v.encode("utf-8")
    return v


class StandInRenderable(object):
    """
    A standin for a Renderable.
    """


class KleinResource(Resource):
    """
    A ``Resource`` that can do URL routing.
    """
    isLeaf = True


    def __init__(self, app):
        Resource.__init__(self)
        self._app = app


    def render(self, request):
        # Stuff we need to know for the mapper.
        server_name = request.getRequestHostname()
        server_port = request.getHost().port
        if (bool(request.isSecure()), server_port) not in [
                (True, 443), (False, 80)]:
            server_name = '%s:%d' % (server_name, server_port)
        script_name = ''
        if request.prepath:
            script_name = '/'.join(request.prepath)

            if not script_name.startswith('/'):
                script_name = '/' + script_name

        path_info = ''
        if request.postpath:
            path_info = '/'.join(request.postpath)

            if not path_info.startswith('/'):
                path_info = '/' + path_info

        url_scheme = 'https' if request.isSecure() else 'http'
        # Bind our mapper.
        mapper = self._app.url_map.bind(server_name, script_name, path_info=path_info,
            default_method=request.method, url_scheme=url_scheme)
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

        def write_response(r):
            if not isinstance(r, StandInRenderable):
                if isinstance(r, unicode):
                    r = r.encode('utf-8')

                if r is not None:
                    request.write(r)

                if not request_finished[0]:
                    request.finish()

        def process(r):
            if IResource.providedBy(r):
                request.render(getChildForRequest(r, request))
                return StandInRenderable()

            if IRenderable.providedBy(r):
                return flattenString(request, r).addCallback(process)

            return r

        def processing_failed(failure, error_handlers):
            # The failure processor writes to the request.  If the
            # request is already finished we should suppress failure
            # processing.  We don't return failure here because there
            # is no way to surface this failure to the user if the
            # request is finished.
            if request_finished[0]:
                if not failure.check(defer.CancelledError):
                    log.err(failure, _why="Unhandled Error Processing Request.")
                return

            # If there are no more registered handlers, apply some defaults
            if len(error_handlers) == 0:
                if failure.check(HTTPException):
                    he = failure.value
                    request.setResponseCode(he.code)
                    resp = he.get_response({})

                    for header, value in resp.headers:
                        request.setHeader(ensure_utf8_bytes(header), ensure_utf8_bytes(value))

                    return ensure_utf8_bytes(he.get_body({}))
                else:
                    request.processingFailed(failure)
                    return

            error_handler = error_handlers[0]

            # Each error handler is a tuple of (list_of_exception_types, handler_fn)
            if failure.check(*error_handler[0]):
                d = defer.maybeDeferred(self._app.execute_error_handler,
                                        error_handler[1],
                                        request,
                                        failure)

                return d.addErrback(processing_failed, error_handlers[1:])

            return processing_failed(failure, error_handlers[1:])

        d = defer.maybeDeferred(_execute)
        d.addCallback(process)
        d.addErrback(processing_failed, self._app._error_handlers)
        d.addCallback(write_response).addErrback(log.err,
            _why="Unhandled Error writing response")
        return server.NOT_DONE_YET
