# -*- test-case-name: klein.test.test_session -*-

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import attr
from zope.interface import Interface, implementer

from twisted.internet.defer import inlineCallbacks
from twisted.python.components import Componentized
from twisted.python.reflect import qual
from twisted.web.http import UNAUTHORIZED
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.server import Request

from ._util import eagerDeferredCoroutine
from .interfaces import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
    ISession,
    ISessionProcurer,
    ISessionStore,
    NoSuchSession,
    SessionMechanism,
    TooLateForCookies,
)


async def cookieLoader(
    self: SessionProcurer,
    request: IRequest,
    token: str,
    sentSecurely: bool,
    cookieName: Union[str, bytes],
) -> ISession:
    """
    Procuring a session from a cookie is complex.  First, just try to look it
    up based on the current cookie, but then, do a bunch of checks to see if we
    can set up a new session, then set one up.
    """
    try:
        return await self._store.loadSession(
            token, sentSecurely, SessionMechanism.Cookie
        )
    except NoSuchSession:
        pass

    # No existing session.
    if request.startedWriting:  # type: ignore[attr-defined]
        # At this point, if the mechanism is Header, we either have
        # a valid session or we bailed after NoSuchSession above.
        raise TooLateForCookies(
            "You tried initializing a cookie-based session too"
            " late in the request pipeline; the headers"
            " were already sent."
        )
    if request.method != b"GET":
        # Sessions should only ever be auto-created by GET
        # requests; there's no way that any meaningful data
        # manipulation could succeed (no CSRF token check could
        # ever succeed, for example).
        raise NoSuchSession(
            "Can't initialize a session on a "
            "{method} request.".format(method=request.method.decode("ascii"))
        )
    if not self._setCookieOnGET:
        # We don't have a session ID at all, and we're not allowed
        # by policy to set a cookie on the client.
        raise NoSuchSession(
            "Cannot auto-initialize a session for this request."
        )
    session = await self._store.newSession(
        sentSecurely, SessionMechanism.Cookie
    )

    # https://github.com/twisted/twisted/issues/11865
    wrongSignature: Request = request  # type:ignore[assignment]
    wrongSignature.addCookie(
        cookieName,
        session.identifier,
        max_age=str(self._maxAge),
        domain=self._cookieDomain,
        path=self._cookiePath,
        secure=sentSecurely,
        httpOnly=True,
    )

    return session


async def headerLoader(
    self: SessionProcurer,
    request: IRequest,
    token: str,
    sentSecurely: bool,
    cookieName: Union[str, bytes],
) -> ISession:
    """
    Procuring a session via a header API key is very simple.  Just look it up
    and fail if you can't find it.
    """
    return await self._store.loadSession(
        token, sentSecurely, SessionMechanism.Header
    )


loaderForMechanism = {
    SessionMechanism.Cookie: cookieLoader,
    SessionMechanism.Header: headerLoader,
}


@implementer(ISessionProcurer)
@attr.s(auto_attribs=True)
class SessionProcurer:
    """
    A L{SessionProcurer} procures a session from a request and a store.

    @ivar _store: The session store to procure a session from.
    @ivar _maxAge: The maximum age (in seconds) of the session cookie.
    @ivar _secureCookie: The name of the cookie to use for sessions protected
        with TLS (i.e. HTTPS).
    @ivar _insecureCookie: The name of the cookie to use for sessions I{not}
        protected with TLS (i.e. HTTP).
    @ivar _cookieDomain: If set, the domain name to restrict the session cookie
        to.
    @ivar _cookiePath: If set, the URL path to restrict the session cookie to.
    @ivar _secureTokenHeader: The name of the HTTPS header to try to extract a
        session token from; API clients should use this header, rather than a
        cookie.
    @ivar _insecureTokenHeader: The name of the HTTP header to try to extract a
        session token from; API clients should use this header, rather than a
        cookie.
    @ivar _setCookieOnGET: Automatically request that the session store create
        a session if one is not already associated with the request and the
        request is a GET.
    """

    _store: ISessionStore

    _maxAge: int = 3600
    _secureCookie: bytes = b"Klein-Secure-Session"
    _insecureCookie: bytes = b"Klein-INSECURE-Session"
    _cookieDomain: Optional[bytes] = None
    _cookiePath: bytes = b"/"

    _secureTokenHeader: bytes = b"X-Auth-Token"
    _insecureTokenHeader: bytes = b"X-INSECURE-Auth-Token"
    _setCookieOnGET: bool = True

    def _tokenTransportAttributes(
        self, request: IRequest, forceInsecure: bool
    ) -> Tuple[bytes, bytes, bool]:
        """
        @return: 3-tuple of header, cookie, secure
        """
        secure = (self._secureTokenHeader, self._secureCookie, True)
        insecure = (self._insecureTokenHeader, self._insecureCookie, False)

        if request.isSecure():
            return insecure if forceInsecure else secure

        # Have we inadvertently disclosed a secure token over an insecure
        # transport, for example, due to a buggy client?
        allPossibleSentTokens: Sequence[bytes] = sum(
            (
                request.requestHeaders.getRawHeaders(header, [])
                for header in [
                    self._secureTokenHeader,
                    self._insecureTokenHeader,
                ]
            ),
            [],
        ) + [
            it
            for it in [
                request.getCookie(cookie)
                for cookie in [self._secureCookie, self._insecureCookie]
                if cookie is not None
            ]
            if it
        ]

        # Fun future feature: honeypot that does this over HTTPS, but sets
        # isSecure() to return false because it serves up a cert for the
        # wrong hostname or an invalid cert, to keep API clients honest
        # about chain validation.
        self._store.sentInsecurely(
            [each.decode() for each in allPossibleSentTokens]
        )
        return insecure

    @eagerDeferredCoroutine
    async def procureSession(
        self, request: IRequest, forceInsecure: bool = False
    ) -> ISession:
        alreadyProcured: Optional[ISession] = ISession(request, None)
        if alreadyProcured is not None:
            if not forceInsecure or not request.isSecure():
                return alreadyProcured

        tokenHeader, cookieName, sentSecurely = self._tokenTransportAttributes(
            request, forceInsecure
        )

        sentHeader = (request.getHeader(tokenHeader) or b"").decode("utf-8")
        sentCookie = (request.getCookie(cookieName) or b"").decode("utf-8")

        mechanism, token = (
            (SessionMechanism.Header, sentHeader)
            if sentHeader
            else (SessionMechanism.Cookie, sentCookie)
        )

        session = await loaderForMechanism[mechanism](
            self, request, token, sentSecurely, cookieName
        )

        if sentSecurely or not request.isSecure():
            # Do not cache the insecure session on the secure request, thanks.
            cast(Componentized, request).setComponent(ISession, session)
        return session


class AuthorizationDenied(Resource):
    def __init__(self, interface: Type[Interface], instance: Any) -> None:
        self._interface = interface
        super().__init__()

    def render(self, request: IRequest) -> bytes:
        request.setResponseCode(UNAUTHORIZED)
        return f"{qual(self._interface)} DENIED".encode()


@implementer(IDependencyInjector, IRequiredParameter)
@attr.s(auto_attribs=True)
class Authorization:
    """
    Declare that a C{require}-decorated function requires a certain interface
    be authorized from the session.

    This is a dependency injector used in conjunction with a L{klein.Requirer},
    like so::

        from klein import Requirer, SesssionProcurer
        from klein.interfaces import ISession

        from myapp import ISuperDuperAdmin

        requirer = Requirer()
        procurer = SessionProcurer(store=someSessionStore)
        @requirer.prerequisite(ISession)
        def sessionize(request):
            return procurer.procureSession(request)

        app = Klein()

        @requirer.require(
            app.route("/admin"),
            adminPowers=Authorization(ISuperDuperAdmin)
        )
        def myRoute(adminPowers):
            return 'ok admin: ' + adminPowers.doAdminThing()

    In this example, ISuperDuperAdmin is an interface known to your
    application, and (via authorization plugins depending on your session
    storage backend) to your session store.  It has a doAdminThing method.
    When a user hits /admin in their browser, if they are duly authorized,
    they'll see 'ok admin: ' and whatever the super-secret result of
    doAdminThing is.  If not, by default, they'll simply get an HTTP
    UNAUTHORIZED response that says "myapp.ISuperDuperAdmin DENIED".  (This
    behavior can be customized via the C{whenDenied} parameter to
    L{Authorization}.)

    @ivar _interface: the interface that is required.  a provider of this
        interface is what will be dependency-injected.

    @ivar _required: is this authorization required?  If so (the default),
        don't invoke the application code if it cannot be authorized by the
        procured session, and instead return the object specified by whenDenied
        from the dependency-injection process.  If not, then just pass None if
        it is not on the session.

    @ivar _whenDenied: when this authorization is denied, what object - usually
        an IResource - should be returned to the route decorator that was
        passed to L{Requirer.require}?  Note that this will never be used if
        C{required} is set to C{False}.
    """

    _interface: Type[Interface]
    _required: bool = True
    _whenDenied: Callable[[Type[Interface], Any], Any] = AuthorizationDenied

    def registerInjector(
        self,
        injectionComponents: Componentized,
        parameterName: str,
        lifecycle: IRequestLifecycle,
    ) -> IDependencyInjector:
        """
        Register this authorization to inject a parameter.
        """
        return self

    @inlineCallbacks
    def injectValue(
        self, instance: Any, request: IRequest, routeParams: Dict[str, Any]
    ) -> Any:
        """
        Inject a value by asking the request's session.
        """
        # TODO: this could be optimized to do fewer calls to 'authorize' by
        # collecting all the interfaces that are necessary and then using
        # addBeforeHook; the interface would not need to change.
        session = ISession(request)
        provider = (yield session.authorize([self._interface])).get(
            self._interface
        )
        if self._required and provider is None:
            raise EarlyExit(self._whenDenied(self._interface, instance))
        # TODO: CSRF protection should probably go here
        return provider

    def finalize(self) -> None:
        """
        Nothing to finalize when registering.
        """
