# -*- test-case-name: klein.test.test_session -*-

from typing import Any, Callable, Dict, Optional, Sequence, Type, Union, cast

import attr
from zope.interface import Interface, implementer

from twisted.internet.defer import inlineCallbacks
from twisted.python.components import Componentized
from twisted.python.reflect import qual
from twisted.web.http import UNAUTHORIZED
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource

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

    @inlineCallbacks
    def procureSession(
        self, request: IRequest, forceInsecure: bool = False
    ) -> Any:
        alreadyProcured = cast(Componentized, request).getComponent(ISession)
        if alreadyProcured is not None:
            if not forceInsecure or not request.isSecure():
                return alreadyProcured

        if request.isSecure():
            if forceInsecure:
                tokenHeader = self._insecureTokenHeader
                cookieName: Union[str, bytes] = self._insecureCookie
                sentSecurely = False
            else:
                tokenHeader = self._secureTokenHeader
                cookieName = self._secureCookie
                sentSecurely = True
        else:
            # Have we inadvertently disclosed a secure token over an insecure
            # transport, for example, due to a buggy client?
            allPossibleSentTokens: Sequence[str] = sum(
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
                ]
                if it
            ]
            # Does it seem like this check is expensive? It sure is! Don't want
            # to do it? Turn on your dang HTTPS!
            self._store.sentInsecurely(allPossibleSentTokens)
            tokenHeader = self._insecureTokenHeader
            cookieName = self._insecureCookie
            sentSecurely = False
            # Fun future feature: honeypot that does this over HTTPS, but sets
            # isSecure() to return false because it serves up a cert for the
            # wrong hostname or an invalid cert, to keep API clients honest
            # about chain validation.
        sentHeader = (request.getHeader(tokenHeader) or b"").decode("utf-8")
        sentCookie = (request.getCookie(cookieName) or b"").decode("utf-8")
        if sentHeader:
            mechanism = SessionMechanism.Header
        else:
            mechanism = SessionMechanism.Cookie
        if not (sentHeader or sentCookie):
            session = None
        else:
            try:
                session = yield self._store.loadSession(
                    sentHeader or sentCookie, sentSecurely, mechanism
                )
            except NoSuchSession:
                if mechanism == SessionMechanism.Header:
                    raise
                session = None
        if mechanism == SessionMechanism.Cookie and (
            session is None or session.identifier != sentCookie
        ):
            if session is None:
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
                        "{method} request.".format(
                            method=request.method.decode("ascii")
                        )
                    )
                if not self._setCookieOnGET:
                    # We don't have a session ID at all, and we're not allowed
                    # by policy to set a cookie on the client.
                    raise NoSuchSession(
                        "Cannot auto-initialize a session for this request."
                    )
                session = yield self._store.newSession(sentSecurely, mechanism)
            identifierInCookie = session.identifier
            if not isinstance(identifierInCookie, str):
                identifierInCookie = identifierInCookie.encode("ascii")
            if not isinstance(cookieName, str):
                cookieName = cookieName.decode("ascii")
            request.addCookie(  # type: ignore[call-arg]
                cookieName,
                identifierInCookie,
                max_age=str(self._maxAge),
                domain=self._cookieDomain,
                path=self._cookiePath,
                secure=sentSecurely,
                httpOnly=True,
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
