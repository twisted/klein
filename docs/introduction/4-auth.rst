
Authentication and Authorization
================================

Now that we can handle forms and sessions, let's build on that to build a
website with signup and login forms.

We'll build on our food-rating wiki example, and modify it to have to have user
accounts.  Let's begin by changing our schema to include the user who posted
the rating.

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :lines: 21-30

We are adding a ``rated_by`` column with a foreign key constraint on
``account``.  But where did ``account`` come from?

In order to do anything useful within a database with authentication, we need
to be able to relate to the account and session tables, so they are considered
part of Klein's public API.  For reference, here is that full schema:

.. literalinclude:: ../../src/klein/storage/sql/basic_auth_schema.sql
   :language: sql

Next, we'll need to split up our database interface.  Previously, we only had
one authorized object, for all clients.  However, now we have two classes of
client: those logged in to an account, and those not logged in to an account.
We only want to allow ratings for those who have signed up and logged in.

On the front page, we will want to display a bunch of ratings by different
users, with links to their user pages.  So we will need a new ``NamedRating``
class which combines the rating with a username rather than an account ID, to
make the presentation of the URLs nice; we don't want them to include the
opaque blobs used for account IDs.  We'll also need a query to build those.
So, here are our new queries; we need one for just the top 10 ratings, and then
one that gives us all the ratings by a given user:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: PublicRatingsDB

Next, we will need our *private* queries interface, the one you only get if
you're logged in.

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: RatingsDB

Similar to before, we have an authorizer that allows everyone access to the
public ratings:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: RatingsViewer

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: authorizeRatingsViewer

But now, we have the slight additional complexity of *conditional*
authorization.  Our authenticated-user authorization, ``FoodCritic``, needs to
return ``None`` from its authorizer if you're not logged in:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: FoodCritic

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_db.py
   :pyobject: authorizeFoodCritic

``SQLSessionProcurer`` provides built-in authorizers for Klein's built-in
account functionality, ``ISimpleAccountBinding`` and ``ISimpleAccount``.  So
here we ask the session to authorize us an ``ISimpleAccountBinding`` to see
which accounts our session is bound to.  If it we find one, then we can return
a ``FoodCritic`` wrapped around it; the ``FoodCritic`` remembers its user and
performs all its operations with that account ID.  If we can't, then we return
``None``.

.. note::

   The interfaces for ``ISimpleAccount`` and ``ISimpleAccountBinding`` begin
   with the word "simple" because Klein's built-in account system is
   deliberately simplistic.  It is intended to be easy to get started with and
   suitable for light production workloads, but is not intended to be an
   all-encompassing way that all Klein applications should perform their
   account management; not all systems have usernames, not all systems have
   passwords, and not all systems use a relational database.

   If you have your own existing datastore, your own way of accessing your
   RDBMS, or your own authentication system, you will want to look into
   implementing your own version of the ``ISessionStore`` and ``ISession``
   interfaces; in particular ``ISession.authorize`` is the back-end for
   ``Authorization``.  Once you have one, you can set up your ``ISession``
   prerequisite to use ``SessionProcurer`` with your own ``ISessionStore``, and
   all the route-level logic ought to look similar, modulo whatever access
   pattern your data store requires.

So now our database and model supports our new authenticated/unauthenticated
distinction.  But this doesn't do us any good if we can't sign up for the site,
or log in to it.  So let's make some routes that can do just that:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_auth_routes.py
   :pyobject: signup

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_auth_routes.py
   :pyobject: showSignup

We have another form following the example set in the previous section.
``signup`` presents a form with a username and 2 password fields.  Ensuring
that those fields match is left as an exercise for the reader, but we request
an ``Authorization`` for ``ISimpleAccountBinding``.  Once again, this
authorizer is built in to the SQL session store and is available to any user.
We create an account and send the user over to ``/login``.  Then we render the
form in the same way as any other form, with ``Form.rendererFor``.

Having successfully signed up, now we need to log in.

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_auth_routes.py
   :pyobject: login

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_auth_routes.py
   :pyobject: loginForm

Our login form looks a lot like our signup form, but instead calls
``bindIfCredentialsMatch`` with the username/password credentials that we've
received.  This returns the bound account if the credentials match, but
``None`` otherwise.  Finally, we need a way to log out as well:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_auth_routes.py
   :pyobject: logout

Here we demonstrate customizing the text on the submit button for the form,
since we need *some* field to indicate this is indeed a form post processor;
including an explicit “submit” field is how you mark an effectively no-argument
form as a POSTable form route.  Plus, it wouldn't make sense for the rendered
button to say “submit” with no context; “log out” makes a lot more sense.

.. note::

   If you want to interact with a session store directly in, i.e. an
   administrative command line tool rather than a Klein route, you can
   instantiate a ``klein.storage.sql.SessionStore`` directly with an
   ``AsyncConnection``, rather than using ``SQLSessionProcurer``, which needs
   an HTTP request.

That's sign-up, login, and logout handled.  Now we need to change the way that
our application routes actually handle authorization to deal with our new
logged-in/logged-out split.  First, let's look at our food-rating post handler:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_routes.py
   :pyobject: notLoggedIn

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_routes.py
   :pyobject: postHandler

Not much has changed here; we still have an ``Authorization`` that requests a
``FoodCritic`` and calls a method on it.  The only difference here is that
*this method will no longer be called* if the user is not logged in; instead,
the resource specified by ``whenDenied`` - in other words, the simple templated
page from ``notLoggedIn`` - will be displayed.

But surely we don't even want to *show* the form to the user if they're not
logged in, right?  Just the top ratings, with the option to log in.  How can we
accomplish that?  We don't want the presence of an ``Authorization`` requesting
the ``FoodCritic`` on the front page to simply *fail* and show the user an
error, that would be a pretty annoying user experience.  What we use here is an
``Authorization`` with ``required=False`` ; that will give us a conditional
authorization that passes ``None`` if it cannot be authorized, so we take a
``FoodCritic | None`` as our parameter, like so:

.. literalinclude:: codeexamples/foodwiki/auth/foodwiki_routes.py
   :pyobject: frontPage

We require an ``Authorization`` for a ``FoodCritic`` conditionally, but we
require ``RatingsViewer`` unconditionally, mirroring the way the page is
actually displayed.  We want to see the top ratings regardless, but the form
only when we're logged in.  Note that our ``topRatings`` method is now giving
us ``NamedRating`` objects, and thus we use a new ``linkedFood`` fragment to
display them with a hyperlink.
