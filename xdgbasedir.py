# http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

import os
import sys

pname = os.getenv ('PACKAGE_NAME', os.path.basename (sys.argv[0]))

__all__ = (
	########## These functions should be used. ###############
	# Set the name of the package the main program is part of.  Default: basename of executable without extension.
	'packagename',
	# Save or load a config file in a standard format (defined by this module).
	'config_save',
	'config_load',
	# Get filenames for reading or writing.
	'data_filename_write',
	'data_files_read',
	'cache_filename_write',
	'cache_filename_read',
	'runtime_filename_write',	# This must not be called if XDG_RUNTIME_DIR is not set.
	'runtime_filename_read',	# This must not be called if XDG_RUNTIME_DIR is not set.

	########## These functions and variables should most likely not be used; they are only here for completeness. ###############
	# XDG environment variables, or their defaults.
	'XDG_CONFIG_HOME',
	'XDG_CONFIG_DIRS',
	'XDG_DATA_HOME',
	'XDG_DATA_DIRS',
	'XDG_CACHE_HOME',
	'XDG_RUNTIME_DIR',	# Note that this one doesn't have a default.
	# Get config filenames for reading or writing.
	'config_filename_write',
	'config_files_read',
	)

def packagename (name):
	global pname
	pname = name

def protect (data, extra = ''):
	ret = ''
	extra += '%'
	for x in data:
		o = ord (x)
		if o < 32 or o >= 127 or x in extra:
			ret += '%%%02x' % o
		else:
			ret += x
	return ret

def unprotect (data):
	ret = ''
	while len (data) > 0:
		if data[0] == '%':
			ret += chr (int (data[1:3], 16))
			data = data[3:]
		else:
			if 32 <= ord (data[0]) < 127:
				# newlines can happen; only this range is valid.
				ret += data[0]
			data = data[1:]
	return ret

HOME = os.path.expanduser ('~')

# Configuration files.
XDG_CONFIG_HOME = os.getenv ('XDG_CONFIG_HOME', os.path.join (HOME, '.config'))
XDG_CONFIG_DIRS = tuple ([XDG_CONFIG_HOME] + os.getenv ('XDG_CONFIG_DIRS', '/etc/xdg').split (':'))
# Low level.
def config_filename_write (filename = None, packagename = None):
	if filename is None:
		filename = (packagename or pname) + os.extsep + 'txt'
	return os.path.join (XDG_CONFIG_HOME, (packagename or pname), filename)
def config_files_read (filename = None, packagename = None):
	if not filename:
		filename = (packagename or pname) + os.extsep + 'txt'
	ret = []
	for d in XDG_CONFIG_DIRS:
		p = os.path.join (d, (packagename or pname), filename)
		if os.path.exists (p):
			ret.append (p)
	return ret
# High level.
def config_save (config, filename = None, packagename = None):
	target = config_filename_write (filename, packagename)
	d = os.path.dirname (target)
	if not os.path.exists (d):
		os.makedirs (d)
	keys = config.keys ()
	keys.sort ()
	with open (target, 'w') as f:
		for key in keys:
			f.write ('%s=%s\n' % (protect (key, '='), protect (config[key])))
def config_load (filename = None, packagename = None, defaults = None, argv = None):
	'''Load configuration.
	The defaults argument should be set to a dict of possible arguments,
	with their defaults as values.  Required argument are given a value
	of None.'''
	ret = {}
	if defaults:
		# Allow overriding values from the commandline; require them if the default is set to None.
		assert 'configfile' not in defaults
		assert 'saveconfig' not in defaults
		import argparse
		a = argparse.ArgumentParser ()
		a.add_argument ('--configfile')
		a.add_argument ('--saveconfig', nargs = '?', default = False)
		for k in defaults:
			if defaults[k] is None:
				a.add_argument ('--' + k, help = 'required if not in config file')
			else:
				a.add_argument ('--' + k, help = 'default: %s' % defaults[k])
		args = a.parse_args (argv)
		for k in defaults:
			if getattr (args, k.replace ('-', '_')) is not None:
				ret[k] = getattr (args, k.replace ('-', '_'))
	files = config_files_read (args.configfile if defaults and args.configfile else filename, packagename)
	for name in files:
		with open (name) as f:
			for l in f.xreadlines ():
				key, value = l.split ('=', 1)
				key = unprotect (key)
				if key in ret:
					continue
				ret[key] = unprotect (value)
	if defaults:
		for k in defaults:
			if k not in ret:
				if defaults[k] is None:
					sys.stderr.write ('Required but not defined: %s\n' % k)
					sys.exit (1)
				ret[k] = defaults[k]
		if args.saveconfig != False:
			config_save (ret, args.configfile if defaults and args.configfile else filename, packagename)
	return ret

XDG_DATA_HOME = os.getenv ('XDG_DATA_HOME', os.path.join (HOME, '.local', 'share'))
XDG_DATA_DIRS = tuple ([XDG_DATA_HOME] + os.getenv ('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split (':'))
# Low level only; high level is too application-specific.
def data_filename_write (filename, makedirs = True, packagename = None):
	targetdir = os.path.join (XDG_DATA_HOME, (packagename or pname))
	target = os.path.join (targetdir, filename)
	if makedirs:
		if not os.path.exists (targetdir):
			os.makedirs (targetdir)
	return target
def data_files_read (filename, packagename = None):
	ret = []
	for d in XDG_DATA_DIRS:
		p = os.path.join (d, (packagename or pname), filename)
		if os.path.exists (p):
			ret.append (p)
	return ret

XDG_CACHE_HOME = os.getenv ('XDG_CACHE_HOME', os.path.join (HOME, '.cache'))
# Low level only; high level is too application-specific.
def cache_filename_write (filename = None, makedirs = True, packagename = None):
	if filename is None:
		filename = (packagename or pname) + os.extsep + 'dat'
	target = os.path.join (XDG_CACHE_HOME, (packagename or pname), filename)
	if makedirs:
		d = os.path.dirname (target)
		if not os.path.exists (d):
			os.makedirs (d)
	return target
def cache_filename_read (filename = None, packagename = None):
	if filename is None:
		filename = (packagename or pname) + os.extsep + 'dat'
	p = os.path.join (XDG_CACHE_HOME, (packagename or pname), filename)
	if os.path.exists (p):
		return p
	return None

XDG_RUNTIME_DIR = os.getenv ('XDG_RUNTIME_DIR')
# Low level only; high level is too application-specific.
def runtime_filename_write (filename = None, makedirs = True, packagename = None):
	assert XDG_RUNTIME_DIR
	if filename is None:
		filename = (packagename or pname)
	target = os.path.join (XDG_RUNTIME_DIR, (packagename or pname), filename)
	if makedirs:
		d = os.path.dirname (target)
		if not os.path.exists (d):
			os.makedirs (d)
	return target
def runtime_filename_read (filename = None, packagename = None):
	assert XDG_RUNTIME_DIR
	if filename is None:
		filename = (packagename or pname)
	p = os.path.join (XDG_RUNTIME_DIR, (packagename or pname), filename)
	if os.path.exists (p):
		return p
	return None
