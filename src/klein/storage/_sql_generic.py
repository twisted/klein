"""
Generic SQL data storage stuff; the substrate for session-storage stuff.
"""

from collections import deque
from sys import exc_info
from typing import Any, Text, Optional
import attr
from attr import Factory
from twisted.internet.defer import (Deferred, inlineCallbacks, returnValue,
                                    succeed)
from ..interfaces import TransactionEnded
from sqlalchemy import create_engine
from alchimia import TWISTED_STRATEGY

_sqlAlchemyConnection = Any
_sqlAlchemyTransaction = Any

COMMITTING = "committing"
COMMITTED = "committed"
COMMIT_FAILED = "commit failed"
ROLLING_BACK = "rolling back"
ROLLED_BACK = "rolled back"
ROLLBACK_FAILED = "rollback failed"


@attr.s
class Transaction(object):
    """
    Wrapper around a SQLAlchemy connection which is invalidated when the
    transaction is committed or rolled back.
    """
    _connection = attr.ib(type=_sqlAlchemyConnection)
    _transaction = attr.ib(type=_sqlAlchemyTransaction)
    _parent = attr.ib(type='Optional[Transaction]', default=None)
    _stopped = attr.ib(type=Text, default=u"")
    _completeDeferred = attr.ib(type=Deferred, default=Factory(Deferred))

    def _checkStopped(self):
        """
        Raise an exception if the transaction has been stopped for any reason.
        """
        # type: () -> None
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
            (lambda commitFailure: self._finishWith(COMMIT_FAILED))
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
            (lambda commitFailure: self._finishWith(ROLLBACK_FAILED))
        )


    def _finishWith(self, stopStatus):
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
        returnValue(Transaction(
            self._connection, (yield self._connection.begin_nested()),
            self
        ))


    def subtransact(self, logic):
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
class Transactor(object):
    """
    A context manager that represents the lifecycle of a transaction when
    paired with application code.
    """

    _newTransaction = attr.ib(type='Callable[[...], Deferred]')
    _transaction = attr.ib(type=Optional[Transaction], default=None)

    @inlineCallbacks
    def __aenter__(self):
        """
        Start a transaction.
        """
        # type: (type, Exception, Any) -> Deferred
        self._transaction = yield self._newTransaction()
        returnValue(self._transaction)

    @inlineCallbacks
    def __aexit__(self, exc_type, exc_value, traceback):
        # type: (type, Exception, Any) -> Deferred
        """
        End a transaction.
        """
        if exc_type is None:
            yield self._transaction.commit()
        else:
            yield self._transaction.rollback()
        self._transaction = None

    @inlineCallbacks
    def run(self, logic):
        """
        Run the given logic within this L{TransactionContext}, starting and
        stopping as usual.
        """
        # type: (Callable) -> Deferred
        try:
            transaction = yield self.__aenter__()
            result = yield logic(transaction)
        finally:
            yield self.__aexit__(*exc_info())
        returnValue(result)



@attr.s
class DataStore(object):
    """
    L{DataStore} is a generic storage object that connect to an SQL
    database, run transactions, and manage schema metadata.
    """

    _engine = attr.ib(type=_sqlAlchemyConnection)
    _freeConnections = attr.ib(default=Factory(deque), type=deque)

    @inlineCallbacks
    def newTransaction(self):
        """
        Create a new Klein transaction.
        """
        alchimiaConnection = (
            self._freeConnections.popleft() if self._freeConnections
            else (yield self._engine.connect())
        )
        alchimiaTransaction = yield alchimiaConnection.begin()
        kleinTransaction = Transaction(alchimiaConnection, alchimiaTransaction)
        @kleinTransaction._completeDeferred.addBoth
        def recycleTransaction(anything):
            self._freeConnections.append(alchimiaConnection)
            return anything
        returnValue(kleinTransaction)


    @inlineCallbacks
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
        # type: (IReactorThreads, Text, Iterable[Callable]) -> DataStore
        """
        Open an L{DataStore}.

        @param reactor: the reactor that this store should be opened on.
        @type reactor: L{IReactorThreads}

        @param dbURL: the SQLAlchemy database URI to connect to.
        @type dbURL: L{str}
        """
        return cls(create_engine(dbURL, reactor=reactor,
                                 strategy=TWISTED_STRATEGY))


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
    
