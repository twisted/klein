==========================
Example -- Using Deferreds
==========================

And of course, this is Twisted.
So there is a wealth of APIs that return a ``twisted.internet.defer.Deferred``.
A ``Deferred`` may also be returned from handler functions and their result will be used as the response body.

Here is a simple Google proxy, using `treq <https://github.com/dreid/treq>`_ (think Requests, but using Twisted).

.. literalinclude:: /codeexamples/intro1/googleProxy.py