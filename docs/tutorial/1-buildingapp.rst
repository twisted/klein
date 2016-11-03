==============
Klein Tutorial
==============

In this tutorial we're going to build simple book library in Twisted Klein. Index
page will list all available items. If user clicks
on book link we'll download book text asynchronously and display result.

Setting up
==========

Database for this tutorial is available in Klein github repo. 
We'll assume you have requirements installed. Aside from Klein you also
need to install Jinja2_ for templating and Twisted-Treq_

.. _Twisted-Treq: https://github.com/twisted/treq
.. _Jinja2: http://jinja.pocoo.org/

Index Page
==========

Main page of our book library will simply list all the books we have in our possession.
To actually show books we need to do two things. First we need to connect to database and 
get list of our books. Then we need to display books in html. 
It will be easier to generate HTML using some templating engine. One popular choice is Jinja2. 
We will store templates in templates directory, and create
simple html file with following contents:


.. literalinclude:: code/templates/homepage.html

Now we need to write our app and tell it to display books. We'll write two
route handlers. One will serve our index page. Other one will serve static files. There
will be only one static file for now - css file with Twitter Bootstrap_ styling. It will
make our raw html template look pretty. Usually serving static files is better done with
some external web server (e.g. nginx or apache), but for the purposes of tutorial we'll
just serve them from web application.


.. _Bootstrap: http://getbootstrap.com/

.. literalinclude:: code/index_sync.py

Index Async
===========

Twisted Klein is asynchronous. Does it mean that above code will
be asynchronous? Unfortunatenly no. Just using Twisted Klein doesn't make your
code magically asynchronous. Above code is still synchronous it will still block. 
If your database is overloaded and one query takes long time other clients
asking for data will need to wait. How can we make our code asynchrous then?

In order to make our code asynchronous we need to make use of async API. Klein is just a
wrapper for Twisted, making it slightly easier to use for web applications. If you want to make your code
asynchronous you need to use Twisted asynchronous API. Main element of this API
is Deferred_. You need to use them to benefit from asynchronous request processing.

In case of above index page we need to use Twisted adbapi_. SQL query will be transformed
into Deferred and executed asynchronously.

.. literalinclude:: code/index_async.py

There are following important elements of above code sample. First you need to remember
that database query does not return result immediately. `dbpool.runQuery` does not return a
result. If you start debugger on next line after `runQuery` and investigate content of dfd
variable you'll find it contains only a Defferred object and not list of results obtained from
a database. We attach callback `got_sql_results` to this Deferred. 
When database processing is done this callback will fire and `got_sql_results`
will receive list of results as single argument. This list will be returned to client.

.. _adbapi: https://twistedmatrix.com/documents/current/core/howto/rdbms.html
.. _Deferred: https://twistedmatrix.com/documents/current/core/howto/defer.html

Make HTTP Request From Server
====================================

Deferreds are most useful when you deal with network operations. For example
fetching resource from remote HTTP server is much more efficient when done
in asynchronous manner. In our library this is we'll need async HTTP requests
to download text of our books from external website. Let's write code
that will do this using Deferreds. 

Our database stores file ids, but let's assume that for some reason 
we dont want to redirect users to remote website. We would like to limit the load on project 
Gutenberg by serving books ourselves (and perhaps caching downloads in the future).

We'll add new route to our application. If user clicks on link our application will
download book text from project Gutenberg, show it to the user and save file in local filesystem.
Download will be performed on the server side in our Klein app.

.. literalinclude:: code/download_book.py

You can see above code uses couple of Deferreds. First it generates async SQL query
that fetches result from database. After callback of this Deferred fires with results
we launch another Deferreds with HTTP download of book text. This fires again with
downloaded response and returns yet another Deferred that reads response content
asynchronously. At the end of the process user gets book text.

Structuring Your App
====================

Up till now we defined our routes as Python functions. This is good for quick
prototyping but is not very practical. Your application usually need to have access
to some non-global state, for example, as we'll see in next step you'll need to keep
track of user sessions. To make your app easier to maintain it is much better to
create App object and define routes as method of this object. For example 
skeleton of your app could look like this:

.. literalinclude:: code/app_object.py

Handling User Sessions
======================

Most web applications need to handle user sessions. How do we do this in Twisted
Klein? Let's add simple login functionality to our library.

.. literalinclude:: code/login.py

Above code keeps dictionary of users as attribute of application, /login url will
display simple login page (generated from Jinja template). Login form makes POST
to /do_login handler where we check username and password and set session cookie.
Setting cookies makes use of Twisted Sessions_. 

.. _Sessions: http://twistedmatrix.com/documents/current/web/howto/web-in-60/session-basics.html
