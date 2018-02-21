from __future__ import absolute_import, division

from typing import TYPE_CHECKING

from twisted.python.constants import NamedConstant, Names

from zope.interface import Attribute, Interface

if TYPE_CHECKING:
    ifmethod = staticmethod
else:
    def ifmethod(method):
        return method

class IKleinRequest(Interface):
    branch_segments = Attribute("Segments consumed by a branch route.")
    mapper = Attribute("L{werkzeug.routing.MapAdapter}")

    def url_for(
        self, endpoint, values=None, method=None,
        force_external=False, append_unknown=True,
    ):
        """
        L{werkzeug.routing.MapAdapter.build}
        """

class NoSuchSession(Exception):
    """
    No such session could be found.
    """


class TooLateForCookies(Exception):
    """
    It's too late to set a cookie.
    """


class TransactionEnded(Exception):
    """
    Exception raised when.
    """



class _ISessionStore(Interface):
    """
    Backing storage for sessions.
    """

    def newSession(isConfidential, authenticatedBy):
        """
        Create a new L{ISession}.

        @return: a new session with a new identifier.
        @rtype: L{Deferred} firing with L{ISession}.
        """


    def loadSession(identifier, isConfidential, authenticatedBy):
        """
        Load a session given the given identifier and security properties.

        As an optimization for session stores where the back-end can generate
        session identifiers when the presented one is not found in the same
        round-trip to a data store, this method may return a L{Session} object
        with an C{identifier} attribute that does not match C{identifier}.
        However, please keep in mind when implementing L{ISessionStore} that
        this behavior is only necessary for requests where C{authenticatedBy}
        is L{SessionMechanism.Cookie}; an unauthenticated
        L{SessionMechanism.Header} session is from an API client and its
        session should be valid already.

        @return: an existing session with the given identifier.
        @rtype: L{Deferred} firing with L{ISession} or failing with
            L{NoSuchSession}.
        """


    def sentInsecurely(identifiers):
        """
        The transport layer has detected that the given identifiers have been
        sent over an unauthenticated transport.
        """



class ISimpleAccountBinding(Interface):
    """
    Data-store agnostic account / session binding manipulation API for "simple"
    accounts - i.e. those using username, password, and email address as a
    method to authenticate a user.

    This goes into a user-authentication-capable L{ISession} object's C{data}
    attribute as a component.
    """

    def log_in(username, password):
        """
        Attach the session this is a component of to an account with the given
        username and password, if the given username and password correctly
        authenticate a principal.
        """

    def authenticated_accounts():
        """
        Retrieve the accounts currently associated with the session this is a
        component of.

        @return: L{Deferred} firing with a L{list} of L{ISimpleAccount}.
        """

    def log_out():
        """
        Disassociate the session this is a component of from any accounts it's
        logged in to.
        """

    def createAccount(username, email, password):
        """
        Create a new account with the given username, email and password.
        """



class ISimpleAccount(Interface):
    """
    Data-store agnostic account interface.
    """

    username = Attribute(
        """
        Unicode username.
        """
    )

    accountID = Attribute(
        """
        Unicode account-ID.
        """
    )

    def add_session(self, session):
        """
        Add the given session to this account.
        """


    def change_password(self, new_password):
        """
        Change the password of this account.
        """



class ISQLSchemaComponent(Interface):
    """
    A component of an SQL schema.
    """

    @ifmethod
    def initialize_schema(transaction):
        """
        Add the relevant tables to the database.
        """



class ISQLAuthorizer(Interface):
    """
    An add-on for an L{AlchimiaDataStore} that can populate data on an Alchimia
    session.
    """

    authzn_for = Attribute(
        """
        The interface or class for which a session can be authorized by this
        L{ISQLAuthorizer}.
        """
    )

    def authzn_for_session(session_store, transaction, session):
        """
        Get a data object that the session has access to.

        If necessary, load related data first.

        @param session_store: the store where the session is stored.
        @type session_store: L{AlchimiaSessionStore}

        @param transaction: The transaction that loaded the session.
        @type transaction: L{klein.storage.sql.Transaction}

        @param session: The session that said this data will be attached to.
        @type session: L{ISession}

        @return: the object the session is authorized to access
        @rtype: a providier of C{self.authzn_for}, or a L{Deferred} firing the
            same.
        """



class _ISessionProcurer(Interface):
    """
    An L{ISessionProcurer} wraps an L{ISessionStore} and can procure sessions
    that store, given HTTP request objects.
    """

    def procureSession(self, request, forceInsecure=False,
                       alwaysCreate=True):
        """
        Retrieve a session using whatever technique is necessary.

        If the request already identifies an existing session in the store,
        retrieve it.  If not, create a new session and retrieve that.

        @param request: The request to procure a session from.
        @type request:  L{twisted.web.server.Request}

        @param forceInsecure: Even if the request was transmitted securely
            (i.e. over HTTPS), retrieve the session that would be used by the
            same browser if it were sending an insecure (i.e. over HTTP)
            request; by default, this is False, and the session's security will
            match that of the request.
        @type forceInsecure: L{bool}

        @param alwaysCreate: Create a session if one is not associated with
            the request.
        @param alwaysCreate: L{bool}

        @raise TooLateForCookies: if the request bound to this procurer has
            already sent the headers and therefore we can no longer set a
            cookie, and we need to set a cookie.

        @return: a new or loaded session from this the a L{Deferred} that fires
            with an L{ISession} provider.
        @rtype: L{Session}
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
        L{unicode} identifying a session.

        This value should be:

            1. I{unique} - no two sessions have the same identifier

            2. I{unpredictable} - no one but the receipient of the session
               should be able to guess what it is

            3. I{opaque} - it should contain no interesting information
        """
    )

    isConfidential = Attribute(
        """
        A L{bool} indicating whether this session mechanism transmitted over an
        encrypted transport, i.e., HTTPS.  If C{True}, this means that this
        session can be used for sensitive information; otherwise, the
        information contained in it should be considered to be available to
        attackers.
        """
    )

    authenticatedBy = Attribute(
        """
        A L{SessionMechanism} indicating what mechanism was used to
        authenticate this session.
        """
    )


    def authorize(interfaces):
        """
        Retrieve other objects from this session.

        This method is how you can retrieve application-specific objects from
        the general-purpose session; define interfaces for each facet of
        something accessible to a session, then pass it here and to the
        L{ISessionStore} implementation you're using.

        @param interfaces: A list of interfaces.
        @type interfaces: L{iterable} of
            L{zope.interface.interfaces.IInterface}

        @return: all of the providers that could be retrieved from the session.
        @rtype: L{Deferred} firing with L{dict} mapping
            L{zope.interface.interfaces.IInterface} to providers of each
            interface.
        """

if TYPE_CHECKING:
    from ._storage.memory import MemorySessionStore
    from ._storage.sql import AlchimiaSessionStore
    from ._session import SessionProcurer
    from typing import Union

    ISessionStore = Union[_ISessionStore, MemorySessionStore,
                          AlchimiaSessionStore]
    ISessionProcurer = Union[_ISessionProcurer, SessionProcurer]
else:
    ISessionStore = _ISessionStore
    ISessionProcurer = _ISessionProcurer
