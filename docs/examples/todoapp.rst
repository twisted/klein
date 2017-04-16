===================
Example -- TODO app
===================

Here is a short example showing basic CRUD and error handling:

    from os import environ
    from json import dumps, loads
    from uuid import uuid4

    from collections import OrderedDict
    from klein import Klein
    from exceptions import Exception

    from pprint import PrettyPrinter

    pp = PrettyPrinter(indent=4).pprint

    tier = environ.get('tier', 'production')


    def parse_error(failure):
        error = str(failure.type)
        return dumps(dict(error='.'.join(error[error.find("'"):error.rfind("'")].split('.')[1:]),
                          error_message=failure.getErrorMessage(),
                          **dict(stack=failure.getTraceback()) if tier == 'debug' else {}))


    class HTTPError(Exception):
        def __init__(self, message, status):
            super(HTTPError, self).__init__(message)
            self.status = status


    class UniqueKeyError(HTTPError):
        def __init__(self, message):
            super(self.__class__, self).__init__(message, 400)


    class NotFoundError(HTTPError):
        def __init__(self, message):
            super(self.__class__, self).__init__(message, 404)


    class ValidationError(HTTPError):
        def __init__(self, message):
            super(self.__class__, self).__init__(message, 400)


    class CustomerStore(object):
        app = Klein()

        def __init__(self):
            self.customers = OrderedDict(dict())  # Trivial to swap out for some simple k/v store or SimpleDB

        @app.route('/', methods=['GET', 'POST'])
        def create_customer(self, request):
            request.setHeader('Content-Type', 'application/json')

            if request.method == 'POST':
                body = loads(request.content.read())
                if body.keys() != ['first_name', 'last_name', 'country']:
                    raise ValidationError('You must include `first_name` and `last_name` keys')
                pk = '{first_name} {last_name}'.format(first_name=body['first_name'], last_name=body['last_name'])
                if pk in self.customers:
                    raise UniqueKeyError('First name + last_name combination must be unique')
                body['id'] = uuid4().get_hex()
                self.customers[pk] = body
                return dumps({'created': body})
            else:
                if not request.args or 'limit' in request.args:
                    if not self.customers:
                        raise NotFoundError('No customers in collection')
                    return dumps(self.customers[:request.args.get('limit', 2)])  # Show only two records by default
                elif request.args.keys() != ['first_name', 'last_name']:
                    raise ValidationError('You must include `first_name` and `last_name` keys')
                pk = '{first_name} {last_name}'.format(first_name=request.args['first_name'][0],
                                                       last_name=request.args['last_name'][0])
                if pk not in self.customers:
                    raise NotFoundError('First name + last_name combination not found in collection')

                return dumps(self.customers[pk])

        @app.route('/<string:name>', methods=['PUT'])
        def save_customer(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            body = loads(request.content.read())
            # You can also edit the pk here, which might not be a good idea:
            if {'first_name', 'last_name', 'id'}.issubset(set(body.keys())):  # Allow you to edit `id` here
                raise ValidationError('You must include `first_name`, `last_name`, `country` and/or `id` key(s)')
            if name not in self.customers:
                raise NotFoundError('"{name}" not found in customers collection'.format(name=name))

            self.customers[name].update(body)
            return dumps(self.customers[name])

        @app.route('/<string:name>', methods=['GET'])
        def retrieve_customer(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            if name not in self.customers:
                raise NotFoundError('"{name}" not found in customers collection'.format(name=name))
            return dumps(self.customers[name])

        @app.route('/<string:name>', methods=['DELETE'])
        def delete_customer(self, request, name):
            request.setHeader('Content-Type', 'application/json')
            if name not in self.customers:
                raise NotFoundError('"{name}" not found in customers collection'.format(name=name))
            return dumps({'deleted': self.customers.pop(name)})

        @app.handle_errors(HTTPError)
        def error_handler(self, request, failure):
            request.setResponseCode(failure.value.status)
            return parse_error(failure)


    if __name__ == '__main__':
        store = CustomerStore()
        store.app.run('0.0.0.0', 8080)
