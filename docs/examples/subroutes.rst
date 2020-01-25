====================
Example -- Subroutes
====================

The ``routes`` decorator lets you set up different routes easily, but it can be cumbersome to write many similar routes.
If you need to write similar routes, the ``subroute`` function can help.
``subroute`` is a context manager within whose scope all invocations of ``route`` will have a prefix added.

Here is an example app that has routes for ``/branch/lair``, ``/branch/crypt``, and ``/branch/swamp`` all defined in a ``with app.subroute()`` block.

.. code-block:: python

    from klein import Klein

    app = Klein()

    with app.subroute("/branch") as app:
        @app.route("/lair")
        def lair(request):
            return b"These stairs lead to the lair of beasts."

        @app.route("/crypt")
        def crypt(request):
            return b"These stairs lead to an ancient crypt."

        @app.route("/swamp")
        def swamp(request):
            return b"A stair to a swampy wasteland."

    app.run("localhost", 8080)


The subroute method is also available globally if that is your preferred klein
pattern.

.. code-block:: python

    from klein import run, subroute

    with subroute("/branch") as app:
      @app.route("/twilightforest")
      def twighlightforest(request):
          return b"These stairs lead to the twilight forest."
    app.run("localhost", 8080)
