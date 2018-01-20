# -*- test-case-name: klein.test.test_memory -*-
from binascii import hexlify
from os import urandom

import attr
from attr import Factory

from twisted.internet.defer import fail, succeed
from twisted.python.components import Componentized

from zope.interface import implementer

from klein import SessionProcurer
from klein.interfaces import ISession, ISessionStore, NoSuchSession

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

    def authorize(self, interfaces):
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

def declareMemoryAuthorizer(forInterface):
    """
    Declare that the decorated function is an authorizer usable with a memory
    session store.
    """
    def decorate(decoratee):
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

    @classmethod
    def fromAuthorizers(cls, authorizers):
        """
        Create a L{MemorySessionStore} from a collection of callbacks which can
        do authorization.
        """
        interfaceToCallable = {}
        for authorizer in authorizers:
            specifiedInterface = authorizer.__memoryAuthInterface__
            interfaceToCallable[specifiedInterface] = authorizer

        def authorizationCallback(interface, session, data):
            return interfaceToCallable[interface](interface, session, data)
        return cls(authorizationCallback)

    def procurer(self):
        return SessionProcurer(self)


    def _storage(self, isConfidential):
        """
        Return the storage appropriate to the isConfidential flag.
        """
        if isConfidential:
            return self._secureStorage
        else:
            return self._insecureStorage


    def newSession(self, isConfidential, authenticatedBy):
        storage = self._storage(isConfidential)
        identifier = hexlify(urandom(32)).decode('ascii')
        session = MemorySession(identifier, isConfidential, authenticatedBy,
                                self.authorizationCallback)
        storage[identifier] = session
        return succeed(session)


    def loadSession(self, identifier, isConfidential, authenticatedBy):
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
        return
