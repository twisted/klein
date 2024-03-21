# -*- test-case-name: klein.storage.dbxs.test.test_access -*-
from __future__ import annotations

from dataclasses import dataclass, field
from inspect import BoundArguments, signature
from typing import (
    Any,
    AsyncIterable,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from ..._typing_compat import ParamSpec, Protocol
from .dbapi_async import AsyncConnection, AsyncCursor


T = TypeVar("T")
P = ParamSpec("P")
A = TypeVar("A", bound=Union[AsyncIterable[object], Awaitable[object]])


class ParamMismatch(Exception):
    """
    The parameters required by the query are different than the parameters
    specified by the function.
    """


class IncorrectResultCount(Exception):
    """
    An assumption about the number of rows from a given query was violated;
    there were either too many or too few.
    """


class NotEnoughResults(IncorrectResultCount):
    """
    There were not enough results for the query to satify L{one}.
    """


class TooManyResults(IncorrectResultCount):
    """
    There were more results for a query than expected; more than one for
    L{one}, or any at all for L{zero}.
    """


class ExtraneousMethods(Exception):
    """
    An access pattern defined extraneous methods.
    """


def one(
    load: Callable[..., T],
) -> Callable[[object, AsyncCursor], Coroutine[object, object, T]]:
    """
    Fetch a single result with a translator function.
    """

    async def translate(db: object, cursor: AsyncCursor) -> T:
        rows = await cursor.fetchall()
        if len(rows) < 1:
            raise NotEnoughResults()
        if len(rows) > 1:
            raise TooManyResults()
        return load(db, *rows[0])

    return translate


def maybe(
    load: Callable[..., T]
) -> Callable[[object, AsyncCursor], Coroutine[object, object, Optional[T]]]:
    """
    Fetch a single result and pass it to a translator function, but return None
    if it's not found.
    """

    async def translate(db: object, cursor: AsyncCursor) -> Optional[T]:
        rows = await cursor.fetchall()
        if len(rows) < 1:
            return None
        if len(rows) > 1:
            raise TooManyResults()
        return load(db, *rows[0])

    return translate


def many(
    load: Callable[..., T]
) -> Callable[[object, AsyncCursor], AsyncIterable[T]]:
    """
    Fetch multiple results with a function to translate rows.
    """

    async def translate(db: object, cursor: AsyncCursor) -> AsyncIterable[T]:
        while True:
            row = await cursor.fetchone()
            if row is None:
                return
            yield load(db, *row)

    return translate


async def zero(loader: object, cursor: AsyncCursor) -> None:
    """
    Zero record loader.
    """
    result = await cursor.fetchone()
    if result is not None:
        raise TooManyResults("statemnts should not return values")
    return None


METADATA_KEY = "__query_metadata__"


@dataclass
class MaybeAIterable:
    down: Any

    def __await__(self) -> Any:
        return self.down.__await__()

    async def __aiter__(self) -> Any:
        actuallyiter = await self
        async for each in actuallyiter:
            yield each


@dataclass
class QueryMetadata:
    """
    Metadata defining a certain function on a protocol as a query method.
    """

    sql: str
    load: Callable[[AccessProxy, AsyncCursor], A]
    proxyMethod: Callable[..., Awaitable[object]] = field(init=False)

    def setOn(self, protocolMethod: Any) -> None:
        """
        Attach this QueryMetadata to the given protocol method definition,
        checking its arguments and computing C{proxyMethod} in the process,
        raising L{ParamMismatch} if the expected parameters do not match.
        """
        sig = signature(protocolMethod)
        precomputedSQL: Dict[str, Tuple[str, QmarkParamstyleMap]] = {}
        for style, mapFactory in styles.items():
            mapInstance = mapFactory()
            styledSQL = self.sql.format_map(mapInstance)
            precomputedSQL[style] = (styledSQL, mapInstance)

        sampleSQL, sampleInstance = precomputedSQL["qmark"]
        selfExcluded = list(sig.parameters)[1:]
        if set(sampleInstance.names) != set(selfExcluded):
            raise ParamMismatch(
                f"when defining {protocolMethod.__name__}(...), "
                f"SQL placeholders {sampleInstance.names} != "
                f"function params {selfExcluded}"
            )

        def proxyMethod(
            proxySelf: AccessProxy, *args: object, **kw: object
        ) -> Any:
            """
            Implementation of all database-proxy methods on objects returned
            from C{accessor}.
            """

            async def body() -> Any:
                conn = proxySelf.__query_connection__
                styledSQL, styledMap = precomputedSQL[conn.paramstyle]
                cur = await conn.cursor()
                bound = sig.bind(None, *args, **kw)
                await cur.execute(styledSQL, styledMap.queryArguments(bound))
                maybeAgen: Any = self.load(proxySelf, cur)
                try:
                    # there is probably a nicer way to detect aiter-ability
                    return await maybeAgen
                except TypeError:
                    return maybeAgen

            return MaybeAIterable(body())

        self.proxyMethod = proxyMethod
        setattr(protocolMethod, METADATA_KEY, self)

    @classmethod
    def loadFrom(cls, f: object) -> Optional[QueryMetadata]:
        """
        Load the query metadata for C{f} if it has any.
        """
        self: Optional[QueryMetadata] = getattr(f, METADATA_KEY, None)
        return self

    @classmethod
    def filterProtocolNamespace(
        cls, protocolNamespace: Iterable[Tuple[str, object]]
    ) -> Iterable[Tuple[str, QueryMetadata]]:
        """
        Load all QueryMetadata
        """
        extraneous = []
        for attrname, value in protocolNamespace:
            qm = QueryMetadata.loadFrom(value)
            if qm is None:
                if attrname not in PROTOCOL_IGNORED_ATTRIBUTES:
                    extraneous.append(attrname)
                continue
            yield attrname, qm
        if extraneous:
            raise ExtraneousMethods(
                f"non-query/statement methods defined: {extraneous}"
            )


def query(
    *,
    sql: str,
    load: Callable[[object, AsyncCursor], A],
) -> Callable[[Callable[P, A]], Callable[P, A]]:
    """
    Declare a query method.
    """
    qm = QueryMetadata(sql=sql, load=load)

    def decorator(f: Callable[P, A]) -> Callable[P, A]:
        qm.setOn(f)
        return f

    return decorator


def statement(
    *,
    sql: str,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, None]]],
    Callable[P, Coroutine[Any, Any, None]],
]:
    """
    Declare a query method.
    """
    return query(sql=sql, load=zero)


@dataclass
class DBProxy:
    """
    Database Proxy
    """

    name: str
    transaction: AsyncConnection


@dataclass
class QmarkParamstyleMap:
    names: List[str] = field(default_factory=list)

    def __getitem__(self, name: str) -> str:
        self.names.append(name)
        return "?"

    def queryArguments(self, bound: BoundArguments) -> Sequence[object]:
        """
        Compute the arguments to the query.
        """
        return [bound.arguments[each] for each in self.names]


class _EmptyProtocol(Protocol):
    """
    Empty protocol for setting a baseline of what attributes to ignore while
    metaprogramming.
    """


PROTOCOL_IGNORED_ATTRIBUTES = set(_EmptyProtocol.__dict__.keys())

styles = {
    "qmark": QmarkParamstyleMap,
}


@dataclass
class AccessProxy:
    """
    Superclass of all access proxies.
    """

    __query_connection__: AsyncConnection


def accessor(
    accessPatternProtocol: Callable[[], T]
) -> Callable[[AsyncConnection], T]:
    """
    Create a factory which binds a database transaction in the form of an
    AsyncConnection to a set of declared SQL methods.
    """
    return type(
        f"{accessPatternProtocol.__name__}DB",
        tuple([AccessProxy]),
        {
            name: metadata.proxyMethod
            for name, metadata in QueryMetadata.filterProtocolNamespace(
                accessPatternProtocol.__dict__.items()
            )
        },
    )
