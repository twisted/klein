
from typing import Any, TYPE_CHECKING

import attr

try:
    from constantly import NamedConstant, Names
except ImportError:             # pragma: no cover
    from twisted.python.constants import NamedConstant, Names

from zope.interface import Attribute, Interface

from ._typing import ifmethod

if TYPE_CHECKING:               # pragma: no cover
    from twisted.internet.defer import Deferred
    from twisted.python.components import Componentized
    from typing import Dict, Iterable, List, Text, Type, Sequence
    from twisted.web.iweb import IRequest
    from zope.interface.interfaces import IInterface

    Deferred, Text, Componentized, Sequence, IRequest, List, Type
    Iterable, IInterface, Dict

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



class ISessionStore(Interface):
    """
    Backing storage for sessions.
    """

    @ifmethod
    def newSession(isConfidential, authenticatedBy):
        # type: (bool, SessionMechanism) -> Deferred
        """
        Create a new L{ISession}.

        @return: a new session with a new identifier.
        @rtype: L{Deferred} firing with L{ISession}.
        """


    @ifmethod
    def loadSession(identifier, isConfidential, authenticatedBy):
        # type: (Text, bool, SessionMechanism) -> Deferred
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


    @ifmethod
    def sentInsecurely(identifiers):
        # type: (Sequence[Text]) -> None
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

    @ifmethod
    def bindIfCredentialsMatch(username, password):
        # type: (Text, Text) -> None
        """
        Attach the session this is a component of to an account with the given
        username and password, if the given username and password correctly
        authenticate a principal.
        """

    @ifmethod
    def boundAccounts():
        # type: () -> Deferred
        """
        Retrieve the accounts currently associated with the session this is a
        component of.

        @return: L{Deferred} firing with a L{list} of L{ISimpleAccount}.
        """

    @ifmethod
    def unbindThisSession():
        # type: () -> None
        """
        Disassociate the session this is a component of from any accounts it's
        logged in to.
        """

    @ifmethod
    def createAccount(username, email, password):
        # type: (Text, Text, Text) -> None
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

    def bindSession(self, session):
        # type: (ISession) -> None
        """
        Bind the given session to this account; i.e. authorize the given
        session to act on behalf of this account.
        """


    def changePassword(self, newPassword):
        # type: (Text) -> None
        """
        Change the password of this account.
        """



class ISessionProcurer(Interface):
    """
    An L{ISessionProcurer} wraps an L{ISessionStore} and can procure sessions
    that store, given HTTP request objects.
    """

    def procureSession(self, request, forceInsecure=False):
        # type: (IRequest, bool, bool) -> Deferred
        """
        Retrieve a session using whatever technique is necessary.

        If the request already identifies an existing session in the store,
        retrieve it.  If not, create a new session and retrieve that.

        @param request: The request to procure a session from.
        @type request: L{twisted.web.server.Request}

        @param forceInsecure: Even if the request was transmitted securely
            (i.e. over HTTPS), retrieve the session that would be used by the
            same browser if it were sending an insecure (i.e. over HTTP)
            request; by default, this is False, and the session's security will
            match that of the request.
        @type forceInsecure: L{bool}

        @return: a L{Deferred} that:

                - fires with an L{ISession} provider if the request describes
                  an existing, valid session, or, if the intersection of the
                  data in the request and the configuration of this
                  L{ISessionProcurer} allow for a cookie to be set immediately,
                  or

                - fails with L{NoSuchSession} if the request is unable to
                  negotiate a session based on the current request: this is
                  generally if the client is trying to use header-based
                  authentication (and therefore does not want a new cookie set)
                  or if this procurer is configured not to automatically create
                  new sessions on the fly, or

                - fails with L{TooLateForCookies} if the request bound to this
                  procurer has already sent the headers and therefore we can no
                  longer set a cookie, and we need to set a cookie.

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


    @ifmethod
    def authorize(interfaces):
        # type: (Iterable[IInterface]) -> Deferred
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
            interface.  Interfaces which cannot be authorized will not be
            present as keys in this dictionary.
        """


class IDependencyInjector(Interface):
    """
    An injector for a given dependency.
    """

    @ifmethod
    def injectValue(instance, request, routeParams):
        # type: (Any, IRequest, Dict[str, Any]) -> Any
        """
        Return a value to be injected into the parameter name specified by the
        IRequiredParameter.  This may return a Deferred, or an object, or an
        object directly providing the relevant interface.

        @param instance: The instance to which the Klein router processing this
            request is bound.

        @param request: The request being processed.

        @param routeParams: A (read-only) copy of the the arguments passed to
            the route by the layer below dependency injection (for example, URL
            parameters).
        """

    @ifmethod
    def finalize():
        # type: () -> None
        """
        Finalize this injector before allowing the route to be created.

        Finalization generally includes:

            - attaching any hooks to the request lifecycle object that need to
              be run before/after each request

            - attaching any finalized component objects to the
              injectionComponents originally passed along to the
              IRequiredParameter that created this IDependencyInjector.

        """


class IRequiredParameter(Interface):
    """
    A declaration that a given Python parameter is required to satisfy a given
    dependency at request-handling time.
    """

    @ifmethod
    def registerInjector(injectionComponents, parameterName, lifecycle):
        # type: (Componentized, str, IRequestLifecycleT) -> IDependencyInjector
        """
        Register the given injector at method-decoration time, informing it of
        its Python parameter name.

        @note: this happens at I{route definition} time, after all other
            injectors have been registered by
            L{IRequiredParameter.registerInjector}.

        @param lifecycle: An L{IRequestLifecycle} provider which contains hooks
            that will be run before and after each request.  If this injector
            has shared per-request dependencies that need to be executed before
            or after the request is processed, this method should attach them
            to those lists.  These hooks are supplied here rather than relying
            on C{injectValue} to run the requisite logic each time so that
            DependencyInjectors may cooperate on logic that needs to be
            duplicated, such as provisioning a session.
        """



class IRequestLifecycle(Interface):
    """
    Interface for adding hooks to the phases of a request's lifecycle.
    """


if TYPE_CHECKING:               # pragma: no cover
    from typing import Union
    from ._requirer import RequestLifecycle
    IRequestLifecycleT = Union[RequestLifecycle, IRequestLifecycle]


@attr.s
class EarlyExit(Exception):
    """
    An L{EarlyExit} may be raised by any of the code that runs in the
    before-request dependency injection code path when using
    L{klein.Requirer.require}.

    @ivar alternateReturnValue: The return value which should instead be
        supplied as the route's response.
    @type alternateReturnValue: Any type that's acceptable to return from a
        Klein route.
    """
    alternateReturnValue = attr.ib(type=Any)
