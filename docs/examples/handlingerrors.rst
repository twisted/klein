==========================
Example -- Handling Errors
==========================

Most applications ever encounter errors.
Klein provides an error handling function to let you handle your app's errors in a centralized way.
Because Klein inherits Twisted's error callbacks, this error handling is built on top of Twisted callbacks.
You can still use Twisted callbacks directly, but Klein's error handlers let you concisely re-use error handling logic across different parts of your app.

Klein instances have a ``handle_errors`` method meant for use as a decorator.
When code in your app's endpoints raises an exception, Klein tries to catch it by calling functions you've decorated with ``@handle_errors``.
Klein calls your ``@handle_errors`` functions with the ``twisted.web.http.Request`` in progress and with a ``twisted.python.failure.Failure`` that wraps the raised exception.
This is the same signature as regular Twisted error callbacks.

Pass one or more classes as arguments to ``@handle_errors`` to make the decorated function handle only exceptions of those classes.
Like ``try foo: except Bar, Baz``, ``handle_errors`` also handles exceptions that subclass the classes passed as arguments.

If you decorate a function with ``@handle_errors`` but do not pass any arguments, it will try to handle *all* errors.
This can make development more difficult because your handler may handle errors you don't anticipate, and thus obscure stack traces & logging.
Like a ``try:`` block that ends with a bare ``except:``, ``@handle_errors`` with no arguments is a sign that you should be more specific about your expected failure cases.
The same holds for ``handle_errors(Exception)``: like ``except Exception:`` it's a code pattern that is very likely to cause bugs.


Example App
===========

This example uses error handling to return a custom 404 response when endpoints raise ``NotFound`` exceptions.

.. literalinclude:: error_handling.py


The following cURL commands (and output) can be used to test this behaviour::

    curl -L http://localhost:8080/droid/R2D2
    Not found, I say

    curl -L http://localhost:8080/droid/Janeway
    Droid found

    curl -L http://localhost:8080/bounty/things
    Not found, I say
