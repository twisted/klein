
import attr

from zope.interface import implementer
from klein.interfaces import (
    ISessionProcurer, SessionMechanism, NoSuchSession, ISession
)
from twisted.internet.defer import inlineCallbacks, returnValue

@implementer(ISessionProcurer)
@attr.s
class SessionProcurer(object):
    """
    Session procurer.
    """
    _store = attr.ib()
    _request = attr.ib()

    _max_age = attr.ib(default=3600)
    _secure_cookie = attr.ib(default=b"Klein-Secure-Session")
    _insecure_cookie = attr.ib(default=b"Klein-INSECURE-Session")
    _cookie_domain = attr.ib(default=None)
    _cookie_path = attr.ib(default=b"/")

    _secure_auth_header = attr.ib(default=b"X-Auth-Token")
    _insecure_auth_header = attr.ib(default=b"X-Insecure-Session")


    @inlineCallbacks
    def procure_session(self, force_insecure=False, always_create=True):
        """
        Retrieve a session based on this request.
        """
        already_procured = ISession(self._request, None)
        if already_procured is not None:
            returnValue(already_procured)

        if self._request.isSecure():
            if force_insecure:
                auth_header = self._insecure_auth_header
                cookie_name = self._insecure_cookie
                sent_securely = False
            else:
                auth_header = self._secure_auth_header
                cookie_name = self._secure_cookie
                sent_securely = True
        else:
            # Have we inadvertently disclosed a secure token over an insecure
            # transport, for example, due to a buggy client?
            all_possible_sent_tokens = (
                sum([self._request.requestHeaders.getRawHeaders(header, [])
                     for header in [self._secure_auth_header,
                                    self._insecure_auth_header]], []) +
                [it for it in [self._request.getCookie(cookie)
                               for cookie in [self._secure_cookie,
                                              self._insecure_cookie]] if it]
            )
            # Does it seem like this check is expensive? It sure is! Don't want
            # to do it? Turn on your dang HTTPS!
            yield self._store.sent_insecurely(all_possible_sent_tokens)
            auth_header = self._insecure_auth_header
            cookie_name = self._insecure_cookie
            sent_securely = False
            # Fun future feature: honeypot that does this over HTTPS, but sets
            # isSecure() to return false because it serves up a cert for the
            # wrong hostname or an invalid cert, to keep API clients honest
            # about chain validation.
        session_id = self._request.getHeader(auth_header)
        if session_id is not None:
            mechanism = SessionMechanism.Header
        else:
            mechanism = SessionMechanism.Cookie
            session_id = self._request.getCookie(cookie_name)
        if session_id is not None:
            try:
                session = yield self._store.load_session(
                    session_id, sent_securely, mechanism
                )
            except NoSuchSession:
                if mechanism == SessionMechanism.Header:
                    raise
                session_id = None
        if session_id is None:
            if always_create:
                session = yield self._store.new_session(sent_securely,
                                                        mechanism)
            else:
                returnValue(None)
        if session_id != session.identifier:
            if self._request.startedWriting:
                raise ValueError("You tried initializing a cookie session too"
                                 " late in the request pipeline; the headers"
                                 " were already sent.")
            self._request.addCookie(
                cookie_name, session.identifier, max_age=self._max_age,
                domain=self._cookie_domain, path=self._cookie_path,
                secure=sent_securely, httpOnly=True,
            )
        if not force_insecure:
            # Do not cache the insecure session on the secure request, thanks.
            self._request.setComponent(ISession, session)
        returnValue(session)
