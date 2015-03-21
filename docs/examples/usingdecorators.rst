===========================
Example -- Using Decorators 
===========================

Sometimes you might want to have more flexibility regarding how you create routes and decorate them.
Below we show how to register routes dynamically as well as applying default and optional decorators to each route.

`defaultMiddleware` shows how to set `Content-Type` header to `application/json` for all responses.
`authenticate` decorator shows how to authenticate a request by looking at the `Authorization` header and comparing it
with a previous defined key.

.. code-block:: python

    from functools import wraps
    from klein import Klein

    import json


    class WebAPI(object):

        def __init__(self, host=None, port=None, secretKey=None):

            self.host = '127.0.0.1' if host is None else host
            self.port = 8080 if port is None else port
            self.secretKey = 'twisted' if secretKey is None else secretKey

            self.app = Klein()
            self.setupRoutes()


        def setupRoutes(self):
            ''' Register endpoints '''

            self.app.handle_errors(self.notFound)
            self.addRoute('/', self.index)
            self.addRoute('/admin', self.admin, methods=['GET'], restricted=True)


        def toJSON(self, data):
            ''' Serialize data to JSON '''
            return json.dumps(data)

        
        def defaultMiddleware(self, f):
            '''This middleware sets application/json as default header for all responses'''

            @wraps(f)

            def deco(*args, **kwargs):
                request = next(iter(args), None)
                request.setHeader('Content-Type', 'application/json')

                return f(*args, **kwargs)

            return deco

        
        def authenticate(self, f):
            ''' Middleware for api-key authentication '''

            @wraps(f)

            def deco(*args, **kwargs):
                request = next(iter(args), None)
                apiKey = request.getHeader('Authorization')

                if not apiKey or apiKey != self.secretKey:
                    request.setResponseCode(401)
                    body = { 
                        'scope': 'private',
                        'message': 'Sorry, you need valid credentials to access this content' 
                    }
                    
                    return self.toJSON(body)

                return f(*args, **kwargs)

            return deco


        def addRoute(self, route, func, **kwargs):
            ''' 
            This is a helper function for assigning optional and default decorators 
            while setting up route endpoints
            '''

            methods = kwargs.get('methods', ['GET'])
            restricted = kwargs.get('restricted', False)

            resourceRoute = ''.join([kwargs.get('prefix', ''), route])

            func = self.defaultMiddleware(func)

            if restricted:
                func = self.authenticate(func)

            self.app.route(resourceRoute, methods=methods)(func)


        def index(self, request):
            response = { 'scope': 'public' , 'message': 'Welcome to our public endpoint' }

            return self.toJSON(response)


        def admin(self, request):
            response = { 'scope': 'private', 'message': 'You got access to our restricted content' }

            return self.toJSON(response)


        def notFound(self, request, failure):
            request.setResponseCode(404)
            request.setHeader('Content-Type', 'application/json')
            response = { 'scope': 'public', 'message': 'No idea what you are looking for' }

            return self.toJSON(response)


        def run(self):
            self.app.run(self.host, self.port)


    if __name__ == '__main__':
        webApi = WebAPI(host='0.0.0.0', secretKey='tw15t3d')
        webApi.run()


You can see the expected endpoints responses by executing the following cURL commands:

    curl -L http://localhost:8080/
    {"scope": "public", "message": "Welcome to our public endpoint"}

    curl -L http://localhost:8080/unknown
    {"scope": "public", "message": "No idea what you are looking for"}

    curl -L http://localhost:8080/admin
    {"scope": "private", "message": "Sorry, you need valid credentials to access this content"}

    curl -L http://localhost:8080/admin -H 'Authorization: tw15t3d'
    {"scope": "private", "message": "You got access to our restricted content"}

