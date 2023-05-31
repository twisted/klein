from typing import Awaitable, Callable, List, Optional

import attr
from treq import content
from treq.testing import StubTreq

from twisted.internet.defer import Deferred
from twisted.python.compat import nativeString
from twisted.python.modules import getModule
from twisted.trial.unittest import TestCase
from twisted.web.iweb import IRequest

from klein import Authorization, Field, Klein, Requirer, SessionProcurer
from klein.interfaces import (
    ISession,
    ISessionProcurer,
    ISimpleAccountBinding,
    SessionMechanism,
)
from klein.storage.dbaccess.testing import MemoryPool, immediateTest
from klein.storage.memory import MemoryAccountStore, MemorySessionStore
from klein.storage.sql._sql_glue import AccountSessionBinding, SessionStore

from ...interfaces import ISimpleAccount
from .._passwords import KleinV1PasswordEngine, PasswordEngine
from ..dbaccess.dbapi_async import transaction
from ..sql import SQLSessionProcurer


def fewerRounds() -> PasswordEngine:
    return KleinV1PasswordEngine(2**4, 2**5)


def moreRounds() -> PasswordEngine:
    return KleinV1PasswordEngine(2**6, 2**7)


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
        self.boundAccounts = await binder.boundAccounts()
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

        # sending insecure tokens should invalidate our session
        response = await stub.get("http://localhost/private", cookies=cookies)
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

    def test_memoryStore(self) -> None:
        """
        Test that L{MemoryAccountStore} can store simple accounts and bindings.
        """
        users = MemoryAccountStore()
        users.addAccount("itsme", "secretstuff")
        sessions = MemorySessionStore.fromAuthorizers(users.authorizers())
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

        # XXX need a cleaner way to make async-passlib functions be not-async
        from twisted.internet.defer import maybeDeferred

        from klein import _util

        self.patch(_util, "deferToThread", maybeDeferred)

        async with transaction(pool.connectable) as c:
            cursor = await c.cursor()
            for stmt in (
                getModule(__name__)
                .filePath.parent()
                .parent()
                .child("sql")
                .child("basic_auth_schema.sql")
                .getContent()
                .decode("utf-8")
                .split(";")
            ):
                await cursor.execute(stmt)

        async def newSession(
            isSecure: bool, mechanism: SessionMechanism
        ) -> ISession:
            async with transaction(pool.connectable) as c:
                return await SessionStore(c, [], fewerRounds()).newSession(
                    isSecure, mechanism
                )

        async with transaction(pool.connectable) as c:
            sampleStore = SessionStore(c, [], fewerRounds())
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

        proc = SQLSessionProcurer(pool.connectable, [], moreRounds())
        await self.authWithStoreTest(newSession, proc, pool)
