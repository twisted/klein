from typing import TYPE_CHECKING

from ._iform import (
    ValidationError,
    ValueAbsent,
)
from ._interfaces import IKleinRequest
from ._isession import (
    EarlyExit,
    IDependencyInjector as _IDependencyInjector,
    IRequestLifecycle as _IRequestLifecycle,
    IRequiredParameter as _IRequiredParameter,
    ISession as _ISession,
    ISessionProcurer as _ISessionProcurer,
    ISessionStore as _ISessionStore,
    ISimpleAccount as _ISimpleAccount,
    ISimpleAccountBinding as _ISimpleAccountBinding,
    NoSuchSession,
    SessionMechanism,
    TooLateForCookies,
    TransactionEnded,
)

if TYPE_CHECKING:  # pragma: no cover
    from typing import Union

    from ._dihttp import RequestURL, RequestComponent
    from ._form import Field, RenderableFormParam, FieldInjector
    from ._requirer import RequestLifecycle
    from ._session import SessionProcurer, Authorization
    from .storage._memory import MemorySessionStore, MemorySession

    IDependencyInjector = Union[
        _IDependencyInjector,
        Authorization,
        FieldInjector,
        RenderableFormParam,
        RequestComponent,
        RequestURL,
    ]
    IRequestLifecycle = Union[_IRequestLifecycle, RequestLifecycle]
    IRequiredParameter = Union[
        _IRequiredParameter,
        Authorization,
        Field,
        RenderableFormParam,
        RequestComponent,
        RequestURL,
    ]
    ISession = Union[_ISession, MemorySession]
    ISessionProcurer = Union[_ISessionProcurer, SessionProcurer]
    ISessionStore = Union[_ISessionStore, MemorySessionStore]
    ISimpleAccount = _ISimpleAccount
    ISimpleAccountBinding = _ISimpleAccountBinding
else:
    IDependencyInjector = _IDependencyInjector
    IRequestLifecycle = _IRequestLifecycle
    IRequiredParameter = _IRequiredParameter
    ISession = _ISession
    ISessionProcurer = _ISessionProcurer
    ISessionStore = _ISessionStore
    ISimpleAccount = _ISimpleAccount
    ISimpleAccountBinding = _ISimpleAccountBinding

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
