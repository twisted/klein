================================================
Example -- Disabling signal handler installation
================================================

You have the possibility to print raised errors directly in the file descriptor specified in the ``Klein.run()`` ``logFile`` parameter, it can be useful for troubleshooting or logging fins.

Below is an example of such implementation, the raised errors will be printed in ``sys.stdout`` by default :


.. code-block:: python

	from klein import route, run


	@route("/")
	def home(request):
	    return "Hello, world!"


	run("localhost", 8080, installSignalHandlers=False)

This is an addition of the ``Klein.handle_errors`` method.
