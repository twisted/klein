
import attr

from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implementer

from ._app import _call
from ._decorators import bindable, modified
from ._interfaces import (
    ISession, ISessionProcurer, NoSuchSession, SessionMechanism,
    TooLateForCookies, ISessionStore
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    ISessionStore


@implementer(ISessionProcurer)
@attr.s
class SessionProcurer(object):
    """
    A L{SessionProcurer} procures a session from a request and a store.

    @ivar _store: The session store to procure a session from.
    @type _store: L{klein.interfaces.ISessionStore}

    @ivar _maxAge: The maximum age (in seconds) of the session cookie.
    @type _maxAge: L{int}

    @ivar _secureCookie: The name of the cookie to use for sessions protected
        with TLS (i.e. HTTPS).
    @type _secureCookie: L{bytes}

    @ivar _insecureCookie: The name of the cookie to use for sessions I{not}
        protected with TLS (i.e. HTTP).
    @type _insecureCookie: L{bytes}

    @ivar _cookieDomain: If set, the domain name to restrict the session
        cookie to.
    @type _cookieDomain: L{None} or L{bytes}

    @ivar _cookiePath: If set, the URL path to restrict the session cookie to.
    @type _cookiePath: L{bytes}

    @ivar _secureTokenHeader: The name of the HTTPS header to try to extract
        a session token from; API clients should use this header, rather than a
        cookie.
    @type _secureTokenHeader: L{bytes}

    @ivar _insecureTokenHeader: The name of the HTTP header to try to extract
        a session token from; API clients should use this header, rather than a
        cookie.
    @type _insecureTokenHeader: L{bytes}
    """

    _store = attr.ib()

    _maxAge = attr.ib(default=3600)
    _secureCookie = attr.ib(default=b"Klein-Secure-Session")
    _insecureCookie = attr.ib(default=b"Klein-INSECURE-Session")
    _cookieDomain = attr.ib(default=None)
    _cookiePath = attr.ib(default=b"/")

    _secureTokenHeader = attr.ib(default=b"X-Auth-Token")
    _insecureTokenHeader = attr.ib(default=b"X-INSECURE-Auth-Token")

    if TYPE_CHECKING:

        def __init__(
                self,
                store,                                # type: ISessionStore
                maxAge=3600,                          # type: int
                secureCookie=b"Klein-Secure-Session", # type: bytes
                insecureCookie=b"Klein-INSECURE-Session", # type: bytes
                cookieDomain=None,                        # type: _Optional[bytes]
                cookiePath=b'/',                          # type: bytes
                secureTokenHeader=b"X-Auth-Token",        # type: bytes
                insecureTokenHeader=b"X-INSECURE-Auth-Token" # type: bytes
        ):
            # type: (...) -> None
            pass

    @inlineCallbacks
    def procureSession(self, request, forceInsecure=False, alwaysCreate=True):
        # type: (IRequest, bool, bool) -> Awaitable[ISession]
        alreadyProcured = ISession(request, None)
        if alreadyProcured is not None:
            returnValue(alreadyProcured)

        if request.isSecure():
            if forceInsecure:
                tokenHeader = self._insecureTokenHeader
                cookieName = self._insecureCookie
                sentSecurely = False
            else:
                tokenHeader = self._secureTokenHeader
                cookieName = self._secureCookie
                sentSecurely = True
        else:
            # Have we inadvertently disclosed a secure token over an insecure
            # transport, for example, due to a buggy client?
            allPossibleSentTokens = (
                sum([request.requestHeaders.getRawHeaders(header, [])
                     for header in [self._secureTokenHeader,
                                    self._insecureTokenHeader]], []) +
                [it for it in [request.getCookie(cookie)
                               for cookie in [self._secureCookie,
                                              self._insecureCookie]] if it]
            )
            # Does it seem like this check is expensive? It sure is! Don't want
            # to do it? Turn on your dang HTTPS!
            yield self._store.sentInsecurely(allPossibleSentTokens)
            tokenHeader = self._insecureTokenHeader
            cookieName = self._insecureCookie
            sentSecurely = False
            # Fun future feature: honeypot that does this over HTTPS, but sets
            # isSecure() to return false because it serves up a cert for the
            # wrong hostname or an invalid cert, to keep API clients honest
            # about chain validation.
        sessionID = request.getHeader(tokenHeader)
        if sessionID is not None:
            mechanism = SessionMechanism.Header
        else:
            mechanism = SessionMechanism.Cookie
            sessionID = request.getCookie(cookieName)
        if sessionID is not None:
            sessionID = sessionID.decode('ascii')
            try:
                session = yield self._store.loadSession(
                    sessionID, sentSecurely, mechanism
                )
            except NoSuchSession:
                if mechanism == SessionMechanism.Header:
                    raise
                sessionID = None
        if sessionID is None:
            if alwaysCreate:
                if request.startedWriting:
                    # At this point, if the mechanism is Header, we either have
                    # a valid session or we bailed after NoSuchSession above.
                    raise TooLateForCookies(
                        "You tried initializing a cookie-based session too"
                        " late in the request pipeline; the headers"
                        " were already sent."
                    )
                session = yield self._store.newSession(sentSecurely,
                                                       mechanism)
            else:
                returnValue(None)
        if sessionID != session.identifier:
            if request.startedWriting:
                raise TooLateForCookies(
                    "You tried changing a session ID to a new session ID too"
                    " late in the request pipeline; the headers were already"
                    " sent."
                )
            request.addCookie(
                cookieName, session.identifier, max_age=self._maxAge,
                domain=self._cookieDomain, path=self._cookiePath,
                secure=sentSecurely, httpOnly=True,
            )
        if not forceInsecure:
            # Do not cache the insecure session on the secure request, thanks.
            request.setComponent(ISession, session)
        returnValue(session)


from typing import Union, Callable, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from twisted.web.iweb import IRequest
    from mypy_extensions import KwArg, VarArg, Arg
    from zope.interface import IInterface
    from typing import TypeVar, Optional as _Optional, Dict, Awaitable
    T = TypeVar('T')
    IRequest, Arg, KwArg, VarArg, Callable, Any, IInterface, _Optional, Dict, Awaitable
    _routeCallable = Any

_procureProcurerType = Union[
    Callable[[Any], ISessionProcurer],
    Callable[[], ISessionProcurer]
]

def requirer(procure_procurer):
    # type: (_procureProcurerType) -> Callable[[Arg(_routeCallable, 'route'), KwArg(Any)], Callable[[Callable[[IRequest, VarArg(Any), KwArg(Any)], None]], None]]
    def requires(route, **kw):
        # type: (_routeCallable, **Any) -> Callable[[Callable[[IRequest, VarArg(Any), KwArg(Any)], None]], None]
        def toroute(thunk):
            # type: (Callable[[IRequest, VarArg(Any), KwArg(Any)], None]) -> None
            # FIXME: this should probably inspect the signature of 'thunk' to
            # see if it has default arguments, rather than relying upon people
            # to pass in Optional instances
            optified = dict([(k, Required.maybe(v)) for k, v in kw.items()])
            any_required = any(v._required for v in optified.values())
            session_set = set([Optional(ISession), Required(ISession)])
            to_authorize = set(x._interface for x in
                               (set(optified.values()) - session_set))

            @modified("requirer", thunk, route)
            @bindable
            @inlineCallbacks
            def routed(instance, request, *args, **kwargs):
                # type: (object, IRequest, *Any, **Any) -> Any
                newkw = kwargs.copy()
                procu = _call(instance, procure_procurer)
                session = yield (
                    procu.procureSession(request, alwaysCreate=any_required)
                )
                values = ({} if session is None else
                          (yield session.authorize(to_authorize)))
                values[ISession] = session
                for k, v in optified.items():
                    oneval = v.retrieve(values)
                    newkw[k] = oneval
                returnValue(
                    (yield _call(instance, thunk, request, *args, **newkw))
                )
        return toroute
    return requires



@attr.s(frozen=True)
class Optional(object):
    _interface = attr.ib()
    _required = False

    if TYPE_CHECKING:
        def __init__(self, interface):
            # type: (IInterface) -> None
            pass

    def retrieve(self, dict):
        # type: (Dict[IInterface, T]) -> _Optional[T]
        return dict.get(self._interface, None)

@attr.s(frozen=True)
class Required(object):
    _interface = attr.ib()
    _required = True

    if TYPE_CHECKING:
        def __init__(self, interface):
            # type: (IInterface) -> None
            pass

    @classmethod
    def maybe(cls, it):
        # type: (Union[Optional, Required, object]) -> Union[Optional, Required]
        if isinstance(it, (Optional, Required)):
            return it
        return cls(it)

    def retrieve(self, dict):
        # type: (Dict[IInterface, T]) -> T
        return dict[self._interface]
