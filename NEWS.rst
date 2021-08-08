NEWS
====

NEXT
-------------------
 * Python 2 is no longer supported by Klein.
 * Python 3.5 is no longer supported by Klein.
 * Python 3.9 is now supported by Klein. [`#412 <https://github.com/twisted/klein/pull/412>`_]
 * Fixed a compatibility issue with Twisted versions greater than 20.3.0 in Klein's test suite. [`#383 <https://github.com/twisted/klein/pull/383>`]
 * Fixed a compatibility issue with Werkzeug versions greater than 2.0 in Klein's test suite. [`#499 <https://github.com/twisted/klein/pull/499>`]
 * Klein has incomplete, but growing type hints, but ``py.typed`` is not installed, as they might not work well for most clients yet.
 * ``Plating`` now sets the ``Content-Type`` header to ``application/json`` instead of ``text/json; charset=utf8``.

20.6.0 - 2020-06-07
-------------------
 * This is the last release of Klein expected to support Python 2.
 * This is the last release of Klein expected to support Python 3.5.
 * Python 3.4 is no longer supported by Klein. [`#284 <https://github.com/twisted/klein/pull/284>`_]
 * Python 3.8 is now supported by Klein. [`#303 <https://github.com/twisted/klein/pull/303>`_]
 * ``klein.app.subroute`` is now also available as ``klein.subroute``. [`#293 <https://github.com/twisted/klein/pull/293>`_]
 * Support for forms and sessions. [`#276 <https://github.com/twisted/klein/pull/276>`_]
 * The ``Klein`` class now supports deep copy by implementing ``__copy__``. [`#74 <https://github.com/twisted/klein/pull/74>`_]

19.6.0 - 2019-06-07
-------------------

New "forms" and "sessions" subsystems provide official support for POST requests, including CSRF protection, form generation to include CSRF tokens, dependency injection to populate parameters from both the request and session, as well as lightweight JSON API support.

17.10.0 - 2017-10-22
--------------------

17.2.0 - 2017-03-03
-------------------

16.12.0 - 2016-12-13
--------------------

15.3.1 - 2015-12-17
-------------------

15.2.0 - 2015-11-30
-------------------

15.1.0 - 2015-07-08
-------------------

15.0.0 - 2015-01-11
-------------------
 * [BUG] Klein now includes its test package as part of the distribution. [`#65 <https://github.com/twisted/klein/pull/65>`_]

14.0.0 - 2014-12-18
-------------------
 * [BUG] Klein now attempts to decode non-ASCII URLs as UTF-8 and serves a 400 if that fails instead of always serving a 500. [`#62 <https://github.com/twisted/klein/pull/62>`_]

0.2.3 - 2014-01-14
------------------
 * [BUG] Klein now correctly handles producing resources [`#30 <https://github.com/twisted/klein/pull/30>`_]
 * [ENHANCEMENT] Klein now supports using tox for local testing [`#36 <https://github.com/twisted/klein/pull/36>`_]
 * [ENHANCEMENT] Klein has improved tests and an expanded range of test platforms [`#33 <https://github.com/twisted/klein/pull/33>`_, `#35 <https://github.com/twisted/klein/pull/35>`_, `#37 <https://github.com/twisted/klein/pull/37>`_]

0.2.2 - 2013-11-21
------------------
 * [ENHANCEMENT] Klein.handle_errors now allows the definition of custom error handling behavior. [`#26 <https://github.com/twisted/klein/pull/26>`_]

0.2.1 - 2013-07-23
------------------
 * [BUG] Klein has been updated to support the latest werkzeug release: [`#21 <https://github.com/twisted/klein/pull/21>`_]
 * [BUG] request.URLPath inside a handler points to the correct path. [`#15 <https://github.com/twisted/klein/pull/15>`_]
 * [ENHANCEMENT] IKleinRequest(request).url_for is supported: [`#16 <IKleinRequest(request).url_for>`_]

0.2.0 - 2013-02-27
------------------
 * [BUG] Remove support for implicit branch routes. [`#12 <https://github.com/twisted/klein/pull/12>`_]
 * [FEATURE] Support creating Klein apps that are bound to an instance of a class. [`#9 <https://github.com/twisted/klein/pull/9>`_]

0.1.1 - 2013-02-25
------------------
 * Include headers when handling werkzeug HTTPExceptions.

0.1.0 - 2013-01-04
------------------
 * Initial release
