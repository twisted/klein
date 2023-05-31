# -*- test-case-name: klein.test.test_form.TestForms -*-
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Type

from attrs import Factory, define, field
from zope.interface import implementer

from twisted.python.components import Componentized

from ..._util import eagerDeferredCoroutine
from ...interfaces import ISession, ISimpleAccount, ISimpleAccountBinding
from ._memory import _MemoryAuthorizerFunction, declareMemoryAuthorizer


@implementer(ISimpleAccount)
@define
class MemoryAccount:
    """
    Implementation of in-memory simple account.
    """

    store: MemoryAccountStore
    accountID: str
    username: str
    password: str = field(repr=False)

    @eagerDeferredCoroutine
    async def bindSession(self, session: ISession) -> None:
        """
        Bind this account to the given session.
        """
        self.store._bindings[session.identifier].append(self)

    @eagerDeferredCoroutine
    async def changePassword(self, newPassword: str) -> None:
        """
        Change the password of this account.
        """
        self.password = newPassword


@implementer(ISimpleAccountBinding)
@define
class MemoryAccountBinding:
    """
    Implementation of in-memory simple account binding.
    """

    store: MemoryAccountStore
    session: ISession

    @eagerDeferredCoroutine
    async def boundAccounts(self) -> Sequence[ISimpleAccount]:
        return self.store._bindings[self.session.identifier]

    @eagerDeferredCoroutine
    async def createAccount(
        self, username: str, email: str, password: str
    ) -> Optional[ISimpleAccount]:
        """
        Refuse to create new accounts; memory accounts should be pre-created,
        since they won't persist.
        """

    @eagerDeferredCoroutine
    async def bindIfCredentialsMatch(
        self, username: str, password: str
    ) -> Optional[ISimpleAccount]:
        """
        Bind if the credentials match.
        """
        account = self.store._accounts.get(username)
        if account is None:
            return None
        if account.password != password:
            return None
        account.bindSession(self.session)
        return account

    @eagerDeferredCoroutine
    async def unbindThisSession(self) -> None:
        """
        Un-bind this session from all accounts.
        """
        del self.store._bindings[self.session.identifier]


@define
class MemoryAccountStore:
    """
    In-memory account store.
    """

    _accounts: Dict[str, MemoryAccount] = field(default=Factory(dict))
    _bindings: Dict[str, List[MemoryAccount]] = field(default=defaultdict(list))

    def authorizers(self) -> Iterable[_MemoryAuthorizerFunction]:
        """
        Construct the list of authorizers from the account state populated on
        this store.
        """

        @declareMemoryAuthorizer(MemoryAccount)
        @eagerDeferredCoroutine
        async def memauth(
            interface: Type[MemoryAccount],
            session: ISession,
            componentized: Componentized,
        ) -> Optional[MemoryAccount]:
            for account in self._bindings[session.identifier]:
                return account
            return None

        @declareMemoryAuthorizer(ISimpleAccount)
        @eagerDeferredCoroutine
        async def alsoSimple(
            interface: Type[ISimpleAccount],
            session: ISession,
            componentized: Componentized,
        ) -> Optional[ISimpleAccount]:
            return (await session.authorize([MemoryAccount])).get(MemoryAccount)

        @declareMemoryAuthorizer(ISimpleAccountBinding)
        def membind(
            interface: Type[ISimpleAccountBinding],
            session: ISession,
            componentized: Componentized,
        ) -> ISimpleAccountBinding:
            """
            ISimpleAccountBinding.
            """
            return MemoryAccountBinding(self, session)

        return [membind, alsoSimple, memauth]

    def addAccount(self, username: str, password: str) -> None:
        """
        Add an account with the given username and password.
        """
        self._accounts[username] = MemoryAccount(
            self, str(len(self._accounts)), username=username, password=password
        )
