"""
Generic SQL data storage stuff; the substrate for session-storage stuff.
"""

from collections import deque
from sys import exc_info
from typing import TYPE_CHECKING, Any, Optional, Text, TypeVar

import attr
from alchimia import TWISTED_STRATEGY
from attr import Factory
from sqlalchemy import create_engine
from zope.interface import Interface, implementer

from twisted.internet.defer import (
    Deferred,
    gatherResults,
    inlineCallbacks,
    returnValue,
    succeed,
)

from ..interfaces import TransactionEnded


_sqlAlchemyConnection = Any
_sqlAlchemyTransaction = Any

COMMITTING = "committing"
COMMITTED = "committed"
COMMIT_FAILED = "commit failed"
ROLLING_BACK = "rolling back"
ROLLED_BACK = "rolled back"
ROLLBACK_FAILED = "rollback failed"

if TYPE_CHECKING:  # pragma: no cover
    T = TypeVar("T")
    from twisted.internet.interfaces import IReactorThreads

    IReactorThreads
    from typing import Iterable

    Iterable
    from typing import Callable

    Callable
    from twisted.web.iweb import IRequest

    IRequest


@attr.s
class Transaction:
    """
    Wrapper around a SQLAlchemy connection which is invalidated when the
    transaction is committed or rolled back.
    """

    _connection = attr.ib(type=_sqlAlchemyConnection)
    _transaction = attr.ib(type=_sqlAlchemyTransaction)
    _parent = attr.ib(type="Optional[Transaction]", default=None)
    _stopped = attr.ib(type=str, default="")
    _completeDeferred = attr.ib(type=Deferred, default=Factory(Deferred))

    def _checkStopped(self):
        # type: () -> None
        """
        Raise an exception if the transaction has been stopped for any reason.
        """
        if self._stopped:
            raise TransactionEnded(self._stopped)
        if self._parent is not None:
            self._parent._checkStopped()

    def execute(self, statement, *multiparams, **params):
        # type: (Any, *Any, **Any) -> Deferred
        """
        Execute a statement unless this transaction has been stopped, otherwise
        raise L{TransactionEnded}.
        """
        self._checkStopped()
        return self._connection.execute(statement, *multiparams, **params)

    def commit(self):
        # type: () -> Deferred
        """
        Commit this transaction.
        """
        self._checkStopped()
        self._stopped = COMMITTING
        return self._transaction.commit().addCallbacks(
            (lambda commitResult: self._finishWith(COMMITTED)),
            (lambda commitFailure: self._finishWith(COMMIT_FAILED)),
        )

    def rollback(self):
        # type: () -> Deferred
        """
        Roll this transaction back.
        """
        self._checkStopped()
        self._stopped = ROLLING_BACK
        return self._transaction.rollback().addCallbacks(
            (lambda commitResult: self._finishWith(ROLLED_BACK)),
            (lambda commitFailure: self._finishWith(ROLLBACK_FAILED)),
        )

    def _finishWith(self, stopStatus):
        # type: (Text) -> None
        """
        Complete this transaction.
        """
        self._stopped = stopStatus
        self._completeDeferred.callback(stopStatus)

    @inlineCallbacks
    def savepoint(self):
        # type: () -> Deferred
        """
        Create a L{Savepoint} which can be treated as a sub-transaction.

        @note: As long as this L{Savepoint} has not been rolled back or
            committed, this transaction's C{execute} method will execute within
            the context of that savepoint.
        """
        returnValue(
            Transaction(
                self._connection, (yield self._connection.begin_nested()), self
            )
        )

    def subtransact(self, logic):
        # type: (Callable[[Transaction], Deferred]) -> Deferred
        """
        Run the given C{logic} in a subtransaction.
        """
        return Transactor(self.savepoint).transact(logic)

    def maybeCommit(self):
        # type: () -> Deferred
        """
        Commit this transaction if it hasn't been finished (committed or rolled
        back) yet; otherwise, do nothing.
        """
        if self._stopped:
            return succeed(None)
        return self.commit()

    def maybeRollback(self):
        # type: () -> Deferred
        """
        Roll this transaction back if it hasn't been finished (committed or
        rolled back) yet; otherwise, do nothing.
        """
        if self._stopped:
            return succeed(None)
        return self.rollback()


@attr.s
class Transactor:
    """
    A context manager that represents the lifecycle of a transaction when
    paired with application code.
    """

    _newTransaction = attr.ib(type="Callable[[], Deferred]")
    _transaction = attr.ib(type=Optional[Transaction], default=None)

    @inlineCallbacks
    def __aenter__(self):
        # type: () -> Deferred
        """
        Start a transaction.
        """
        self._transaction = yield self._newTransaction()
        # ^ https://github.com/python/mypy/issues/4688
        returnValue(self._transaction)

    @inlineCallbacks
    def __aexit__(self, exc_type, exc_value, traceback):
        # type: (type, Exception, Any) -> Deferred
        """
        End a transaction.
        """
        assert self._transaction is not None
        if exc_type is None:
            yield self._transaction.commit()
        else:
            yield self._transaction.rollback()
        self._transaction = None

    @inlineCallbacks
    def transact(self, logic):
        # type: (Callable) -> Deferred
        """
        Run the given logic within this L{TransactionContext}, starting and
        stopping as usual.
        """
        try:
            transaction = yield self.__aenter__()
            result = yield logic(transaction)
        finally:
            yield self.__aexit__(*exc_info())
        returnValue(result)


@attr.s(hash=False)
class DataStore:
    """
    L{DataStore} is a generic storage object that connect to an SQL
    database, run transactions, and manage schema metadata.
    """

    _engine = attr.ib(type=_sqlAlchemyConnection)
    _freeConnections = attr.ib(default=Factory(deque), type=deque)

    @inlineCallbacks
    def newTransaction(self):
        # type: () -> Deferred
        """
        Create a new Klein transaction.
        """
        alchimiaConnection = (
            self._freeConnections.popleft()
            if self._freeConnections
            else (yield self._engine.connect())
        )
        alchimiaTransaction = yield alchimiaConnection.begin()
        kleinTransaction = Transaction(alchimiaConnection, alchimiaTransaction)

        @kleinTransaction._completeDeferred.addBoth
        def recycleTransaction(anything):
            # type: (T) -> T
            self._freeConnections.append(alchimiaConnection)
            return anything

        returnValue(kleinTransaction)

    def transact(self, callable):
        # type: (Callable[[Transaction], Any]) -> Any
        """
        Run the given C{callable} within a transaction.

        @param callable: A callable object that encapsulates application logic
            that needs to run in a transaction.
        @type callable: callable taking a L{Transaction} and returning a
            L{Deferred}.

        @return: a L{Deferred} firing with the result of C{callable}
        @rtype: L{Deferred} that fires when the transaction is complete, or
            fails when the transaction is rolled back.
        """
        return Transactor(self.newTransaction).transact(callable)

    @classmethod
    def open(cls, reactor, dbURL):
        # type: (IReactorThreads, Text) -> DataStore
        """
        Open an L{DataStore}.

        @param reactor: the reactor that this store should be opened on.
        @type reactor: L{IReactorThreads}

        @param dbURL: the SQLAlchemy database URI to connect to.
        @type dbURL: L{str}
        """
        return cls(
            create_engine(dbURL, reactor=reactor, strategy=TWISTED_STRATEGY)
        )


class ITransactionRequestAssociator(Interface):
    """
    Associates transactions with requests.
    """


@implementer(ITransactionRequestAssociator)
@attr.s
class TransactionRequestAssociator:
    """
    Does the thing the interface says.
    """

    _map = attr.ib(type=dict, default=Factory(dict))
    committing = attr.ib(type=bool, default=False)

    @inlineCallbacks
    def transactionForStore(self, dataStore):
        # type: (DataStore) -> Deferred
        """
        Get a transaction for the given datastore.
        """
        if dataStore in self._map:
            returnValue(self._map[dataStore])
        txn = yield dataStore.newTransaction()
        self._map[dataStore] = txn
        returnValue(txn)

    def commitAll(self):
        # type: () -> Deferred
        """
        Commit all associated transactions.
        """
        self.committing = True
        return gatherResults(
            [value.maybeCommit() for value in self._map.values()]
        )


@inlineCallbacks
def requestBoundTransaction(request, dataStore):
    # type: (IRequest, DataStore) -> Deferred
    """
    Retrieve a transaction that is bound to the lifecycle of the given request.

    There are three use-cases for this lifecycle:

        1. 'normal CRUD' - a request begins, a transaction is associated with
           it, and the transaction completes when the request completes.  The
           appropriate time to commit the transaction is the moment before the
           first byte goes out to the client.  The appropriate moment to
           interpose this commit is in `Request.write`, at the moment where
           it's about to call channel.writeHeaders, since the HTTP status code
           should be an indicator of whether the transaction succeeded or
           failed.

        2. 'just the session please' - a request begins, a transaction is
           associated with it in order to discover the session, and the
           application code in question isn't actually using the database.
           (Ideally as expressed through "the dependency-declaration decorator,
           such as @authorized, did not indicate that a transaction will be
           required").

        3. 'fancy API stuff' - a request begins, a transaction is associated
           with it in order to discover the session, the application code needs
           to then do I{something} with that transaction in-line with the
           session discovery, but then needs to commit in order to relinquish
           all database locks while doing some potentially slow external API
           calls, then start a I{new} transaction later in the request flow.
    """
    assoc = request.getComponent(ITransactionRequestAssociator)
    if assoc is None:
        assoc = TransactionRequestAssociator()
        request.setComponent(ITransactionRequestAssociator, assoc)

        def finishCommit(result):
            # type: (Any) -> Deferred
            return assoc.commitAll()

        request.notifyFinish().addBoth(finishCommit)

        # originalWrite = request.write
        # buffer = []
        # def committed(result):
        #     for buf in buffer:
        #         if buf is None:
        #             originalFinish()
        #         else:
        #             originalWrite(buf)

        # def maybeWrite(data):
        #     if request.startedWriting:
        #         return originalWrite(data)
        #     buffer.append(data)
        #     if assoc.committing:
        #         return
        #     assoc.commitAll().addBoth(committed)
        # def maybeFinish():
        #     if not request.startedWriting:
        #         buffer.append(None)
        #     else:
        #         originalFinish()
        # originalFinish = request.finish
        # request.write = maybeWrite
        # request.finish = maybeFinish
    txn = yield assoc.transactionForStore(dataStore)
    return txn
