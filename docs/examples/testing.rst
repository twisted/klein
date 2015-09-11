=================================
Example -- Testing Your Klein App
=================================

Writing tests is important: untested code is buggy code.
The best approach is to use Twisted's ``treq`` to generate requests to your Klein app.
This avoids the need to use ``urllib`` or other approaches to generating requests that require spinning up an entire app instance and thus introducing confounding factors.

Here are some tests that show this approach.
All of them test code from other parts of Klein's documentation.

.. code goes here.
