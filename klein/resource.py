from twisted.web.resource import Resource, IResource, getChildForRequest
from twisted.web.iweb import IRenderable
from twisted.web.template import flattenString
from twisted.web import server
from twisted.internet import defer

from werkzeug.exceptions import HTTPException

from klein.interfaces import IKleinRequest

__all__ = ["KleinResource"]


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

        # Actually doing the match right here. This can cause an exception to
        # percolate up, which we can catch and render directly in order to
        # save ourselves some legwork.
        try:
            (rule, kwargs) = mapper.match(return_rule=True)
            endpoint = rule.endpoint
        except HTTPException as he:
            request.setResponseCode(he.code)
            return he.get_body({})

        handler = self._app.endpoints[endpoint]

        # Standard Twisted Web stuff. Defer the method action, giving us
        # something renderable or printable. Return NOT_DONE_YET and set up
        # the incremental renderer.
        d = defer.maybeDeferred(handler, request, **kwargs)

        def process(r):
            if IResource.providedBy(r):
                while (request.postpath and
                       request.postpath != kleinRequest.branch_segments):
                    request.prepath.append(request.postpath.pop(0))

                return request.render(getChildForRequest(r, request))

            if IRenderable.providedBy(r):
                return flattenString(request, r).addCallback(process)

            if isinstance(r, unicode):
                r = r.encode('utf-8')

            if r is not None:
                request.write(r)

            request.finish()

        d.addCallback(process)
        d.addErrback(request.processingFailed)
        return server.NOT_DONE_YET
