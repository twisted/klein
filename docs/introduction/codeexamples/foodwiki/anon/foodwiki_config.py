import sqlite3

from dbxs.adapters.dbapi_twisted import adaptSynchronousDriver
from dbxs.dbapi import DBAPIConnection
from foodwiki_db import allAuthorizers

from twisted.internet.defer import Deferred, succeed
from twisted.web.iweb import IRequest

from klein import Klein, Requirer
from klein.interfaces import ISession
from klein.storage.sql import SQLSessionProcurer

DB_FILE = "food-wiki.sqlite"


def connectAndEnableForeignKeys() -> DBAPIConnection:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


asyncDriver = adaptSynchronousDriver(
    connectAndEnableForeignKeys, sqlite3.paramstyle
)

sessions = SQLSessionProcurer(asyncDriver, allAuthorizers)
requirer = Requirer()
app = Klein()


@requirer.prerequisite([ISession])
def procurer(request: IRequest) -> Deferred[ISession]:
    result: ISession | None = ISession(request, None)
    if result is not None:
        # TODO: onValidationFailureFor results in one require nested inside
        # another, which invokes this prerequisite twice. this mistake should
        # not be easy to make
        return succeed(result)
    return sessions.procureSession(request)
