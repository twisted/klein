# -*- test-case-name: klein.test.test_memory -*-
from binascii import hexlify
from os import urandom
from typing import Any, Callable, Dict, Iterable, Type, cast

import attr
from zope.interface import Interface, implementer

from twisted.internet.defer import Deferred, fail, succeed
from twisted.python.components import Componentized

from klein.interfaces import (
    ISession,
    ISessionStore,
    NoSuchSession,
    SessionMechanism,
)


_authCB = Callable[[Type[Interface], ISession, Componentized], Any]


@implementer(ISession)
@attr.s(auto_attribs=True)
class MemorySession:
    """
    An in-memory session.
    """

    identifier: str
    isConfidential: bool
    authenticatedBy: SessionMechanism
    _authorizationCallback: _authCB
    _components: Componentized = attr.ib(factory=Componentized)

    def authorize(self, interfaces: Iterable[Type[Interface]]) -> Deferred:
        """
        Authorize each interface by calling back to the session store's
        authorization callback.
        """
        result = {}
        for interface in interfaces:
            provider = self._authorizationCallback(
                interface, self, self._components
            )
            if provider is not None:
                result[interface] = provider
        return succeed(result)


class _MemoryAuthorizerFunction:
    """
    Type shadow for function with the given attribute.
    """

    __memoryAuthInterface__: Type[Interface] = None  # type: ignore[assignment]

    def __call__(
        self, interface: Type[Interface], session: ISession, data: Componentized
    ) -> Any:
        """
        Return a provider of the given interface.
        """


_authFn = Callable[[Type[Interface], ISession, Componentized], Any]


def declareMemoryAuthorizer(
    forInterface: Type[Interface],
) -> Callable[[Callable], _MemoryAuthorizerFunction]:
    """
    Declare that the decorated function is an authorizer usable with a memory
    session store.
    """

    def decorate(decoratee: _authFn) -> _MemoryAuthorizerFunction:
        decoratee = cast(_MemoryAuthorizerFunction, decoratee)
        decoratee.__memoryAuthInterface__ = forInterface
        return decoratee

    return decorate


def _noAuthorization(
    interface: Type[Interface], session: ISession, data: Componentized
) -> None:
    return None


@implementer(ISessionStore)
@attr.s(auto_attribs=True)
class MemorySessionStore:
    authorizationCallback: _authFn = _noAuthorization
    _secureStorage: Dict[str, Any] = attr.ib(factory=dict)
    _insecureStorage: Dict[str, Any] = attr.ib(factory=dict)

    @classmethod
    def fromAuthorizers(
        cls, authorizers: Iterable[_MemoryAuthorizerFunction]
    ) -> "MemorySessionStore":
        """
        Create a L{MemorySessionStore} from a collection of callbacks which can
        do authorization.
        """
        interfaceToCallable = {}
        for authorizer in authorizers:
            assert authorizer.__memoryAuthInterface__ is not None
            specifiedInterface = authorizer.__memoryAuthInterface__
            interfaceToCallable[specifiedInterface] = authorizer

        def authorizationCallback(
            interface: Type[Interface], session: ISession, data: Componentized
        ) -> Any:
            return interfaceToCallable.get(interface, _noAuthorization)(
                interface, session, data
            )

        return cls(authorizationCallback)

    def _storage(self, isConfidential: bool) -> Dict[str, Any]:
        """
        Return the storage appropriate to the isConfidential flag.
        """
        if isConfidential:
            return self._secureStorage
        else:
            return self._insecureStorage

    def newSession(
        self, isConfidential: bool, authenticatedBy: SessionMechanism
    ) -> Deferred:
        storage = self._storage(isConfidential)
        identifier = hexlify(urandom(32)).decode("ascii")
        session = MemorySession(
            identifier,
            isConfidential,
            authenticatedBy,
            self.authorizationCallback,
        )
        storage[identifier] = session
        return succeed(session)

    def loadSession(
        self,
        identifier: str,
        isConfidential: bool,
        authenticatedBy: SessionMechanism,
    ) -> Deferred:
        storage = self._storage(isConfidential)
        if identifier in storage:
            return succeed(storage[identifier])
        else:
            return fail(
                NoSuchSession(
                    "Session not found in memory store {id!r}".format(
                        id=identifier
                    )
                )
            )

    def sentInsecurely(self, tokens: Iterable[str]) -> None:
        return
