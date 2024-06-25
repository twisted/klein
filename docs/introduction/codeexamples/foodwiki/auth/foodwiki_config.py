import sqlite3
from typing import Optional

from foodwiki_db import allAuthorizers

from twisted.internet.defer import Deferred, succeed
from twisted.web.iweb import IRequest

from klein import Klein, Requirer
from klein.interfaces import ISession
from klein.storage.dbxs.dbapi_async import adaptSynchronousDriver
from klein.storage.sql import SQLSessionProcurer


app = Klein()

DB_FILE = "food-wiki.sqlite"

asyncDriver = adaptSynchronousDriver(
    (lambda: sqlite3.connect(DB_FILE)), sqlite3.paramstyle
)

sessions = SQLSessionProcurer(asyncDriver, allAuthorizers)
requirer = Requirer()


@requirer.prerequisite([ISession])
def procurer(request: IRequest) -> Deferred[ISession]:
    result: Optional[ISession] = ISession(request, None)
    if result is not None:
        # TODO: onValidationFailureFor results in one require nested inside
        # another, which invokes this prerequisite twice. this mistake should
        # not be easy to make
        return succeed(result)
    return sessions.procureSession(request)
