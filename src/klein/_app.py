# -*- test-case-name: klein.test.test_app -*-
"""
Applications are great.  Lets have more of them.
"""

from __future__ import absolute_import, division

import sys
from collections import namedtuple
from contextlib import contextmanager
from inspect import iscoroutine

from typing import (
    Any,
    Callable,
    Dict,
    IO,
    List,
    Mapping,
    Optional,
    Text,
    Union,
    cast,
)
from weakref import ref

from twisted.internet import reactor
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.endpoints import serverFromString
from twisted.python import log
from twisted.python.components import registerAdapter
from twisted.python.failure import Failure
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import IResource
from twisted.web.server import Request, Site

from werkzeug.routing import Map, MapAdapter, Rule, Submount

from zope.interface import implementer

from ._decorators import modified, named
from ._interfaces import IKleinRequest
from ._resource import KleinResource
from ._typing import Awaitable, KwArg, VarArg


KleinSynchronousRenderable = Union[str, bytes, IResource, IRenderable]
KleinRenderable = Union[
    KleinSynchronousRenderable, Awaitable[KleinSynchronousRenderable]
]
KleinRoute = Callable[[Any, IRequest, VarArg(Any), KwArg(Any)], KleinRenderable]
KleinErrorHandler = Callable[
    [Optional["Klein"], IRequest, Failure], KleinRenderable
]


def _call(__klein_instance__, __klein_f__, *args, **kwargs):
    # type: (Optional[Klein], Callable, Any, Any) -> Deferred
    """
    Call C{__klein_f__} with the given C{*args} and C{**kwargs}.

    Insert C{__klein_instance__} as the first positional argument to
    C{__klein_f__} if C{__klein_f__} is not decorated with
    L{klein._decorators.bindable}.

    @return: The result of C{__klein_f__}; additionally, if C{__klein_f__}
        returns a coroutine, instead return the Deferred created by calling
        C{ensureDeferred} on it.
    """
    if __klein_instance__ is not None or getattr(
        __klein_f__, "__klein_bound__", False
    ):
        args = (__klein_instance__,) + args
    result = __klein_f__(*args, **kwargs)
    if iscoroutine(result):
        result = ensureDeferred(result)
    return result


def buildURL(
    mapper,  # type: MapAdapter
    endpoint,  # type: Text
    values=None,  # type: Optional[Mapping[Text, Text]]
    method=None,  # type: Optional[Text]
    force_external=False,  # type: bool
    append_unknown=True,  # type: bool
):
    # type: (...) -> Text
    return cast(
        Text,
        mapper.build(endpoint, values, method, force_external, append_unknown),
    )


@implementer(IKleinRequest)
class KleinRequest(object):
    def __init__(self, request):
        # type: (Request) -> None
        self.branch_segments = [""]

        # Don't annotate as optional, since you should never set this to None
        self.mapper = None  # type: MapAdapter # type: ignore[assignment]

    def url_for(
        self,
        endpoint,  # type: Text
        values=None,  # type: Optional[Mapping[Text, Text]]
        method=None,  # type: Optional[Text]
        force_external=False,  # type: bool
        append_unknown=True,  # type: bool
    ):
        # type: (...) -> Text
        return buildURL(
            self.mapper,
            endpoint,
            values,
            method,
            force_external,
            append_unknown,
        )


registerAdapter(KleinRequest, Request, IKleinRequest)


class Klein(object):
    """
    L{Klein} is an object which is responsible for maintaining the routing
    configuration of our application.

    @ivar _url_map: A C{werkzeug.routing.Map} object which will be used for
        routing resolution.
    @ivar _endpoints: A C{dict} mapping endpoint names to handler functions.
    """

    _subroute_segments = 0

    def __init__(self):
        # type: () -> None
        self._url_map = Map()
        self._endpoints = {}  # type: Dict[Text, KleinRoute]
        self._error_handlers = []  # type: List[KleinErrorHandler]
        self._instance = None  # type: Optional[Klein]
        self._boundAs = None  # type: Optional[Text]

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, Klein):
            return vars(self) == vars(other)
        return NotImplemented

    def __ne__(self, other):
        # type: (Any) -> bool
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    @property
    def url_map(self):
        # type: () -> Map
        """
        Read only property exposing L{Klein._url_map}.
        """
        return self._url_map

    @property
    def endpoints(self):
        # type: () -> Dict[Text, KleinRoute]
        """
        Read only property exposing L{Klein._endpoints}.
        """
        return self._endpoints

    def execute_endpoint(self, endpoint, request, *args, **kwargs):
        # type: (Text, IRequest, Any, Any) -> KleinRenderable
        """
        Execute the named endpoint with all arguments and possibly a bound
        instance.
        """
        endpoint_f = self._endpoints[endpoint]
        return endpoint_f(self._instance, request, *args, **kwargs)

    def execute_error_handler(self, handler, request, failure):
        # type: (KleinErrorHandler, IRequest, Failure) -> KleinRenderable
        """
        Execute the passed error handler, possibly with a bound instance.
        """
        return handler(self._instance, request, failure)

    def resource(self):
        # type: () -> KleinResource
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """

        return KleinResource(self)

    def __get__(self, instance, owner):
        # type: (Any, object) -> Klein
        """
        Get an instance of L{Klein} bound to C{instance}.
        """
        if instance is None:
            return self

        if self._boundAs is None:
            for name in dir(owner):
                # Properties may raise an AttributeError on access even though
                # they're visible on the instance, we can ignore those because
                # Klein instances won't raise AttributeError.
                obj = getattr(owner, name, None)
                if obj is self:
                    self._boundAs = name
                    break
            else:
                self._boundAs = "unknown_" + str(id(self))

        boundName = "__klein_bound_{}__".format(self._boundAs)
        k = cast(
            Optional["Klein"], getattr(instance, boundName, lambda: None)()
        )

        if k is None:
            k = self.__class__()
            k._url_map = self._url_map
            k._endpoints = self._endpoints
            k._error_handlers = self._error_handlers
            k._instance = instance
            kref = ref(k)
            try:
                setattr(instance, boundName, kref)
            except AttributeError:
                pass

        return k

    @staticmethod
    def _segments_in_url(url):
        # type: (Text) -> int
        segment_count = url.count("/")
        if url.endswith("/"):
            segment_count -= 1
        return segment_count

    def route(self, url, *args, **kwargs):
        """
        Add a new handler for C{url} passing C{args} and C{kwargs} directly to
        C{werkzeug.routing.Rule}.  The handler function will be passed at least
        one argument an L{twisted.web.server.Request} and any keyword arguments
        taken from the C{url} pattern.

        ::
            @app.route("/")
            def index(request):
                return "Hello"

        @param url: A werkzeug URL pattern given to C{werkzeug.routing.Rule}.
        @type url: str

        @param branch: A bool indiciated if a branch endpoint should
            be added that allows all child path segments that don't
            match some other route to be consumed.  Default C{False}.
        @type branch: bool


        @returns: decorated handler function.
        """
        segment_count = self._segments_in_url(url) + self._subroute_segments

        @named("router for '" + url + "'")
        def deco(f):
            # type: (KleinRoute) -> KleinRoute
            kwargs.setdefault("endpoint", f.__name__)
            if kwargs.pop("branch", False):
                branchKwargs = kwargs.copy()
                branchKwargs["endpoint"] = branchKwargs["endpoint"] + "_branch"

                @modified("branch route '{url}' executor".format(url=url), f)
                def branch_f(instance, request, *a, **kw):
                    # type: (Any, IRequest, Any, Any) -> KleinRenderable
                    IKleinRequest(request).branch_segments = kw.pop(
                        "__rest__", ""
                    ).split("/")
                    return _call(instance, f, request, *a, **kw)

                branch_f = cast(KleinRoute, branch_f)

                branch_f.segment_count = (  # type: ignore[attr-defined]
                    segment_count
                )

                self._endpoints[branchKwargs["endpoint"]] = branch_f
                self._url_map.add(
                    Rule(
                        url.rstrip("/") + "/" + "<path:__rest__>",
                        *args,
                        **branchKwargs,
                    )
                )

            @modified("route '{url}' executor".format(url=url), f)
            def _f(instance, request, *a, **kw):
                # type: (Any, IRequest, Any, Any) -> KleinRenderable
                return _call(instance, f, request, *a, **kw)

            _f = cast(KleinRoute, _f)

            _f.segment_count = segment_count  # type: ignore[attr-defined]

            self._endpoints[kwargs["endpoint"]] = _f
            self._url_map.add(Rule(url, *args, **kwargs))
            return f

        return deco

    @contextmanager
    def subroute(self, prefix):
        """
        Within this block, C{@route} adds rules to a
        C{werkzeug.routing.Submount}.

        This is implemented by tinkering with the instance's C{_url_map}
        variable. A context manager allows us to gracefully use the pattern of
        "change a variable, do some things with the new value, then put it back
        to how it was before.

        Named "subroute" to try and give callers a better idea of its
        relationship to C{@route}.

        Usage:
        ::
            with app.subroute("/prefix") as app:
                @app.route("/foo")
                def foo_handler(request):
                    return 'I respond to /prefix/foo'

        @type prefix: string
        @param prefix: The string that will be prepended to the paths of all
                       routes established during the with-block.
        @return: Returns None.
        """

        _map_before_submount = self._url_map

        segments = self._segments_in_url(prefix)

        submount_map = namedtuple("submount", ["rules", "add"])(
            [], lambda r: submount_map.rules.append(r)
        )

        try:
            self._url_map = submount_map
            self._subroute_segments += segments
            yield self
            _map_before_submount.add(Submount(prefix, submount_map.rules))
        finally:
            self._url_map = _map_before_submount
            self._subroute_segments -= segments

    def handle_errors(self, f_or_exception, *additional_exceptions):
        """
        Register an error handler. This decorator supports two syntaxes. The
        simpler of these can be used to register a handler for all C{Exception}
        types::

            @app.handle_errors
            def error_handler(request, failure):
                request.setResponseCode(500)
                return 'Uh oh'

        Alternately, a handler can be registered for one or more specific
        C{Exception} types::

            @app.handle_errors(EncodingError, ValidationError):
            def error_handler(request, failure)
                request.setResponseCode(400)
                return failure.getTraceback()

        The handler will be passed a L{twisted.web.server.Request} as well as a
        L{twisted.python.failure.Failure} instance. Error handlers may return a
        deferred, a failure or a response body.

        If more than one error handler is registered, the handlers will be
        executed in the order in which they are defined, until a handler is
        encountered which completes successfully. If no handler completes
        successfully, L{twisted.web.server.Request}'s processingFailed() method
        will be called.

        In addition to handling errors that occur within a route handler, error
        handlers also handle any C{werkzeug.exceptions.HTTPException} which is
        raised during routing. In particular, C{werkzeug.exceptions.NotFound}
        will be raised if no matching route is found, so to return a custom 404
        users can do the following::

            @app.handle_errors(NotFound)
            def error_handler(request, failure):
                request.setResponseCode(404)
                return 'Not found'

        @param f_or_exception: An error handler function, or an C{Exception}
            subclass to scope the decorated handler to.
        @type f_or_exception: C{function} or C{Exception}

        @param additional_exceptions: Additional C{Exception} subclasses to
            scope the decorated function to.
        @type additional_exceptions: C{list} of C{Exception}s

        @returns: decorated error handler function.
        """
        # Try to detect calls using the "simple" @app.handle_error syntax by
        # introspecting the first argument - if it isn't a type which
        # subclasses Exception we assume the simple syntax was used.
        if not isinstance(f_or_exception, type) or not issubclass(
            f_or_exception, Exception
        ):
            return self.handle_errors(Exception)(f_or_exception)

        def deco(f):
            @modified("error handling wrapper", f)
            def _f(instance, request, failure):
                return _call(instance, f, request, failure)

            self._error_handlers.append(
                ([f_or_exception] + list(additional_exceptions), _f)
            )
            return _f

        return deco

    def urlFor(
        self,
        request,  # type: IKleinRequest
        endpoint,  # type: Text
        values=None,  # type: Optional[Mapping[Text, Text]]
        method=None,  # type: Optional[Text]
        force_external=False,  # type: bool
        append_unknown=True,  # type: bool
    ):
        # type: (...) -> Text
        host = request.getHeader(b"host")
        if host is None:
            if force_external:
                raise ValueError(
                    "Cannot build external URL if request"
                    " doesn't contain Host header"
                )
            host = b""
        return buildURL(
            self.url_map.bind(host),
            endpoint,
            values,
            method,
            force_external,
            append_unknown,
        )

    url_for = urlFor

    def run(
        self,
        host=None,  # type: Optional[str]
        port=None,  # type: Optional[int]
        logFile=None,  # type: Optional[IO]
        endpoint_description=None,  # type: Optional[str]
        displayTracebacks=True,  # type: bool
    ):
        # type: (...) -> None
        """
        Run a minimal twisted.web server on the specified C{port}, bound to the
        interface specified by C{host} and logging to C{logFile}.

        This function will run the default reactor for your platform and so
        will block the main thread of your application.  It should be the last
        thing your klein application does.

        @param host: The hostname or IP address to bind the listening socket
            to.  "0.0.0.0" will allow you to listen on all interfaces, and
            "127.0.0.1" will allow you to listen on just the loopback
            interface.

        @param port: The TCP port to accept HTTP requests on.

        @param logFile: The file object to log to, by default C{sys.stdout}

        @param endpoint_description: specification of endpoint. Must contain
             protocol, port and interface. May contain other optional arguments,
             e.g. to use SSL: "ssl:443:privateKey=key.pem:certKey=crt.pem"

        @param displayTracebacks: Weather a processing error will result in
            a page displaying the traceback with debugging information or not.
        """
        if logFile is None:
            logFile = sys.stdout

        log.startLogging(logFile)

        if not endpoint_description:
            endpoint_description = "tcp:port={0}:interface={1}".format(
                port, host
            )

        endpoint = serverFromString(reactor, endpoint_description)

        site = Site(self.resource())
        site.displayTracebacks = displayTracebacks

        endpoint.listen(site)
        reactor.run()


_globalKleinApp = Klein()

route = _globalKleinApp.route
run = _globalKleinApp.run
subroute = _globalKleinApp.subroute
resource = _globalKleinApp.resource
handle_errors = _globalKleinApp.handle_errors
urlFor = url_for = _globalKleinApp.urlFor
