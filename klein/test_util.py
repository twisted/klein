import twisted

from twisted.trial.unittest import TestCase
from twisted.python import failure
from twisted.python.versions import Version



if twisted.version < Version('twisted', 13, 1, 0):
    class TestCase(TestCase):
        def successResultOf(self, deferred):
            result = []
            deferred.addBoth(result.append)
            if not result:
                self.fail(
                    "Success result expected on %r, found no result instead" % (
                        deferred,))
            elif isinstance(result[0], failure.Failure):
                self.fail(
                    "Success result expected on %r, "
                    "found failure result instead:\n%s" % (
                        deferred, result[0].getTraceback()))
            else:
                return result[0]

        def failureResultOf(self, deferred, *expectedExceptionTypes):
            result = []
            deferred.addBoth(result.append)
            if not result:
                self.fail(
                    "Failure result expected on %r, found no result instead" % (
                        deferred,))
            elif not isinstance(result[0], failure.Failure):
                self.fail(
                    "Failure result expected on %r, "
                    "found success result (%r) instead" % (deferred, result[0]))
            elif (expectedExceptionTypes and
                  not result[0].check(*expectedExceptionTypes)):
                expectedString = " or ".join([
                    '.'.join((t.__module__, t.__name__)) for t in
                    expectedExceptionTypes])

                self.fail(
                    "Failure of type (%s) expected on %r, "
                    "found type %r instead: %s" % (
                        expectedString, deferred, result[0].type,
                        result[0].getTraceback()))
            else:
                return result[0]
