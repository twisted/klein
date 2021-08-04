from typing import TYPE_CHECKING

from zope.interface import Attribute, Interface

from .._typing import ifmethod

if TYPE_CHECKING:  # pragma: no cover
    from twisted.internet.defer import Deferred
    from ..interfaces import ISessionStore, ISession
    from ._sql_generic import Transaction

    ISession, ISessionStore, Deferred, Transaction


class ISQLAuthorizer(Interface):
    """
    An add-on for an L{AlchimiaDataStore} that can populate data on an Alchimia
    session.
    """

    authorizationInterface = Attribute(
        """
        The interface or class for which a session can be authorized by this
        L{ISQLAuthorizer}.
        """
    )

    @ifmethod
    def authorizationForSession(sessionStore, transaction, session):
        # type: (ISessionStore, Transaction, ISession) -> Deferred
        """
        Get a data object that the session has access to.

        If necessary, load related data first.

        @param sessionStore: the store where the session is stored.
        @type sessionStore: L{ISessionStore}

        @param transaction: The transaction that loaded the session.
        @type transaction: L{klein.storage.sql.Transaction}

        @param session: The session that said this data will be attached to.
        @type session: L{ISession}

        @return: the object the session is authorized to access
        @rtype: a providier of C{self.authorizationInterface}, or a L{Deferred}
            firing the same.
        """
        # session_store is a _sql.SessionStore but it's not documented as such.
