# -*- test-case-name: klein.test.test_memory -*-
from binascii import hexlify
from os import urandom

import attr
from attr import Factory

from twisted.internet.defer import fail, succeed, Deferred
from twisted.python.components import Componentized

from zope.interface import implementer, IInterface

from klein import SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession, SessionMechanism
SessionMechanism
from typing import List, TYPE_CHECKING, Any, Callable, cast, Dict
if TYPE_CHECKING:
    List, Deferred, IInterface, Any, Callable, Dict


@implementer(ISession)
@attr.s
class MemorySession(object):
    """
    An in-memory session.
    """

    identifier = attr.ib()
    isConfidential = attr.ib()
    authenticatedBy = attr.ib()
    _authorizationCallback = attr.ib()
    _components = attr.ib(default=Factory(Componentized))

    if TYPE_CHECKING:
        def __init__(self, identifier, isConfidential, authenticatedBy,
                     authorizationCallback, components=Componentized()):
            # type: (str, bool, SessionMechanism, Callable[[IInterface, ISession, Componentized], Any], Componentized) -> None
            pass

    def authorize(self, interfaces):
        # type: (List[IInterface]) -> Deferred
        """
        Authorize each interface by calling back to the session store's
        authorization callback.
        """
        result = {}
        for interface in interfaces:
            result[interface] = self._authorizationCallback(
                interface, self, self._components
            )
        return succeed(result)


class _MemoryAuthorizerFunction(object):
    """
    Type shadow for function with the given attribute.
    """
    __memoryAuthInterface__ = None # type: IInterface

    def __call__(self, interface, session, data):
        # type: (IInterface, ISession, Componentized) -> Any
        """
        Return a provider of the given interface.
        """


def declareMemoryAuthorizer(forInterface):
    # type: (IInterface) -> Callable[[Callable], _MemoryAuthorizerFunction]
    """
    Declare that the decorated function is an authorizer usable with a memory
    session store.
    """
    def decorate(decoratee):
        # type: (Callable[[IInterface, ISession, Componentized], Any]) -> _MemoryAuthorizerFunction
        decoratee = cast(_MemoryAuthorizerFunction, decoratee)
        decoratee.__memoryAuthInterface__ = forInterface
        return decoratee
    return decorate

@implementer(ISessionStore)
@attr.s
class MemorySessionStore(object):
    authorizationCallback = attr.ib(
        default=lambda interface, session, data: None
    )
    _secureStorage = attr.ib(default=Factory(dict))
    _insecureStorage = attr.ib(default=Factory(dict))

    if TYPE_CHECKING:
        def __init__(self, authorizationCallback=lambda interface, session, data: None,
                     secureStorage={}, insecureStorage={}):
            # type: (Callable[[IInterface, ISession, Componentized], Any], Dict, Dict) -> None
            pass

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
            return interfaceToCallable[interface](interface, session, data)
        return cls(authorizationCallback)

    def procurer(self):
        # type: () -> SessionProcurer
        return SessionProcurer(self)


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
            result = storage[identifier]
            if isConfidential != result.isConfidential:
                storage.pop(identifier)
                return fail(NoSuchSession(identifier))
            return succeed(result)
        else:
            return fail(NoSuchSession(identifier))


    def sentInsecurely(self, tokens):
        # type: (List[str]) -> None
        return
