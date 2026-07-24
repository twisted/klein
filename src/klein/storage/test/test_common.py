from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, TypeVar

import attr
from dbxs.async_dbapi import AsyncConnection, transaction
from dbxs.testing import MemoryPool, immediateTest
from treq import content
from zope.interface import Interface, implementer

from twisted.internet.defer import Deferred, succeed
from twisted.python.compat import nativeString
from twisted.python.components import Componentized
from twisted.trial.unittest import TestCase
from twisted.web.iweb import IRequest

from klein import Authorization, Field, Klein, Requirer, SessionProcurer
from klein.interfaces import (
    ISession,
    ISessionProcurer,
    ISessionStore,
    ISimpleAccountBinding,
    SessionMechanism,
)
from klein.storage.memory import (
    MemoryAccountStore,
    MemorySessionStore,
    declareMemoryAuthorizer,
)
from klein.storage.sql import authorizerFor
from klein.storage.sql._sql_glue import AccountSessionBinding, SessionStore

from ...interfaces import ISimpleAccount
from ...test.util import makeStub as StubTreq
from ..passwords.testing import engineForTesting, hashUpgradeCount
from ..sql import SQLSessionProcurer, applyBasicSchema


T = TypeVar("T")


class IJustBrowsing(Interface):
    def browse() -> str: ...


@implementer(IJustBrowsing)
@dataclass
class JustBrowsing:
    style: str
    id: str

    def browse(self) -> str:
        return f"just browsing {self.style}, from {self.id}"

    @classmethod
    def fromSession(cls, session: ISession) -> JustBrowsing:
        return cls(
            style="securely" if session.isConfidential else "insecurely",
            id=session.identifier,
        )


@declareMemoryAuthorizer(IJustBrowsing)
def authorizeBrowsingMemory(
    what: type[object], session: ISession, componentized: Componentized
) -> Deferred[IJustBrowsing | None]:
    return succeed(JustBrowsing.fromSession(session))


@authorizerFor(IJustBrowsing)
async def authorizeBrowsingDatabase(
    store: ISessionStore, conn: AsyncConnection, session: ISession
) -> IJustBrowsing | None:
    return JustBrowsing.fromSession(session)


@attr.s(auto_attribs=True, hash=False)
class TestObject:
    procurer: ISessionProcurer
    loggedInAs: Optional[ISimpleAccount] = None
    boundAccounts: Optional[List[ISimpleAccount]] = None

    router = Klein()
    requirer = Requirer()

    @requirer.prerequisite([ISession])
    async def procureASession(self, request: IRequest) -> Optional[ISession]:
        return await self.procurer.procureSession(request)

    @requirer.require(
        router.route("/browse", methods=["get"]),
        browsed=Authorization(IJustBrowsing),
    )
    async def justBrowsing(self, browsed: IJustBrowsing) -> str:
        return browsed.browse()

    @requirer.require(
        router.route("/private", methods=["get"]),
        account=Authorization(ISimpleAccount),
    )
    async def whenLoggedIn(self, account: ISimpleAccount) -> str:
        """
        handle a login.
        """
        return f"itsa me, {account.username}"

    @requirer.require(
        router.route("/change-password", methods=["post"]),
        acct=Authorization(ISimpleAccount),
        newPassword=Field.password(),
    )
    async def changePassword(
        self, newPassword: str, acct: ISimpleAccount
    ) -> str:
        """
        Change the password on the logged in account.
        """
        await acct.changePassword(newPassword)
        return "changed"

    @requirer.require(
        router.route("/login", methods=["post"]),
        username=Field.text(),
        password=Field.password(),
        binder=Authorization(ISimpleAccountBinding),
    )
    async def handleLogin(
        self, username: str, password: str, binder: ISimpleAccountBinding
    ) -> str:
        """
        handle a login.
        """
        account = self.loggedInAs = await binder.bindIfCredentialsMatch(
            username, password
        )
        self.boundAccounts = list(await binder.boundAccounts())
        if account is None:
            return "auth fail"
        else:
            return "logged in"

    @requirer.require(
        router.route("/logout", methods=["post"]),
        binder=Authorization(ISimpleAccountBinding),
    )
    async def handleLogout(self, binder: ISimpleAccountBinding) -> str:
        """
        handle a logout
        """
        await binder.unbindThisSession()
        return "unbound"


class CommonStoreTests(TestCase):
    """
    Common interface!
    """

    async def authWithStoreTest(
        self,
        newSession: Callable[[bool, SessionMechanism], Awaitable[ISession]],
        procurer: ISessionProcurer,
        pool: Optional[MemoryPool] = None,
    ) -> None:
        """
        Test using a form to log in to an in-memory store.
        """
        session = await newSession(True, SessionMechanism.Cookie)
        otherSession = await newSession(True, SessionMechanism.Cookie)
        insecureSession = await newSession(False, SessionMechanism.Cookie)

        cookies = {"Klein-Secure-Session": nativeString(session.identifier)}
        to = TestObject(procurer)
        stub = StubTreq(to.router.resource())
        if pool is not None:
            pool.additionalPump(stub.flush)
        presponse = stub.get(
            "https://localhost/private",
            cookies={"Klein-Secure-Session": nativeString(session.identifier)},
        )
        response = await presponse
        self.assertEqual(response.code, 401)
        self.assertIn(b"DENIED", await content(response))

        # wrong password
        async def badLogin(badUsername: str, badPassword: str) -> None:
            response = await stub.post(
                "https://localhost/login",
                data=dict(
                    username=badUsername,
                    password=badPassword,
                    __csrf_protection__=session.identifier,
                ),
                cookies=cookies,
            )
            self.assertEqual(response.code, 200)
            self.assertIn(b"auth fail", await content(response))

            # still not logged in
            presponse = stub.get(
                "https://localhost/private",
                cookies={
                    "Klein-Secure-Session": nativeString(session.identifier)
                },
            )
            response = await presponse
            self.assertEqual(response.code, 401)
            self.assertIn(b"DENIED", await content(response))

        await badLogin("itsme", "wrongpassword")
        await badLogin("wronguser", "doesntmatter")

        # correct password
        response = await stub.post(
            "https://localhost/login",
            data=dict(
                username="itsme",
                password="secretstuff",
                __csrf_protection__=session.identifier,
            ),
            cookies=cookies,
        )
        self.assertEqual(response.code, 200)
        self.assertIn(b"logged in", await content(response))
        toAccounts = to.boundAccounts
        loggedIn = to.loggedInAs
        assert toAccounts is not None
        assert loggedIn is not None
        self.assertEqual(
            [each.username for each in toAccounts], [loggedIn.username]
        )

        async def check(
            whichSession: ISession, code: int, contents: bytes
        ) -> None:
            response = await stub.get(
                "https://localhost/private",
                cookies={
                    "Klein-Secure-Session": nativeString(
                        whichSession.identifier
                    )
                },
            )
            self.assertEqual(response.code, code)
            self.assertIn(contents, await content(response))

        # we can see it
        await check(session, 200, b"itsa me")
        # other session can't see it
        await check(otherSession, 401, b"DENIED")

        # we'll use a different password in a sec
        newPw = "differentstuff"
        response = await stub.post(
            "https://localhost/change-password",
            data=dict(
                newPassword=newPw,
                __csrf_protection__=session.identifier,
            ),
            cookies=cookies,
        )

        response = await stub.post("https://localhost/logout", cookies=cookies)
        self.assertEqual(200, response.code)
        self.assertIn(b"unbound", await content(response))
        # log out and we can't see it again
        await check(session, 401, b"DENIED")

        await badLogin("itsame", "secretstuff")
        response = await stub.post(
            "https://localhost/login",
            data=dict(
                username="itsme",
                password=newPw,
                __csrf_protection__=session.identifier,
            ),
            cookies=cookies,
        )
        self.assertEqual(200, response.code)
        # logged in again
        self.assertIn(b"logged in", await content(response))
        self.assertEqual(to.boundAccounts, [to.loggedInAs])
        self.assertEqual(
            {cookie.value for cookie in response.cookies()},
            {session.identifier},
        )

        # sending supposedly-secure tokens insecurely should invalidate our
        # session
        response = await stub.get("http://localhost/private", cookies=cookies)
        self.assertEqual(response.code, 401)
        self.assertIn(b"DENIED", await content(response))

        # sending invalid tokens insecurely should be like sending no tokens
        # (i.e. this happens when you clear a database, or restart an in-memory
        # server)

        response = await stub.get(
            "http://localhost/private",
            cookies={"Klein-Secure-Session": "never seen this session"},
        )
        self.assertEqual(response.code, 401)
        self.assertIn(b"DENIED", await content(response))

        response = await stub.get("https://localhost/private", cookies=cookies)
        # jar = response.cookies()
        # self.assertEqual()
        body = await content(response)
        self.assertEqual(response.code, 401)
        self.assertIn(b"DENIED", body)
        self.assertNotIn(
            session.identifier, {cookie.value for cookie in response.cookies()}
        )

        # We should be able to maintain an insecure session over an insecure
        # connection.  (A less and less relevant feature on the modern web, but
        # as long as we have it, we should test it.)
        cookies = {"Klein-INSECURE-Session": insecureSession.identifier}
        response = await stub.get("http://localhost/browse", cookies=cookies)
        self.assertEqual(response.code, 200)
        body = await content(response)
        self.assertIn(
            (
                f"just browsing insecurely, from {insecureSession.identifier}"
            ).encode(),
            body,
        )

    def test_memoryStore(self) -> None:
        """
        Test that L{MemoryAccountStore} can store simple accounts and bindings.
        """
        users = MemoryAccountStore()
        users.addAccount("itsme", "secretstuff")
        sessions = MemorySessionStore.fromAuthorizers(
            list(users.authorizers()) + [authorizeBrowsingMemory]
        )
        self.successResultOf(
            Deferred.fromCoroutine(
                self.authWithStoreTest(
                    sessions.newSession, SessionProcurer(sessions)
                )
            )
        )

    @immediateTest()
    async def test_sqlStore(self, pool: MemoryPool) -> None:
        """
        Test that L{procurerFromConnectable} gives us a usable session procurer.
        """

        await applyBasicSchema(pool.connectable)

        def asyncify(x: T) -> Callable[[], Awaitable[T]]:
            """
            Convert a thing that expects an Awaitable ( / Deferred) to instead
            get a coroutine.
            """

            async def get() -> T:
                return x

            return get

        async def newSession(
            isSecure: bool, mechanism: SessionMechanism
        ) -> ISession:
            async with transaction(pool.connectable) as c:
                return await SessionStore(
                    asyncify(c),
                    [authorizeBrowsingDatabase.authorizer],
                    engineForTesting(self),
                ).newSession(isSecure, mechanism)

        async with transaction(pool.connectable) as c:
            sampleStore = SessionStore(
                asyncify(c),
                [authorizeBrowsingDatabase.authorizer],
                engineForTesting(self),
            )
            sampleSession = await newSession(True, SessionMechanism.Cookie)
            b = AccountSessionBinding(sampleStore, sampleSession, c)
            self.assertIsNot(
                await b.createAccount(
                    "itsme", "ignore@example.com", "secretstuff"
                ),
                None,
            )
        async with transaction(pool.connectable) as c:
            self.assertIs(
                await b.createAccount("itsme", "somethingelse", "whatever"),
                None,
            )

        self.assertEqual(hashUpgradeCount(self), 0)
        proc = SQLSessionProcurer(
            pool.connectable,
            [authorizeBrowsingDatabase.authorizer],
            engineForTesting(self, upgradeHashes=True),
        )
        await self.authWithStoreTest(newSession, proc, pool)
        self.assertEqual(hashUpgradeCount(self), 1)
