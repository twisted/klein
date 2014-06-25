def load_extensions():
	"""Load extensions.

	Returns dictionary of extension modules.
	Keys of the dictionary are the named under which given modules should be made available in this package.
	"""
	import pkgutil

	prefix = "klein_"
	rv = {}

	for (loader, name, ispkg) in pkgutil.iter_modules():
		if name.startswith(prefix):
			module = __import__(name)
			rv[name[len(prefix):]] = module

	return rv

exts = load_extensions()
globals().update(exts)
del load_extensions
del exts