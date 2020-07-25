# Copyright (c) 2011-2019. See LICENSE for details.

"""
Extensions to Tubes.
"""

from io import BytesIO
from typing import Any, BinaryIO, Iterable

from attr import attrib, attrs
from attr.validators import instance_of, optional, provides

from tubes.itube import IDrain, IFount, ISegment
from tubes.kit import Pauser, beginFlowingTo
from tubes.undefer import fountToDeferred

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from zope.interface import implementer


__all__ = ()


# See https://github.com/twisted/tubes/issues/60
def fountToBytes(fount: IFount) -> Deferred:
    def collect(chunks: Iterable[bytes]) -> bytes:
        return b"".join(chunks)

    d = fountToDeferred(fount)
    d.addCallback(collect)
    return d


# See https://github.com/twisted/tubes/issues/60
def bytesToFount(data: bytes) -> IFount:
    return IOFount(source=BytesIO(data))


# https://github.com/twisted/tubes/issues/61
@implementer(IFount)
@attrs(frozen=False)
class IOFount(object):
    """
    Fount that reads from a file-like-object.
    """

    outputType = ISegment

    _source: BinaryIO = attrib()

    drain: IDrain = attrib(
        validator=optional(provides(IDrain)), default=None, init=False
    )
    _paused = attrib(validator=instance_of(bool), default=False, init=False)

    def __attrs_post_init__(self) -> None:
        self._pauser = Pauser(self._pause, self._resume)

    def _flowToDrain(self) -> None:
        if self.drain is not None and not self._paused:
            data = self._source.read()
            if data:
                self.drain.receive(data)
            self.drain.flowStopped(Failure(StopIteration()))

    def flowTo(self, drain: IDrain) -> IFount:
        result = beginFlowingTo(self, drain)
        self._flowToDrain()
        return result

    def pauseFlow(self) -> Any:
        return self._pauser.pause()

    def stopFlow(self) -> Any:
        return self._pauser.resume()

    def _pause(self) -> None:
        self._paused = True

    def _resume(self) -> None:
        self._paused = False
        self._flowToDrain()
