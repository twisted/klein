
import attr

from zope.interface import implementer
from .interfaces import (
    ISessionProcurer, SessionMechanism, NoSuchSession, ISession,
    TooLateForCookies
)
from ._decorators import modified, bindable
from .app import _call

from twisted.internet.defer import inlineCallbacks, returnValue

@implementer(ISessionProcurer)
@attr.s
class SessionProcurer(object):
    """
    A L{SessionProcurer} procures a session from a request and a store.

    @ivar _store: The session store to procure a session from.
    @type _store: L{klein.interfaces.ISessionStore}

    @ivar _max_age: The maximum age (in seconds) of the session cookie.
    @type _max_age: L{int}

    @ivar _secure_cookie: The name of the cookie to use for sessions protected
        with TLS (i.e. HTTPS).
    @type _secure_cookie: L{bytes}

    @ivar _insecure_cookie: The name of the cookie to use for sessions I{not}
        protected with TLS (i.e. HTTP).
    @type _insecure_cookie: L{bytes}

    @ivar _cookie_domain: If set, the domain name to restrict the session
        cookie to.
    @type _cookie_domain: L{None} or L{bytes}

    @ivar _cookie_path: If set, the URL path to restrict the session cookie to.
    @type _cookie_path: L{bytes}

    @ivar _secure_token_header: The name of the HTTPS header to try to extract
        a session token from; API clients should use this header, rather than a
        cookie.
    @type _secure_token_header: L{bytes}

    @ivar _insecure_token_header: The name of the HTTP header to try to extract
        a session token from; API clients should use this header, rather than a
        cookie.
    @type _insecure_token_header: L{bytes}
    """

    _store = attr.ib()

    _max_age = attr.ib(default=3600)
    _secure_cookie = attr.ib(default=b"Klein-Secure-Session")
    _insecure_cookie = attr.ib(default=b"Klein-INSECURE-Session")
    _cookie_domain = attr.ib(default=None)
    _cookie_path = attr.ib(default=b"/")

    _secure_token_header = attr.ib(default=b"X-Auth-Token")
    _insecure_token_header = attr.ib(default=b"X-INSECURE-Auth-Token")


    @inlineCallbacks
    def procure_session(self, request, force_insecure=False,
                        always_create=True):
        already_procured = ISession(request, None)
        if already_procured is not None:
            print("returning already procured", already_procured)
            returnValue(already_procured)

        if request.isSecure():
            if force_insecure:
                token_header = self._insecure_token_header
                cookie_name = self._insecure_cookie
                sent_securely = False
            else:
                token_header = self._secure_token_header
                cookie_name = self._secure_cookie
                sent_securely = True
        else:
            # Have we inadvertently disclosed a secure token over an insecure
            # transport, for example, due to a buggy client?
            all_possible_sent_tokens = (
                sum([request.requestHeaders.getRawHeaders(header, [])
                     for header in [self._secure_token_header,
                                    self._insecure_token_header]], []) +
                [it for it in [request.getCookie(cookie)
                               for cookie in [self._secure_cookie,
                                              self._insecure_cookie]] if it]
            )
            # Does it seem like this check is expensive? It sure is! Don't want
            # to do it? Turn on your dang HTTPS!
            yield self._store.sent_insecurely(all_possible_sent_tokens)
            token_header = self._insecure_token_header
            cookie_name = self._insecure_cookie
            sent_securely = False
            # Fun future feature: honeypot that does this over HTTPS, but sets
            # isSecure() to return false because it serves up a cert for the
            # wrong hostname or an invalid cert, to keep API clients honest
            # about chain validation.
        session_id = request.getHeader(token_header)
        if session_id is not None:
            mechanism = SessionMechanism.Header
        else:
            mechanism = SessionMechanism.Cookie
            session_id = request.getCookie(cookie_name)
        if session_id is not None:
            try:
                print("loading session", session_id)
                session = yield self._store.load_session(
                    session_id, sent_securely, mechanism
                )
                print("loaded session", session)
            except NoSuchSession:
                if mechanism == SessionMechanism.Header:
                    raise
                session_id = None
        else:
            print("NO COOKIE?", request)
        if session_id is None:
            if always_create:
                if request.startedWriting:
                    # At this point, if the mechanism is Header, we either have
                    # a valid session or we bailed after NoSuchSession above.
                    raise TooLateForCookies(
                        "You tried initializing a cookie-based session too"
                        " late in the request pipeline; the headers"
                        " were already sent."
                    )
                session = yield self._store.new_session(sent_securely,
                                                        mechanism)
            else:
                print("returning none because too late for cookie")
                returnValue(None)
        if session_id != session.identifier:
            if request.startedWriting:
                raise TooLateForCookies(
                    "You tried changing a session ID to a new session ID too"
                    " late in the request pipeline; the headers were already"
                    " sent."
                )
            request.addCookie(
                cookie_name, session.identifier, max_age=self._max_age,
                domain=self._cookie_domain, path=self._cookie_path,
                secure=sent_securely, httpOnly=True,
            )
        if not force_insecure:
            # Do not cache the insecure session on the secure request, thanks.
            request.setComponent(ISession, session)
        print("returning", session, "at end")
        returnValue(session)



def requirer(procure_procurer):
    def requires(route, **kw):
        def toroute(thunk):
            # FIXME: this should probably inspect the signature of 'thunk' to
            # see if it has default arguments, rather than relying upon people
            # to pass in Optional instances
            optified = dict([(k, Required.maybe(v)) for k, v in kw.items()])
            any_required = any(v._required for v in optified.values())
            @modified("requirer", thunk, route)
            @bindable
            @inlineCallbacks
            def routed(instance, request, *args, **kwargs):
                newkw = kwargs.copy()
                procu = _call(instance, procure_procurer)
                print("procu", procu)
                print("anyreq?", any_required)
                session = yield (procu.procure_session(
                    request, always_create=any_required)
                )
                print("IS-SESSION???", session)
                values = ({} if session is None else
                          (yield session.authorize(
                              [o._interface for o in optified.values()]
                          )))
                for k, v in optified.items():
                    print("retrieving", k, "using", v, "from", values)
                    oneval = v.retrieve(values)
                    print("got", oneval)
                    newkw[k] = oneval
                returnValue((yield _call(instance, thunk, request,
                                         *args, **newkw)))
        return toroute
    return requires



@attr.s
class Optional(object):
    _interface = attr.ib()
    _required = False
    def retrieve(self, dict):
        return dict.get(self._interface, None)
@attr.s
class Required(object):
    _interface = attr.ib()
    _required = True

    @classmethod
    def maybe(cls, it):
        if isinstance(it, (Optional, Required)):
            return it
        return cls(it)

    def retrieve(self, dict):
        return dict[self._interface]
