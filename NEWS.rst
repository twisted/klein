NEWS
====

.. towncrier release notes start

Klein 15.0.0 - 2015-01-11
=========================
 * [BUG] Klein now includes its test package as part of the distribution. [`#65 <https://github.com/twisted/klein/pull/65>`_]

Klein 14.0.0 - 2014-12-18
=========================
 * [BUG] Klein now attempts to decode non-ASCII URLs as UTF-8 and serves a 400 if that fails instead of always serving a 500. [`#62 <https://github.com/twisted/klein/pull/62>`_]

Klein 0.2.3 - 2014-01-14
========================
 * [BUG] Klein now correctly handles producing resources [`#30 <https://github.com/twisted/klein/pull/30>`_]
 * [ENHANCEMENT] Klein now supports using tox for local testing [`#36 <https://github.com/twisted/klein/pull/36>`_]
 * [ENHANCEMENT] Klein has improved tests and an expanded range of test platforms [`#33 <https://github.com/twisted/klein/pull/33>`_, `#35 <https://github.com/twisted/klein/pull/35>`_, `#37 <https://github.com/twisted/klein/pull/37>`_]

Klein 0.2.2 - 2013-11-21
========================
 * [ENHANCEMENT] Klein.handle_errors now allows the definition of custom error handling behavior. [`#26 <https://github.com/twisted/klein/pull/26>`_]

Klein 0.2.1 - 2013-07-23
========================
 * [BUG] Klein has been updated to support the latest werkzeug release: [`#21 <https://github.com/twisted/klein/pull/21>`_]
 * [BUG] request.URLPath inside a handler points to the correct path. [`#15 <https://github.com/twisted/klein/pull/15>`_]
 * [ENHANCEMENT] IKleinRequest(request).url_for is supported: [`#16 <IKleinRequest(request).url_for>`_]

Klein 0.2.0 - 2013-02-27
========================
 * [BUG] Remove support for implicit branch routes. [`#12 <https://github.com/twisted/klein/pull/12>`_]
 * [FEATURE] Support creating Klein apps that are bound to an instance of a class. [`#9 <https://github.com/twisted/klein/pull/9>`_]

Klein 0.1.1 - 2013-02-25
========================
 * Include headers when handling werkzeug HTTPExceptions.

Klein 0.1.0 - 2013-01-04
========================
 * Initial release
