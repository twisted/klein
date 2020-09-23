=================================
Example -- Using Non-Global State
=================================

For obvious reasons it may be desirable for your application to have some non-global state that is used by your route handlers.

Below we have created a simple ``ItemStore`` class that has an instance of ``Klein`` as a class variable ``app``.
We can now use ``@app.route`` to decorate the methods of the class.

.. code-block:: python

    import json

    from klein import Klein


    class ItemStore:
        app = Klein()

        def __init__(self):
            self._items = {}

        @app.route('/')
        def items(self, request):
            request.setHeader('Content-Type', 'application/json')
            return json.dumps(self._items)

        @app.route('/<string:name>', methods=['PUT'])
        def save_item(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            body = json.load(request.content)
            self._items[name] = body
            return json.dumps({'success': True})

        @app.route('/<string:name>', methods=['GET'])
        def get_item(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            return json.dumps(self._items.get(name))


    if __name__ == '__main__':
        store = ItemStore()
        store.app.run('localhost', 8080)
