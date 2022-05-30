from ._iform import ValidationError, ValueAbsent
from ._interfaces import IKleinRequest
from ._isession import (
    EarlyExit,
    IDependencyInjector,
    IRequestLifecycle,
    IRequiredParameter,
    ISession,
    ISessionProcurer,
    ISessionStore,
    ISimpleAccount,
    ISimpleAccountBinding,
    NoSuchSession,
    SessionMechanism,
    TooLateForCookies,
    TransactionEnded,
)


if TYPE_CHECKING:  # pragma: no cover
    from typing import Union

    from ._dihttp import RequestComponent, RequestURL
    from ._form import Field, FieldInjector, RenderableFormParam
    from ._isession import IRequestLifecycleT as _IRequestLifecycleT
    from ._session import Authorization, SessionProcurer
    from ._storage.memory import MemorySession, MemorySessionStore
    from ._storage.sql import (
        AccountSessionBinding,
        IPTrackingProcurer,
        SessionStore,
        SQLAccount,
    )

    ISessionStore = Union[_ISessionStore, MemorySessionStore, SessionStore]
    ISessionProcurer = Union[
        _ISessionProcurer, SessionProcurer, IPTrackingProcurer
    ]
    ISession = Union[_ISession, MemorySession]
    ISimpleAccount = Union[_ISimpleAccount, SQLAccount]
    ISimpleAccountBinding = Union[_ISimpleAccountBinding, AccountSessionBinding]
    IDependencyInjector = Union[
        _IDependencyInjector,
        Authorization,
        RenderableFormParam,
        FieldInjector,
        RequestURL,
        RequestComponent,
    ]
    IRequiredParameter = Union[
        _IRequiredParameter,
        Authorization,
        Field,
        RenderableFormParam,
        RequestURL,
        RequestComponent,
    ]
    IRequestLifecycle = _IRequestLifecycleT
else:
    ISession = _ISession
    ISessionStore = _ISessionStore
    ISimpleAccount = _ISimpleAccount
    ISessionProcurer = _ISessionProcurer
    ISimpleAccountBinding = _ISimpleAccountBinding
    IDependencyInjector = _IDependencyInjector
    IRequiredParameter = _IRequiredParameter
    IRequestLifecycle = _IRequestLifecycle

__all__ = (
    "EarlyExit",
    "IDependencyInjector",
    "IKleinRequest",
    "IRequestLifecycle",
    "IRequiredParameter",
    "ISession",
    "ISessionProcurer",
    "ISessionStore",
    "ISimpleAccount",
    "ISimpleAccountBinding",
    "NoSuchSession",
    "SessionMechanism",
    "TooLateForCookies",
    "TransactionEnded",
    "ValidationError",
    "ValueAbsent",
)
