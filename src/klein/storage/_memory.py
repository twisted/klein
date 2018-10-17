# -*- test-case-name: klein.test.test_memory -*-
from binascii import hexlify
from os import urandom
from typing import Any, Callable, Dict, List, TYPE_CHECKING, Text, cast

import attr
from attr import Factory

from twisted.internet.defer import Deferred, fail, succeed
from twisted.python.components import Componentized

from zope.interface import implementer
from zope.interface.interfaces import IInterface

from klein.interfaces import (
    ISession, ISessionStore, NoSuchSession, SessionMechanism
)

if TYPE_CHECKING:               # pragma: no cover
    List, Deferred, IInterface, Any, Callable, Dict, SessionMechanism

_authCB = Callable[[IInterface, ISession, Componentized], Any]

@implementer(ISession)
@attr.s
class MemorySession(object):
    """
    An in-memory session.
    """

    identifier = attr.ib(type=Text)
    isConfidential = attr.ib(type=bool)
    authenticatedBy = attr.ib(type=SessionMechanism)
    _authorizationCallback = attr.ib(type=_authCB)
    _components = attr.ib(default=Factory(Componentized),
                          type=Componentized)

    def authorize(self, interfaces):
        # type: (List[IInterface]) -> Deferred
        """
        Authorize each interface by calling back to the session store's
        authorization callback.
        """
        result = {}
        for interface in interfaces:
            provider = self._authorizationCallback(interface, self,
                                                   self._components)
            if provider is not None:
                result[interface] = provider
        return succeed(result)


class _MemoryAuthorizerFunction(object):
    """
    Type shadow for function with the given attribute.
    """
    __memoryAuthInterface__ = None  # type: IInterface

    def __call__(self, interface, session, data):
        # type: (IInterface, ISession, Componentized) -> Any
        """
        Return a provider of the given interface.
        """

_authFn = Callable[[IInterface, ISession, Componentized], Any]

def declareMemoryAuthorizer(forInterface):
    # type: (IInterface) -> Callable[[Callable], _MemoryAuthorizerFunction]
    """
    Declare that the decorated function is an authorizer usable with a memory
    session store.
    """
    def decorate(decoratee):
        # type: (_authFn) -> _MemoryAuthorizerFunction
        decoratee = cast(_MemoryAuthorizerFunction, decoratee)
        decoratee.__memoryAuthInterface__ = forInterface
        return decoratee
    return decorate

def _noAuthorization(interface, session, data):
    # type: (IInterface, ISession, Componentized) -> None
    return None

@implementer(ISessionStore)
@attr.s
class MemorySessionStore(object):
    authorizationCallback = attr.ib(
        type=_authFn,
        default=_noAuthorization
    )
    _secureStorage = attr.ib(type=Dict[str, Any],
                             default=cast(Dict[str, Any], Factory(dict)))
    _insecureStorage = attr.ib(type=Dict[str, Any],
                               default=cast(Dict[str, Any], Factory(dict)))

    @classmethod
    def fromAuthorizers(cls, authorizers):
        # type: (List[_MemoryAuthorizerFunction]) -> MemorySessionStore
        """
        Create a L{MemorySessionStore} from a collection of callbacks which can
        do authorization.
        """
        interfaceToCallable = {}
        for authorizer in authorizers:
            specifiedInterface = authorizer.__memoryAuthInterface__
            interfaceToCallable[specifiedInterface] = authorizer

        def authorizationCallback(interface, session, data):
            # type: (IInterface, ISession, Componentized) -> Any
            return interfaceToCallable.get(interface, _noAuthorization)(
                interface, session, data
            )
        return cls(authorizationCallback)


    def _storage(self, isConfidential):
        # type: (bool) -> Dict[str, Any]
        """
        Return the storage appropriate to the isConfidential flag.
        """
        if isConfidential:
            return self._secureStorage
        else:
            return self._insecureStorage


    def newSession(self, isConfidential, authenticatedBy):
        # type: (bool, SessionMechanism) -> Deferred
        storage = self._storage(isConfidential)
        identifier = hexlify(urandom(32)).decode('ascii')
        session = MemorySession(identifier, isConfidential, authenticatedBy,
                                self.authorizationCallback)
        storage[identifier] = session
        return succeed(session)


    def loadSession(self, identifier, isConfidential, authenticatedBy):
        # type: (str, bool, SessionMechanism) -> Deferred
        storage = self._storage(isConfidential)
        if identifier in storage:
            return succeed(storage[identifier])
        else:
            return fail(NoSuchSession(
                u"Session not found in memory store {id!r}"
                .format(id=identifier)
            ))


    def sentInsecurely(self, tokens):
        # type: (List[str]) -> None
        return
