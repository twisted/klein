.. _example-extendandcompose:

=============================
Example -- Extend and Compose
=============================

Let's say there's a need to build a RESTful API within a Klein application and the responses must be in JSON format.
All API responses must also have the content type ``application/json`` in the header.
Finally, to add complexity to this scenario, some endpoints must use an authentication method to gain access.
A typical endpoint might look something like:

.. code-block:: python

    @route('/jsonify')
    def jsonify(request):
        request.setHeader('application/json')
        if authenticated():
            result = {'access': 'granted'}
        else:
            result = {'access': 'denied'}


The downside would be the fact that all the endpoints would need to use the same syntax, making it tedious to write.
A solution would be to extend the functionality of the ``Klein`` object and separate out the reusable bits.

.. literalinclude:: codeexamples/extendandcompose.py
    :lines: 1-38


Instead of subclassing ``klein.Klein`` this example chose to "extend" its functionality by using decorators.
Most of the logic is in the ``route`` method, which applies authentication logic (via the ``authenticate`` decorator) and converts responses to proper JSON (via the ``jsonMiddleware`` decorator).
Now that the reusable JSON API parts have been encapsulated in a class, the technique from the :ref:`example-nonglobalstate` can be combined to compose the main part of the application.

.. literalinclude:: codeexamples/extendandcompose.py
    :lines: 40-63


Test the application endpoints using the ``curl`` command line tool::

    curl -v http://localhost:8080
    curl -v -X GET http://localhost:8080/jsonify
    curl -v -X GET -H 'Authorization:Tw!5t3d-kL3!n' http://localhost:8080/admin
    curl -v -X GET -H 'Authorization:Tw!5t3d-kL3!n' http://localhost:8080/alternate-admin
    curl -v -X GET http://localhost:8080/admin      # fails to authenticate
