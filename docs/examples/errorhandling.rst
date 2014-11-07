=========================
Example -- Error handling
=========================

In Klein you can register error handlers. In the async world this makes more sense than try/catch loops.

An additional advantage is DRYness of errors, for example one error handler for all your custom errors:

Here is an example showing basic error handling:

    from json import dumps

    from klein import Klein
    from exceptions import Exception


    def parse_error(failure):
        error = str(failure.type)
        return dumps(dict(error='.'.join(error[error.find("'"):error.rfind("'")].split('.')[1:]),
                          error_message=failure.getErrorMessage(),
                          **dict(stack=failure.getTraceback()) if tier == 'debug' else {}))


    class HTTPError(Exception):
        def __init__(self, message, status):
            super(HTTPError, self).__init__(message)
            self.status = status


    class NotFoundError(HTTPError):
        def __init__(self, message):
            super(self.__class__, self).__init__(message, 404)


    class MyApp(object):
        app = Klein()

        def __init__(self):
            self.stuff = {}

        @app.route('/', methods=['GET'])
        def get_stuff(self, request):
            request.setHeader('Content-Type', 'application/json')

           if not self.stuff:
               raise NotFoundError('No customers in collection')
           return dumps(self.stuff[:request.args.get('limit', 2)])  # Show only two records by default

        @app.handle_errors(HTTPError)
        def error_handler(self, request, failure):
            request.setResponseCode(failure.value.status)
            return parse_error(failure)


    if __name__ == '__main__':
        MyApp().app.run('0.0.0.0', 8080)
