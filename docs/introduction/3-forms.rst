
===================
Handling Form Input
===================

Prologue
--------

In :ref:`“Streamlined Apps With HTML and JSON” <htmljson>` we set up a basic
site that could render HTML and read data.  However, for most applications, you
will need some way for users to **input** data; in other words: handling forms,
both rendering them and posting them.

In order to handle HTML forms from the browser `securely
<https://owasp.org/www-community/attacks/csrf>`_, we also have to implement
some form of authenticated session along with them.

So let's build on top of our food-list application by letting users submit a
form that adds some foods to a list.

Our example here will be a very simple app, where you type in the name of a
food and give it a star rating.  To begin, it'll be entirely anonymous.

If you want full, runnable examples, you can find them `in the Klein repository
on Github
<https://github.com/twisted/klein/tree/trunk/docs/introduction/codeexamples/>`_

Configuration and Setup
-----------------------

In order to provide a realistic example that actually stores state, we'll also
use Klein's integrated database access system, and simple account/session
storage with username and password authentication.  However, there are
documented interfaces between each of these layers (storage, sessions,
accounts), and your application can supply its own account or session storage
as your needs for authentication evolve.  But before we get into
authentication, let's get a basic system for processing forms and storing data
set up.

To configure our system we will set up a few things:

- First, we will adapt the synchronous ``sqlite3`` database driver to an
  asynchronous one.

- Next, we will build a *session procurer*, which is what will retrieve our
  sessions from the configured database.

- Then, we will set up a ``Requirer``, which is how each of our routes will
  tell the authorization and forms systems what values our routes require to
  execute.

- Finally, we will set up a *prerequisite requirement*, a thing that all routes
  in our application require, of an ``ISession``.  We hook this up to our
  ``Requirer`` using the ``requirer.prerequisite()`` decorator.

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_config.py

We'll also need some HTML templating set up to style our pages.  Using what we
learned about Plating, we'll set up a basic page, use the ``fragment``
convenience decorator to make a widget for consistently displaying a food in
the HTML UI.

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_templates.py

.. note::

   ``@Plating.fragment`` functions are invoked once at the time they are
   decorated, with each of their arguments being a ``slot`` object, **not** the
   type that it's they're declared to have; the only thing you should do in the
   body of these functions is construct a ``Tag`` object that serves as a
   fragment of your resulting template.  This can be a little confusing at
   first, but it allows you to have a nice type-checked interface to ensure
   that you're always passing the correct slots to them later.


Database Access with ``dbxs``
-----------------------------

You may have noticed that in the configuration above, we constructed our
``SQLSessionProcurer`` with a list of *authorizers*.  An authorizer is a
function that can look at a database and determine if a user is authorized to
perform a task, so now we will implement the interaction with the database.

We will use Klein's built-in lightweight asynchronous database access system,
``dbxs``, allows you to keep your queries organized and construct simple
classes from your query results, without bringing in the overhead of an ORM or
query builder.  If you know SQL and you know basic Python data structures, you
allmost know how to use it already.

First let's get started with a very basic schema; a 'food' with a name and a
rating:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :lines: 14-19

Next, a function to apply that schema, along with Klein's own basic account &
session schema with ``session`` and ``account`` tables:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :lines: 11-11

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :pyobject: applySchema

Now, let's define our basic data structure to correspond to that table:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :pyobject: FoodRating

And now we will use ``dbxs`` to specify what queries we're going to make
against that schema.

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :lines: 5

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :pyobject: RatingsDB

Here, we have defined a ``typing.Protocol`` whowse methods are all awaitable or
async iterables decorated with ``@query`` (for SQL expressions that we expect
results for) or ``@statement`` for those which we expect to have side effects
but not return values.  We have one read operation, ``allRatings``, that gives
us all the ratings in the database, and ``addRating`` which adds a rating.  All
the argument types for these methods must be things you can pass to the
database, and they are supplied to the query via the curly-braced format
specifiers included in the SQL string, whose names match the parameters
specified in your Python function arguments.

While ``@statement`` returns no values, ``@query`` needs to know how to
interpret its query results, and it does this via its ``load`` argument.  If
you pass ``load=many(YourCallable)``, the decorated function must return an
``AsyncIterable`` of ``YourCallable``'s return type.  The callable itself takes
an ``AsyncConnection`` as its first argument, and the columns of the query's
results as the rest of the arguments.  Here, we know that ``select name,
rating`` matches up with ``FoodRating``'s dataclass arguments, ``name: str``
and ``rating: int``.

If you have a query that you know should only ever return a single value, you
can use ``load=one(YourType)`` and the return type should be
``Awaitable[YourType]``, or for one-or-zero results you can use
``load=maybe(YourType)`` which should return ``Awaitable[YourType | None]``.

These decorators provide information, but a ``Protocol`` is an abstract type;
it can't actually **do** anything on its own.  We need to somehow transform an
``AsyncConnection`` into something that looks like this type and executes these
queries, and for that we use ``accessor``, which converts our ``RatingsDB``
protocol into a callable that *takes* an ``AsyncConnection`` and *returns* an
instance of ``RatingsDB`` that can execute all those queries.

This system will help you out by performing a few basic checks.  At type-check
time, ``mypy`` will make sure that your return types correspond with the loader
type (``one``, ``many``, ``maybe``) that you've specified.  At import time, you
will get an exception if the arguments specified in your function signatures
are not used in your queries, or if the queries use arguments you didn't
provide.  However, you will need to verify that the SQL itself is valid; we'll
cover that in a later section on testing.

Now that we've got a basic data-access layer in place, let's put some access
control in place.  For this simple anonymous site, the access control is pretty
lenient; everyone should bea uthorized to access these methods all the time.
However, given that we'll want to restrict that a bit in the future, we can't
use our new data-access ``RatingsDB`` ``Protocol`` directly, so we will declare
a new class.  For this example it will simply forward all the methods on:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :pyobject: FoodRater

But then we will also declare an **authorizer** for it, so that Klein knows how
to determine if a user has access to it in a particular route that needs it:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :pyobject: authorizeFoodRater

SQL authorizers are passed a ``dbxs`` ``AsyncConnection``, a session store, and
the user's current session.  They can then do any queries necessary to
determine if a user is authorized, and return ``None`` if they're not, which is
why we declare that we return an ``Optional[FoodRater]``, reserving the right
that we may want to return ``None`` later.  However, for the time being, we use
``accessRatings`` to convert our database connection into a ``RatingsDB``, then
pass it to our ``FoodRater`` so that all sessions have access to this
functionality if they need it; no queries required just yet.

Finally, we can build the list of authorizers that we used in the configuration
above:

.. literalinclude:: codeexamples/foodwiki/anon/foodwiki_db.py
   :lines: 70
