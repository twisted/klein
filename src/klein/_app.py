# -*- test-case-name: klein.test.test_app -*-
"""
Applications are great.  Lets have more of them.
"""


import sys
from contextlib import contextmanager
from inspect import iscoroutine
from typing import (
    IO,
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)
from weakref import ref


try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # type: ignore[misc]

from werkzeug.routing import Map, MapAdapter, Rule, Submount
from zope.interface import implementer

from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred
from twisted.internet.endpoints import serverFromString
from twisted.python import log
from twisted.python.components import registerAdapter
from twisted.python.failure import Failure
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import IResource
from twisted.web.server import Request, Site

from ._decorators import modified, named
from ._interfaces import IKleinRequest, KleinQueryValue
from ._resource import KleinResource


KleinSynchronousRenderable = Union[str, bytes, IResource, IRenderable]
KleinRenderable = Union[
    KleinSynchronousRenderable, Awaitable[KleinSynchronousRenderable]
]


class KleinRouteFunction(Protocol):
    def __call__(_self, request: IRequest) -> KleinRenderable:
        """
        Function that, when decorated by L{Klein.route}, handles a Klein
        request.
        """


class KleinRouteMethod(Protocol):
    def __call__(_self, self: Any, request: IRequest) -> KleinRenderable:
        """
        Method that, when decorated by L{Klein.route}, handles a Klein
        request.
        """


class KleinErrorFunction(Protocol):
    def __call__(
        _self,
        request: IRequest,
        failure: Failure,
    ) -> KleinRenderable:
        """
        Function that, when registered with L{Klein.handle_errors}, handles
        errors raised during request routing.
        """


class KleinErrorMethod(Protocol):
    def __call__(
        _self,
        self: Optional["Klein"],
        request: IRequest,
        failure: Failure,
    ) -> KleinRenderable:
        """
        Method that, when registered with L{Klein.handle_errors}, handles
        errors raised during request routing.
        """


KleinRouteHandler = Union[KleinRouteFunction, KleinRouteMethod]
KleinErrorHandler = Union[KleinErrorFunction, KleinErrorMethod]


def _call(
    __klein_instance__: Optional["Klein"],
    __klein_f__: Callable[..., KleinRenderable],
    *args: Any,
    **kwargs: Any,
) -> KleinRenderable:
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
        result = ensureDeferred(result)  # type: ignore[arg-type]
    return result


def buildURL(
    mapper: MapAdapter,
    endpoint: str,
    values: Optional[Mapping[str, KleinQueryValue]] = None,
    method: Optional[str] = None,
    force_external: bool = False,
    append_unknown: bool = True,
) -> str:
    return mapper.build(
        endpoint, values, method, force_external, append_unknown
    )


@implementer(IKleinRequest)
class KleinRequest:
    def __init__(self, request: Request) -> None:
        self.branch_segments = [""]

        # Don't annotate as optional, since you should never set this to None
        self.mapper: MapAdapter = None  # type: ignore[assignment]

    def url_for(
        self,
        endpoint: str,
        values: Optional[Mapping[str, KleinQueryValue]] = None,
        method: Optional[str] = None,
        force_external: bool = False,
        append_unknown: bool = True,
    ) -> str:
        return buildURL(
            self.mapper,
            endpoint,
            values,
            method,
            force_external,
            append_unknown,
        )


registerAdapter(KleinRequest, Request, IKleinRequest)


ErrorHandlers = List[Tuple[List[Type[Exception]], KleinErrorHandler]]


class Klein:
    """
    L{Klein} is an object which is responsible for maintaining the routing
    configuration of our application.

    @ivar _url_map: A C{werkzeug.routing.Map} object which will be used for
        routing resolution.
    @ivar _endpoints: A C{dict} mapping endpoint names to handler functions.
    """

    _subroute_segments = 0

    def __init__(self) -> None:
        self._url_map = Map()
        self._endpoints: Dict[str, KleinRouteHandler] = {}
        self._error_handlers: ErrorHandlers = []
        self._instance: Optional[Klein] = None
        self._boundAs: Optional[str] = None

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Klein):
            return vars(self) == vars(other)
        return NotImplemented

    def __ne__(self, other: Any) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    @property
    def url_map(self) -> Map:
        """
        Read only property exposing L{Klein._url_map}.
        """
        return self._url_map

    @property
    def endpoints(self) -> Dict[str, KleinRouteHandler]:
        """
        Read only property exposing L{Klein._endpoints}.
        """
        return self._endpoints

    def execute_endpoint(
        self, endpoint: str, request: IRequest, *args: Any, **kwargs: Any
    ) -> KleinRenderable:
        """
        Execute the named endpoint with all arguments and possibly a bound
        instance.
        """
        endpoint_f = self._endpoints[endpoint]
        # typing note: endpoint_f is a KleinRouteHandler, which is not defined
        # as taking *args, **kwargs (because they aren't required), but we're
        # going to pass them along here anyway.
        return endpoint_f(
            self._instance, request, *args, **kwargs  # type: ignore[arg-type]
        )  # type: ignore[call-arg]

    def execute_error_handler(
        self,
        handler: KleinErrorMethod,
        request: IRequest,
        failure: Failure,
    ) -> KleinRenderable:
        """
        Execute the passed error handler, possibly with a bound instance.
        """
        return handler(self._instance, request, failure)

    def resource(self) -> KleinResource:
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """

        return KleinResource(self)

    def __get__(self, instance: Any, owner: object) -> "Klein":
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

        boundName = f"__klein_bound_{self._boundAs}__"
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
    def _segments_in_url(url: str) -> int:
        segment_count = url.count("/")
        if url.endswith("/"):
            segment_count -= 1
        return segment_count

    def route(
        self, url: str, *args: Any, **kwargs: Any
    ) -> Callable[[KleinRouteHandler], KleinRouteHandler]:
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
        @param branch: A bool indiciated if a branch endpoint should
            be added that allows all child path segments that don't
            match some other route to be consumed.  Default C{False}.

        @returns: decorated handler function.
        """
        segment_count = self._segments_in_url(url) + self._subroute_segments

        @named("router for '" + url + "'")
        def deco(f: KleinRouteHandler) -> KleinRouteHandler:
            kwargs.setdefault(
                "endpoint",
                f.__name__,  # type: ignore[union-attr]
            )
            if kwargs.pop("branch", False):
                branchKwargs = kwargs.copy()
                branchKwargs["endpoint"] = branchKwargs["endpoint"] + "_branch"

                @modified(f"branch route '{url}' executor", f)
                def branch_f(
                    instance: Any,
                    request: IRequest,
                    *a: Any,
                    **kw: Any,
                ) -> KleinRenderable:
                    IKleinRequest(request).branch_segments = kw.pop(
                        "__rest__", ""
                    ).split("/")
                    return _call(instance, f, request, *a, **kw)

                branch_f = cast(KleinRouteHandler, branch_f)

                branch_f.segment_count = (  # type: ignore[union-attr]
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

            @modified(f"route '{url}' executor", f)
            def _f(
                instance: Any,
                request: IRequest,
                *a: Any,
                **kw: Any,
            ) -> KleinRenderable:
                return _call(instance, f, request, *a, **kw)

            _f = cast(KleinRouteHandler, _f)

            _f.segment_count = segment_count  # type: ignore[union-attr]

            self._endpoints[kwargs["endpoint"]] = _f
            self._url_map.add(Rule(url, *args, **kwargs))
            return f

        return deco

    @contextmanager
    def subroute(self, prefix: str) -> Iterator["Klein"]:
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

        @param prefix: The string that will be prepended to the paths of all
                       routes established during the with-block.
        """

        _map_before_submount = self._url_map

        segments = self._segments_in_url(prefix)

        class SubmountMap:
            def __init__(self) -> None:
                self.rules: List[Rule] = []

            def add(self, rule: Rule) -> None:
                self.rules.append(rule)

        submount_map = SubmountMap()

        try:
            self._url_map = cast(Map, submount_map)
            self._subroute_segments += segments
            yield self
            _map_before_submount.add(Submount(prefix, submount_map.rules))
        finally:
            self._url_map = _map_before_submount
            self._subroute_segments -= segments

    @overload
    def handle_errors(
        self,
        f_or_exception: KleinErrorHandler,
        *additional_exceptions: Type[Exception],
    ) -> Callable[[KleinErrorHandler], Callable]:
        ...  # pragma: no cover

    @overload
    def handle_errors(
        self,
        f_or_exception: Type[Exception],
        *additional_exceptions: Type[Exception],
    ) -> Callable[[KleinErrorHandler], Callable]:
        ...  # pragma: no cover

    def handle_errors(
        self,
        f_or_exception: Union[KleinErrorHandler, Type[Exception]],
        *additional_exceptions: Type[Exception],
    ) -> Callable[[KleinErrorHandler], Callable]:
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

        In addition to handling errors that occur within a L{KleinRouteHandler},
        error handlers also handle any L{werkzeug.exceptions.HTTPException}
        which is raised during request routing.

        In particular, C{werkzeug.exceptions.NotFound} will be raised if no
        matching route is found, so to return a custom 404 users can do the
        following::

            @app.handle_errors(NotFound)
            def error_handler(request, failure):
                request.setResponseCode(404)
                return 'Not found'

        @param f_or_exception: An error handler function, or an C{Exception}
            subclass to scope the decorated handler to.
        @param additional_exceptions: Additional C{Exception} subclasses to
            scope the decorated function to.

        @returns: decorated error handler function.
        """
        # Try to detect calls using the "simple" @app.handle_error syntax by
        # introspecting the first argument - if it isn't a type which
        # subclasses Exception we assume the simple syntax was used.
        if not isinstance(f_or_exception, type) or not issubclass(
            f_or_exception, Exception
        ):
            # f_or_exception is a KleinErrorHandler
            f = cast(KleinErrorHandler, f_or_exception)
            return self.handle_errors(Exception)(f)

        # f_or_exception is an Exception class
        exceptions = [f_or_exception] + list(additional_exceptions)

        def deco(f: KleinErrorHandler) -> Callable:
            @modified("error handling wrapper", f)
            def _f(
                instance: Optional["Klein"],
                request: IRequest,
                failure: Failure,
            ) -> KleinRenderable:
                return _call(instance, f, request, failure)

            self._error_handlers.append((exceptions, _f))

            return cast(Callable, _f)

        return deco

    def urlFor(
        self,
        request: IRequest,
        endpoint: str,
        values: Optional[Mapping[str, KleinQueryValue]] = None,
        method: Optional[str] = None,
        force_external: bool = False,
        append_unknown: bool = True,
    ) -> str:
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
        host: Optional[str] = None,
        port: Optional[int] = None,
        logFile: Optional[IO] = None,
        endpoint_description: Optional[str] = None,
        displayTracebacks: bool = True,
    ) -> None:
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
            endpoint_description = f"tcp:port={port}:interface={host}"

        endpoint = serverFromString(reactor, endpoint_description)

        site = Site(self.resource())
        site.displayTracebacks = displayTracebacks

        endpoint.listen(site)
        reactor.run()  # type: ignore[attr-defined]


_globalKleinApp = Klein()

route = _globalKleinApp.route
run = _globalKleinApp.run
subroute = _globalKleinApp.subroute
resource = _globalKleinApp.resource
handle_errors = _globalKleinApp.handle_errors
urlFor = url_for = _globalKleinApp.urlFor
