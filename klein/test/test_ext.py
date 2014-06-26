"""Tests for extension modules."""
import imp
import re
import sys

from twisted.trial import unittest

class _VirtualModule(object):
	"""Object used to create virtual modules.

	To be used for testing purposes only.
	"""

	def __init__(self, name):
		self.name = name
		self.mod = imp.new_module(name)
		self.mod.__file__ = __name__

	def __enter__(self):
		sys.meta_path.append(self)
		return self.mod

	def __exit__(self, exc_type, exc_value, traceback):
		sys.meta_path.remove(self)
		name = self.name
		if name in sys.modules:
			assert sys.modules[name] is self.mod
			sys.modules.pop(name)

	# "finder" object methods (meta_path element interface)
	def find_module(self, name, path=None):
		if name == self.name:
			return self
		return None

	# "loader" object interface
	def load_module(self, name):
		assert name == self.name, (name, self.name)
		sys.modules[name] = self.mod
		return self.mod

	def iter_modules(self, prefix=""):
		return [
			(prefix + self.name, True)
		]

class KleinExtTestCase(unittest.TestCase):

	def test_empty_ext(self):
		"""Test "no extensions installed" case."""

		import klein.ext as ext
		reload(ext)

		for name in dir(ext):
			# Only magic fields are expected to be present.
			self.assertTrue(re.match(r"__\w+__", name), name)

		self.assertRaises(ImportError, __import__, "klein.ext.something")

	def test_ext_present(self):
		"""Test case when an extension is present."""

		name = "test_ext_present"
		fqn = "klein_{0}".format(name)

		with _VirtualModule(fqn) as mod:
			self.assertIs(__import__(fqn), mod)

			import klein.ext as ext
			reload(ext)

			self.assertIn(name, dir(ext))
			self.assertIs(getattr(ext, name), mod)

			# Test alternative import format
			from klein.ext import test_ext_present as testExt
			self.assertIs(testExt, mod)

		self.assertRaises(ImportError, __import__, fqn)

	def test_two_exts_present(self):
		"""Test that extension loader loads multiple extensions."""
		
		a = "ext_1"
		b = "ext_2"
		fqn = lambda name: "klein_{0}".format(name)

		with _VirtualModule(fqn(a)) as mod_a:
			with _VirtualModule(fqn(b)) as mod_b:
				import klein.ext as ext
				reload(ext)

				self.assertIn(a, dir(ext))
				self.assertIn(b, dir(ext))

				self.assertIs(getattr(ext, a), mod_a)
				self.assertIs(getattr(ext, b), mod_b)