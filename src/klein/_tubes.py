# Copyright (c) 2017-2018. See LICENSE for details.

"""
Extensions to Tubes.
"""

from io import BytesIO
from typing import Iterable
from typing.io import BinaryIO

from attr import attrib, attrs
from attr.validators import instance_of, optional, provides

from tubes.itube import IDrain, IFount, ISegment
from tubes.kit import Pauser, beginFlowingTo
from tubes.undefer import fountToDeferred

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from zope.interface import implementer

BinaryIO, Deferred, Iterable  # Silence linter


__all__ = ()


# See https://github.com/twisted/tubes/issues/60
def fountToBytes(fount):
    # type: (IFount) -> Deferred[bytes]
    def collect(chunks):
        # type: (Iterable[bytes]) -> bytes
        return b"".join(chunks)

    d = fountToDeferred(fount)
    d.addCallback(collect)
    return d


# See https://github.com/twisted/tubes/issues/60
def bytesToFount(data):
    # type: (bytes) -> IFount
    return IOFount(source=BytesIO(data))



# https://github.com/twisted/tubes/issues/61
@implementer(IFount)
@attrs(frozen=False)
class IOFount(object):
    """
    Fount that reads from a file-like-object.
    """

    outputType = ISegment

    _source = attrib()  # type: BinaryIO

    drain = attrib(
        validator=optional(provides(IDrain)), default=None, init=False
    )  # type: IDrain
    _paused = attrib(validator=instance_of(bool), default=False, init=False)


    def __attrs_post_init__(self):
        # type: () -> None
        self._pauser = Pauser(self._pause, self._resume)


    def _flowToDrain(self):
        # type: () -> None
        if self.drain is not None and not self._paused:
            data = self._source.read()
            if data:
                self.drain.receive(data)
            self.drain.flowStopped(Failure(StopIteration()))


    def flowTo(self, drain):
        # type: (IDrain) -> IFount
        result = beginFlowingTo(self, drain)
        self._flowToDrain()
        return result


    def pauseFlow(self):
        # type: () -> None
        return self._pauser.pause()


    def stopFlow(self):
        # type: () -> None
        return self._pauser.resume()


    def _pause(self):
        # type: () -> None
        self._paused = True


    def _resume(self):
        # type: () -> None
        self._paused = False
        self._flowToDrain()
