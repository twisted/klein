==========================================================
Introduction -- Using ``twistd`` to Start Your Application
==========================================================

``twistd`` (pronounced "twist-dee") is an application runner for Twisted applications.
It takes care of starting your app, setting up loggers, daemonising, and providing a nice interface to start it.


Using the ``twistd web`` Plugin
===============================

Exposing a valid :api:`twisted.web.resource.IResource <IResource>` will allow your application to use the pre-existing ``twistd web`` plugin.

To enable this functionality, just expose the ``resource`` object of your Klein router:

.. literalinclude:: codeexamples/twistdPlugin.py

Then run it (in this example, the file above is saved as ``twistdPlugin.py``:

.. code-block:: sh

  $ twistd -n web --class=twistdPlugin.resource

The full selection of options you can give to ``twistd web`` can be found in its help page.
Here are some relevant entries in it:

.. literalinclude:: twistdwebman.txt


Using HTTPS via the ``twistd web`` Plugin
=========================================

The ``twistd web`` plugin has inbuilt support for HTTPS, assuming you have TLS support for Twisted.

As an example, we will create some self-signed certs -- for the second command, the answers don't really matter, as this is only a demo:

.. code-block:: sh

  $ openssl genrsa > privkey.pem
  $ openssl req -new -x509 -key privkey.pem -out cert.pem -days 365

We will then run our plugin, specifying a HTTPS port and the relevant certificates:

.. code-block:: sh

  $ twistd -n web --class=twistdPlugin.resource -c cert.pem -k privkey.pem --https=4433

This will then start a HTTPS server on port 4433.
Visiting ``https://localhost:4433`` will give you a certificate error -- if you add a temporary exception, you will then be given the "Hello, world!" page.
Inspecting your browser's URL bar should reveal a little lock -- meaning that the connection is encrypted!

Of course, in production, you'd be using a cert signed by a certificate authority -- but self-signed certs have their uses.
