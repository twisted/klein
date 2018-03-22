from typing import TYPE_CHECKING

from ._interfaces import (
    IKleinRequest,
    ISQLAuthorizer,
    ISession as _ISession,
    ISessionProcurer as _ISessionProcurer,
    ISessionStore as _ISessionStore,
    ISimpleAccount as _ISimpleAccount,
    ISimpleAccountBinding,
    IDependencyInjector,
    IRequiredParameter,
    IRequestLifecycle,
    EarlyExit,
    NoSuchSession,
    SessionMechanism,
    TooLateForCookies,
    TransactionEnded,
)


if TYPE_CHECKING:
    from ._storage.memory import MemorySessionStore, MemorySession
    from ._storage.sql import SessionStore, SQLAccount, IPTrackingProcurer
    from ._session import SessionProcurer
    from typing import Union

    ISessionStore = Union[_ISessionStore, MemorySessionStore,
                          SessionStore]
    ISessionProcurer = Union[_ISessionProcurer, SessionProcurer,
                             IPTrackingProcurer]
    ISession = Union[_ISession, MemorySession]
    ISimpleAccount = Union[_ISimpleAccount, SQLAccount]
else:
    ISession = _ISession
    ISessionStore = _ISessionStore
    ISimpleAccount = _ISimpleAccount
    ISessionProcurer = _ISessionProcurer

__all__ = (
    "IKleinRequest",
    "NoSuchSession",
    "TooLateForCookies",
    "TransactionEnded",
    "ISessionStore",
    "ISimpleAccountBinding",
    "ISimpleAccount",
    "ISessionProcurer",
    "ISQLAuthorizer",
    "IDependencyInjector",
    "IRequiredParameter",
    "IRequestLifecycle",
    "EarlyExit",
    "SessionMechanism",
    "ISession",
)
