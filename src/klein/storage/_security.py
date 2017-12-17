
from unicodedata import normalize
from functools import partial
from passlib.context import CryptContext
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.internet.threads import deferToThread


passlibContextWithGoodDefaults = partial(CryptContext, schemes=['bcrypt'])

def _verifyAndUpdate(secret, hash, ctxFactory=passlibContextWithGoodDefaults):
    """
    Asynchronous wrapper for L{CryptContext.verify_and_update}.
    """
    @deferToThread
    def theWork():
        return ctxFactory().verify_and_update(secret, hash)
    return theWork


def _hashSecret(secret, ctxFactory=passlibContextWithGoodDefaults):
    """
    Asynchronous wrapper for L{CryptContext.hash}.
    """
    @deferToThread
    def theWork():
        return ctxFactory().hash(secret)
    return theWork



@inlineCallbacks
def checkAndReset(storedPasswordText, providedPasswordText, resetter):
    """
    Check the given stored password text against the given provided password
    text.

    @param storedPasswordText: opaque (text) from the account database.
    @type storedPasswordText: L{unicode}

    @param providedPasswordText: the plain-text password provided by the
        user.
    @type providedPasswordText: L{unicode}

    @return: L{Deferred} firing with C{True} if the password matches and
        C{False} if the password does not match.
    """
    providedPasswordText = normalize('NFD', providedPasswordText)
    valid, newHash = yield _verifyAndUpdate(providedPasswordText,
                                            storedPasswordText)
    if valid:
        # Password migration!  Does our passlib context have an awesome *new*
        # hash it wants to give us?  Store it.
        if newHash is not None:
            if isinstance(newHash, 'bytes'):
                newHash = newHash.decode("charmap")
            yield resetter(newHash)
        returnValue(True)
    else:
        returnValue(False)



@inlineCallbacks
def computeKeyText(passwordText):
    """
    Compute some text to store for a given plain-text password.

    @param passwordText: The text of a new password, as entered by a user.

    @return: a L{Deferred} firing with L{unicode}.
    """
    normalized = normalize('NFD', passwordText)
    hashed = yield _hashSecret(normalized)
    if isinstance(hashed, bytes):
        hashed = hashed.decode("charmap")
    return hashed
