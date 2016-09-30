
from txscrypt import computeKey, checkPassword
from unicodedata import normalize
from twisted.internet.defer import returnValue, inlineCallbacks


@inlineCallbacks
def check_and_reset(stored_password_text, provided_password_text, resetter):
    """
    Check the given stored password text against the given provided password
    text.

    @param stored_password_text: opaque (text) from the account database.
    @type stored_password_text: L{unicode}

    @param provided_password_text: the plain-text password provided by the
        user.
    @type provided_password_text: L{unicode}
    """
    provided_password_bytes = _password_bytes(provided_password_text)
    stored_password_bytes = stored_password_text.encode("charmap")
    if (yield checkPassword(stored_password_bytes, provided_password_bytes)):
        # Password migration!  Does txscrypt have an awesome *new* hash it
        # wants to give us?  Store it.
        new_password_bytes = yield computeKey(provided_password_bytes)
        if new_password_bytes != provided_password_bytes:
            yield resetter(new_password_bytes.decode("charmap"))
        returnValue(True)
    returnValue(False)



def compute_key_text(password_text):
    """
    Compute some text to store for a given plain-text password.

    @param password_text: The text of a new password, as entered by a user.
    """
    return (computeKey(_password_bytes(password_text))
            .addCallback(lambda x: x.decode("charmap")))



def _password_bytes(password_text):
    """
    Convert a textual password into some bytes.
    """
    return normalize("NFKD", password_text).encode("utf-8")
