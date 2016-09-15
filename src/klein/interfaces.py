from __future__ import absolute_import, division

from zope.interface import Interface, Attribute

from twisted.python.constants import Names, NamedConstant


class IKleinRequest(Interface):
    branch_segments = Attribute("Segments consumed by a branch route.")
    mapper = Attribute("L{werkzeug.routing.MapAdapter}")

    def url_for(self, endpoint, values=None, method=None, force_external=False, append_unknown=True):
        """
        L{werkzeug.routing.MapAdapter.build}
        """



class NoSuchSession(Exception):
    """
    No such session could be found.
    """



class ISessionStore(Interface):
    """
    Backing storage for sessions.
    """

    def new_session(is_confidential, authenticated_by):
        """
        Create a new L{ISession}.

        @return: a new session with a new identifier.
        @rtype: L{Deferred} firing with L{ISession}.
        """


    def load_session(identifier, is_confidential, authenticated_by):
        """
        Load a session given the given identifier and security properties.

        As an optimization for session stores where the back-end can generate
        session identifiers when the presented one is not found in the same
        round-trip to a data store, this method may return a L{Session} object
        with an C{identifier} attribute that does not match C{identifier}.
        However, please keep in mind when implementing L{ISessionStore} that
        this behavior is only necessary for requests where C{authenticated_by}
        is L{SessionMechanism.Cookie}; an unauthenticated
        L{SessionMechanism.Header} session is from an API client and its
        session should be valid already.

        @return: an existing session with the given identifier.
        @rtype: L{Deferred} firing with L{ISession} or failing with
            L{NoSuchSession}.
        """


    def sent_insecurely(identifiers):
        """
        The transport layer has detected that the given identifiers have been
        sent over an unauthenticated transport.
        """



class ISessionProcurer(Interface):
    """
    An L{ISessionProcurer} binds an L{ISessionStore} to a specific L{request
    <twisted.web.server.Request>} and can procure a session from that request.
    """

    def procure_session(force_insecure):
        """
        Retrieve a session using whatever technique is necessary.

        If the request already identifies an existing session in the store,
        retrieve it.  If not, create a new session and retrieve that.

        @return: a L{Deferred} that fires with an L{ISession} provider.
        """


class SessionMechanism(Names):
    """
    Mechanisms which can be used to identify and authenticate a session.

    @cvar Cookie: The Cookie session mechanism involves looking up the session
        identifier via an HTTP cookie.  Session objects retrieved via this
        mechanism may be vulnerable to U{CSRF attacks
        <https://www.owasp.org/index.php/Cross-Site_Request_Forgery_(CSRF)>}
        and therefore must have CSRF protections applied to them.

    @cvar Header: The Header mechanism retrieves the session identifier via a
        separate header such as C{"X-Auth-Token"}.  Since a different-origin
        site in a browser can easily send a form submission including cookies,
        but I{can't} easily put stuff into other arbitrary headers, this does
        not require additional protections.
    """

    Cookie = NamedConstant()
    Header = NamedConstant()



class ISession(Interface):
    """
    An L{ISession} provider contains an identifier for the session, information
    about how the session was negotiated with the client software, and
    """

    identifier = Attribute(
        """
        L{bytes} identifying a session.

        This value should be:

            1. I{unique} - no two sessions have the same identifier

            2. I{unpredictable} - no one but the receipient of the session
               should be able to guess what it is

            3. I{opaque} - it should contain no interesting information
        """
    )

    is_confidential = Attribute(
        """
        A L{bool} indicating whether this session mechanism transmitted over an
        encrypted transport, i.e., HTTPS.  If C{True}, this means that this
        session can be used for sensitive information; otherwise, the
        information contained in it should be considered to be available to
        attackers.
        """
    )

    authenticated_by = Attribute(
        """
        A L{SessionMechanism} indicating what mechanism was used to
        authenticate this session.
        """
    )

    data = Attribute(
        """
        A L{Componentized} representing application-specific data loaded for
        this session.
        """
    )
