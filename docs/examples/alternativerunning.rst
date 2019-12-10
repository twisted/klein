=================================
Example - Alternatives to app.run
=================================

Sometimes you want to do special things, and the very simple ``Klein.run``
does not quite fit.


Example - IPv6, TLS, UNIX sockets, ... (endpoints)
==================================================

Instead of calling ``Klein.run`` with ``host`` and ``port`` parameters, it is
possible to call it with the parameter ``endpoint_description``.

The ``endpoint_description`` parameter uses Twisted Endpoints, which enable
very neat things, like out-of-the-box TLS and IPv6 support.

For more information check (specially the Servers section)
https://twistedmatrix.com/documents/current/core/howto/endpoints.html

.. code-block:: python

    #
    # Run an app that is IPv6 aware
    #

    # Notice that ":" is used as an argument separator on the syntax,
    # which has the effect that ":" separators for IPv6 addresses have to
    # be escaped.
    app.run(endpoint_description="tcp6:port=8080:interface=\:\:1")


    #
    # Run an app that listens on an UNIX socket under
    #

    # /var/srv/klein.sock
    app.run(endpoint_description="unix:address=/var/srv/klein.sock:"
                                 "mode=660:lockfile=1")

    #
    # Run an app that deals with TLS
    #
    app.run(endpoint_description=
                "ssl:port=443:privateKey=server.pem:"
                "extraCertChain=chain.pem:dhParameters=dh_param_1024.pem")

Example - Manually running the reactor
======================================

Calling ``Klein.run`` only makes a couple things easier for you, and
immediately runs the reactor.

Sometimes that is not desired, e.g. if you have other services running on
the same reactor or you want to run multiple Klein apps in the same reactor.

A way to get around that is to manually setup the endpoint (see above)
and manually start the reactor when it is convenient.

Notice that, since ``Klein.run`` sets up logging to stdout for you,
you will need to set that up manually as well.
Read more about logging with Twisted here:
https://twistedmatrix.com/documents/current/core/howto/logger.html

.. code-block:: python

    from klein import Klein
    app = Klein()

    from twisted.internet import endpoints, reactor
    from twisted.web.server import Site

    # Create desired endpoint
    endpoint_description = "tcp6:port=8080:interface=\:\:1"
    endpoint = endpoints.serverFromString(reactor, endpoint_description)

    # This actually starts listening on the endpoint with the Klein app
    endpoint.listen(Site(app.resource()))

    # After doing other things like setting up logging,
    # starting other services in the reactor or
    # listening on other ports or sockets:
    reactor.run()
