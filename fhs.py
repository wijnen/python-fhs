# This module implements fhs directory support in Python.
# vim: set fileencoding=utf-8 foldmethod=marker :

# {{{ Copyright 2013-2016 Bas Wijnen <wijnen@debian.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or(at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# }}}

# File documentation. {{{
'''@mainpage
This module makes it easy to find files in the locations that are defined for
them by the FHS.  Some locations are not defined there.  This module chooses a
location for those.

It also defines a configuration file format which is used automatically when
initializing this module.
'''

'''@file
This module makes it easy to find files in the locations that are defined for
them by the FHS.  Some locations are not defined there.  This module chooses a
location for those.

It also defines a configuration file format which is used automatically when
initializing this module.
'''

'''@package fhs Module for using paths as described in the FHS.
This module makes it easy to find files in the locations that are defined for
them by the FHS.  Some locations are not defined there.  This module chooses a
location for those.

It also defines a configuration file format which is used automatically when
initializing this module.
'''
# }}}

# Paths and how they are handled by this module: {{{
# /etc			configfile
# /run			runtimefile
# /tmp			tempfile
# /usr/lib/package	datafile
# /usr/local		datafile
# /usr/share/package	datafile
# /var/cache		cachefile
# /var/games		datafile
# /var/lib/package	datafile
# /var/lock		lockfile
# /var/log		logfile
# /var/spool		spoolfile
# /var/tmp		tempfile?

# /home			(xdgbasedir)
# /root			(xdgbasedir)
# /bin			-
# /boot			-
# /dev			-
# /lib			-
# /lib<qual>		-
# /media		-
# /mnt			-
# /opt			-
# /sbin			-
# /srv			-
# /usr/bin		-
# /usr/include		-
# /usr/libexec		-
# /usr/lib<qual>	-
# /usr/sbin		-
# /usr/src		-
# /var/lib		-
# /var/opt		-
# /var/run		-

# FHS: http://www.linuxbase.org/betaspecs/fhs/fhs.html
# XDG basedir: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

# So: configfile, runtimefile, tempfile, datafile, cachefile, lockfile, logfile, spoolfile
# }}}

# Imports. {{{
import os
import sys
import shutil
import argparse
import tempfile
import atexit
# }}}

# Globals. {{{
## Flag that is set to True when init() is called.
initialized = False
## Flag that is set during init() if --system was specified, or the application set the system parameter to init().
is_system = False
## Flag that is set during init() if the application set the game parameter to init().
is_game = False
## Default program name; can be overridden from functions that use it.
pname = os.getenv('PACKAGE_NAME', os.path.basename(sys.argv[0]))
## Current user's home directory.
HOME = os.path.expanduser('~')
# Internal variables.
_tempfiles = []
_configs = {}
_moduleconfig = {}
_base = os.path.abspath(os.path.dirname(sys.argv[0]))
# }}}

# Configuration files. {{{
## XDG home directory.
XDG_CONFIG_HOME = os.getenv('XDG_CONFIG_HOME', os.path.join(HOME, '.config'))
## XDG config directory search path.
XDG_CONFIG_DIRS = tuple([XDG_CONFIG_HOME] + os.getenv('XDG_CONFIG_DIRS', '/etc/xdg').split(':'))

# config read/write helpers {{{
def _protect(data, extra = ''):
	ret = ''
	extra += '\\'
	for x in str(data):
		o = ord(x)
		if o < 32 or o >= 127 or x in extra:
			ret += '\\%x;' % o
		else:
			ret += x
	return ret

def _unprotect(data):
	ret = ''
	while len(data) > 0:
		if data[0] == '%':
			l = data.index(';')
			ret += chr(int(data[1:l], 16))
			data = data[l + 1:]
		else:
			if 32 <= ord(data[0]) < 127:
				# newlines can happen; only this range is valid.
				ret += data[0]
			data = data[1:]
	return ret
# }}}

def module_init(modulename, config): # {{{
	'''Add configuration for a module.
	Register configuration options for a module.  This must be called
	before init().  After init(), the values can be retrieved with
	module_get_config().
	@param modulename: Name of the requesting module.  Options get
		--modulename- prefixed to them.
	@param config: Configuration dict, with the same format as the
		parameter for init().
	@return None.
	'''
	assert not initialized
	assert modulename not in _configs
	_configs[modulename] = config
	_moduleconfig[modulename] = {}
# }}}

def module_get_config(modulename): # {{{
	'''Retrieve module configuration.
	A module can add configuration options by calling module_init() before
	the program calls init().  This function is used to retrieve the
	configuration.  If init() has not been called yet, it will be called
	with an empty configuration.
	@param modulename: Name of the module.  Must be identical to the name
		that was passed to module_init().
	@return configuration dict, with the same format as the return value of
		init().  This dict does not include the automatic module prefix
		of the module options.
	'''
	if not initialized:
		init({})
	return _moduleconfig[modulename];
# }}}

def init(config, packagename = None, system = None, game = False):	# {{{
	'''Initialize the module.
	This function must be called before any other in this module (except
	module_init(), which must be called before this function).
	Configuration is read from the commandline, and from the configuration
	files named <packagename>.ini in any of the configuration directories,
	or specified with --configfile.  A configuration file must contain
	name=value pairs.  The configuration that is used can be saved using
	--saveconfig, which can optionally have the filename to save to as a
	parameter.
	@param config: Configuration dict.
		Keys are the configuration options.  These can be used in a
		configuration file, or prefixed with -- and passed on the
		commandline.  'help', 'configfile', 'saveconfig' and 'system'
		are always handled by this module and must not be in the dict.
		The value of the item is the default value for the option, or
		None if it is a required option.  The given argument is
		converted to the type of the default value.  Boolean values are
		True if they are "1", "yes", or "true", and False if they are
		"0", "no", or "false" (all case insensitive).  A custom
		conversion function can be specified by using a tuple of
		(default, function) where default is the default value, and
		function is the conversion function.
	@param packagename: The name of the program.  This is used as a default
		for all other functions.  It has a default of the basename of
		the program.
	@param system: If True, system paths will be used for writing and user
		paths will be ignored for reading.
	@param game: If True, game system directories will be used (/usr/games,
		/usr/share/games, etc.) instead of regular system directories.
	@return Configuration from commandline and config file.
		This is a dict with the same keys as were passed in the config
		parameter, with the values that were specified as their values.  
	'''
	global initialized
	assert not initialized
	global pname
	if packagename is not None:
		pname = packagename
	global is_game
	is_game = game
	ret = {}
	# Allow overriding values from the commandline; require them if the default is set to None.
	assert 'configfile' not in config
	assert 'saveconfig' not in config
	assert 'system' not in config
	import argparse
	a = argparse.ArgumentParser()
	a.add_argument('--configfile', help = 'default: ' + (packagename or pname) + os.extsep + 'ini')
	a.add_argument('--saveconfig', nargs = '?', default = False)
	if system is None:
		a.add_argument('--system', action = 'store_true')
	def add_arg(key, value):
		if isinstance(value, (tuple, list)):
			default = value[0]
		else:
			default = value
		if default is None:
			h = 'required if not in config file'
		else:
			h = 'default: %s' % default
		a.add_argument('--' + key, help = h)
	for k in config:
		add_arg(k, config[k])
	for m in _configs:
		for k in _configs[m]:
			add_arg(m + '-' + k, _configs[m][k])
	args = a.parse_args()
	for k in config:
		if getattr(args, k.replace('-', '_')) is not None:
			ret[k] = getattr(args, k.replace('-', '_'))
	for m in _configs:
		for k in _configs[m]:
			value = getattr(args, m + '_' + k.replace('-', '_'))
			if value is not None:
				_moduleconfig[m][k] = value
	filename = args.configfile if args.configfile else (packagename or pname) + os.extsep + 'ini'
	for d in XDG_CONFIG_DIRS:
		p = os.path.join(d, (packagename or pname), filename)
		if os.path.exists(p):
			with open(p) as f:
				for l in f:
					key, value = l.split('=', 1)
					key = _unprotect(key)
					if key in ret:
						continue
					ret[key] = _unprotect(value)
		for m in _configs:
			p = os.path.join(d, m + os.extsep + 'ini')
			if os.path.exists(p):
				with open(p) as f:
					for l in f.readlines():
						key, value = l.split('=', 1)
						key = _unprotect(key)
						if key in _moduleconfig[m]:
							continue
						_moduleconfig[m][key] = _unprotect(value)
	def convert(value, conf):
		if conf is None:
			return value
		if isinstance(conf, (tuple, list)) and len(conf) >= 2:
			return conf[1](value)
		if isinstance(conf, bool) and isinstance(value, str):
			v = value.lower()
			assert v in ('0', '1', 'true', 'false', 'yes', 'no')
			return v in ('1', 'true', 'yes')
		return type(conf)(value)
	for k in config:
		if k not in ret:
			if config[k] is None:
				sys.stderr.write('Required but not defined: %s\n' % k)
				sys.exit(1)
			ret[k] = config[k]
		else:
			ret[k] = convert(ret[k], config[k])
	for m in _configs:
		for k in _configs[m]:
			if k not in _moduleconfig[m]:
				if _configs[m][k] is None:
					sys.stderr.write('Required but not defined: %s-%s\n' % (m, k))
					sys.exit(1)
				_moduleconfig[m][k] = _configs[m][k]
			else:
				_moduleconfig[m][k] = convert(_moduleconfig[m][k], _configs[m][k])
	initialized = True
	if args.saveconfig != False:
		save_config(ret, args.configfile if config and args.configfile else filename, packagename)
	global is_system
	if system is None:
		is_system = args.system
	else:
		is_system = system
	@atexit.register
	def clean_temps():
		for f in _tempfiles:
			shutil.rmtree(f, ignore_errors = True)
	return ret
# }}}

def save_config(config, name = None, packagename = None):	# {{{
	'''Save a dict as a configuration file.
	Write the config dict to a file in the configuration directory.  The
	file is named <packagename>.ini, unless overridden.
	@param config: The data to be saved.  All values are converted to str.
	@param name: The name of the file to be saved.  ".ini" is appended to
		this.
	@param packagename: Override for the name of the package, to determine
		the directory to save to.
	'''
	assert initialized
	if name is None:
		filename = (packagename or pname) + os.extsep + 'ini'
	else:
		filename = os.path.join(packagename or pname, name + os.extsep + 'ini')
	d = '/etc/xdg' if is_system else XDG_CONFIG_HOME
	target = os.path.join(d, filename)
	d = os.path.dirname(target)
	if not os.path.exists(d):
		os.makedirs(d)
	keys = list(config.keys())
	keys.sort()
	with open(target, 'w') as f:
		for key in keys:
			f.write('%s=%s\n' % (_protect(key, '='), _protect(config[key])))
# }}}
# }}}

# Runtime files. {{{
## XDG runtime directory.  Note that XDG does not specify a default for this.  This module uses /run as the default for system services.
XDG_RUNTIME_DIR = os.getenv('XDG_RUNTIME_DIR')
def _runtime_get(name, packagename, dir):
	assert initialized
	if name is None:
		if dir:
			name = packagename or pname
		else:
			name = (packagename or pname) + os.extsep + 'txt'
	else:
		name = os.path.join(packagename or pname, name)
	d = '/run' if is_system else XDG_RUNTIME_DIR
	target = os.path.join(d, name)
	d = target if dir else os.path.dirname(target)
	return d, target

def write_runtime(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a runtime file for writing.
	@param name: Filename to open.  Defaults to the program name.
	@param text: If True (the default), open the file in text mode.  This parameter is ignored if the file is not opened.
	@param dir: If True, create a directory instead of a file.  Defaults to False.
	@param opened: If True (the default), return the open file.  For directories, the target is not created if this is set to False.
	@param packagename: Override the packagename.
	@return The opened file, or the file or directory name.
	'''
	d, target = _runtime_get(name, packagename, dir)
	if opened and not os.path.exists(d):
		os.makedirs(d)
	return open(target, 'w+' if text else 'w+b') if opened and not dir else target

def read_runtime(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a runtime file for reading.
	@param name: Filename to open.  Defaults to the program name.
	@param text: If True (the default), open the file in text mode.  This parameter is ignored if the file is not opened.
	@param dir: If True, find a directory instead of a file.  Defaults to False.
	@param opened: If True (the default), return the open file.  For directories, this is ignored.
	@param packagename: Override the packagename.
	@return The opened file, or the file or directory name.
	'''
	d, target = _runtime_get(name, packagename, dir)
	if os.path.exists(target) and (dir if os.path.isdir(target) else not dir):
		return open(target, 'r' if text else 'rb') if opened and not dir else target
	return None

def remove_runtime(name = None, dir = False, packagename = None):
	'''Remove a reuntime file or directory.
	A directory is removed recursively.  All parameters must be the same as what was passed to write_runtime() when the file was created.
	@param name: Target to remove.
	@param dir: If True, remove a directory instead of a file.  Defaults to False.
	@param packagename: Override the packagename.
	@return None.
	'''
	assert initialized
	if dir:
		shutil.rmtree(read_runtime(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_runtime(name, False, False, False, packagename))
# }}}

# Temp files. {{{
class _TempFile(object):
	def __init__(self, f, name):
		# Avoid calling file.__setattr__.
		object.__setattr__(self, '_file', f)
		object.__setattr__(self, 'filename', name)
	def remove(self):
		assert initialized
		assert self.filename is not None
		self.close()
		os.unlink(self.filename)
		_tempfiles.remove(self.filename)
		object.__setattr__(self, '_file', None)
		object.__setattr__(self, 'filename', None)
	def __getattr__(self, k):
		return getattr(self._file, k)
	def __setattr__(self, k, v):
		return setattr(self._file, k, v)
	def __enter__(self):
		return self
	def __exit__(self, exc_type, exc_value, traceback):
		self.remove()
		return False

def write_temp(dir = False, text = True, packagename = None):
	'''Open a temporary file for writing.
	The file is automatically removed when the program exits.  If this
	function is used in a with statement, the file is removed when the
	statement finishes.

	Unlike other write_* functions, this one has no option to get the
	filename without opening the file, because that is a security risk for
	temporary files.  However, the returned object is really a wrapper that
	looks like a file, but has one extra attribute: "filename".  This can
	be used in cases where for other file types "opened = False" would be
	appropriate.  It also has an extra method: "remove".  This takes no
	arguments and removes the file immediately.  "remove" should not be
	called multiple times.
	@param dir: If False (the default), a file is created.  If True, a
		directory is created and the name is returned.  On remove, the
		directory contents are recursively removed.
	@param text: If True (the default), the file is opened in text mode.
		This parameter is ignored if dir is True.
	@param packagename: Override the packagename.
	@return The file, or the name of the directory.
	'''
	assert initialized
	if dir:
		ret = tempfile.mkdtemp(prefix = (packagename or pname) + '-')
		_tempfiles.append(ret)
	else:
		f = tempfile.mkstemp(text = text, prefix = (packagename or pname) + '-')
		_tempfiles.append(f[1])
		ret = _TempFile(os.fdopen(f[0], 'w+' if text else 'w+b'), f[1])
	return ret

def remove_temp(name):
	'''Remove a temporary directory.
	Temporary files are removed by closing them.  Directories are removed
	by calling this function.  They are also removed when the program ends
	normally.
	@param name: The name of the directory, as returned by write_temp.
	@return None.
	'''
	assert initialized
	assert name in _tempfiles
	_tempfiles.remove(name)
	shutil.rmtree(name, ignore_errors = False)
# }}}

# Data files. {{{
## XDG data directory.
XDG_DATA_HOME = os.getenv('XDG_DATA_HOME', os.path.join(HOME, '.local', 'share'))
## XDG data directory search path.
XDG_DATA_DIRS = os.getenv('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')

def write_data(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a data file for writing.  The file is not truncated if it exists.
	@param name: Name of the data file.
	@param text: Open as a text file if True (the default).
	@param dir: Create a directory if True, a file if False (the default).
	@param opened: Open or create the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = name if is_system else os.path.join(packagename or pname, name)
	if is_system:
		if is_game:
			if packagename and packagename != pname:
				d = os.path.join('/var/games', pname, packagename)
			else:
				d = os.path.join('/var/games', pname)
		else:
			if packagename and packagename != pname:
				d = os.path.join('/var/lib', pname, packagename)
			else:
				d = os.path.join('/var/lib', pname)
	else:
		d = XDG_DATA_HOME
	target = os.path.join(d, filename)
	if dir:
		if opened and not os.path.exists(target):
			os.makedirs(target)
		return target
	else:
		d = os.path.dirname(target)
		if opened and not os.path.exists(d):
			os.makedirs(d)
		return open(target, 'w+' if text else 'w+b') if opened else target

def read_data(name = None, text = True, dir = False, multiple = False, opened = True, packagename = None):
	'''Open a data file for reading.  The paramers should be identical to what was used to create the file with write_data().
	@param name: Name of the data file.
	@param text: Open as a text file if True (the default).
	@param dir: Return a directory name if True, a file or filename if False (the default).
	@param opened: Open the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = name
	seen = set()
	target = []
	if not is_system:
		t = os.path.join(XDG_DATA_HOME, filename if name is None else os.path.join(packagename or pname, name))
		if t not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(t)
			target.append(r)
	dirs = ['/var/local/lib', '/var/lib', '/usr/local/lib', '/usr/lib', '/usr/local/share', '/usr/share']
	if is_game:
		dirs = ['/var/local/games', '/var/games', '/usr/local/lib/games', '/usr/lib/games', '/usr/local/share/games', '/usr/share/games'] + dirs
	if packagename and packagename != pname:
		dirs = [os.path.join(x, pname, packagename) for x in dirs] + [os.path.join(x, packagename) for x in dirs]
	else:
		dirs = [os.path.join(x, pname) for x in dirs]
	if not is_system:
		dirs = [_base, os.path.curdir, packagename or pname] + [os.path.join(x, packagename or pname) for x in XDG_DATA_DIRS] + dirs
	for d in dirs:
		t = os.path.join(d, filename)
		if t not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(t)
			target.append(r)
	if multiple:
		return target
	else:
		return None

def remove_data(name = None, dir = False, packagename = None):
	'''Remove a data file.  Use the same parameters as were used to create it with write_data().
	@param name: The file to remove.
	@param dir: If True, remove a directory.  If False (the default), remove a file.
	@param packagename: Override the packagename.
	@return None.
	'''
	assert initialized
	if dir:
		shutil.rmtree(read_data(name, False, True, False, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_data(name, False, False, False, False, packagename))
# }}}

# Cache files. {{{
## XDG cache directory.
XDG_CACHE_HOME = os.getenv('XDG_CACHE_HOME', os.path.join(HOME, '.cache'))

def write_cache(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a cache file for writing.  The file is not truncated if it exists.
	@param name: Name of the cache file.
	@param text: Open as a text file if True (the default).
	@param dir: Create a directory if True, a file if False (the default).
	@param opened: Open or create the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = name if is_system else os.path.join(packagename or pname, name)
	d = os.path.join('/var/cache', packagename or pname) if is_system else XDG_CACHE_HOME
	target = os.path.join(d, filename)
	if dir:
		if opened and not os.path.exists(target):
			os.makedirs(target)
		return target
	else:
		d = os.path.dirname(target)
		if opened and not os.path.exists(d):
			os.makedirs(d)
		return open(target, 'w+' if text else 'w+b') if opened and not dir else target

def read_cache(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a cache file for reading.  The paramers should be identical to what was used to create the file with write_cache().
	@param name: Name of the cache file.
	@param text: Open as a text file if True (the default).
	@param dir: Return a directory name if True, a file or filename if False (the default).
	@param opened: Open the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = os.path.join(packagename or pname, name)
	target = os.path.join(XDG_CACHE_HOME, filename)
	if not os.path.exists(target):
		if name is None:
			filename = os.path.join(packagename or pname, packagename or pname + os.extsep + 'dat')
		d = '/var/cache'
		target = os.path.join(d, filename)
		if not os.path.exists(target):
			return None
	return open(target, 'r' if text else 'rb') if opened and not dir else target

def remove_cache(name = None, dir = False, packagename = None):
	'''Remove a cache file.  Use the same parameters as were used to create it with write_cache().
	@param name: The file to remove.
	@param dir: If True, remove a directory.  If False (the default), remove a file.
	@param packagename: Override the packagename.
	@return None.
	'''
	assert initialized
	if dir:
		shutil.rmtree(read_cache(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_cache(name, False, False, False, packagename))
# }}}

# Log files. {{{
def write_log(name = None, packagename = None):
	'''Open a log file for writing.
	There are not many options here; logfiles are always opened for append,
	never read, and never removed by the program.  Log directories can be
	created by specifying a directory as part of the name.
	@param name: Log filename.
	@param packagename: Override the packagename.
	@return The logfile, opened in text append mode.
	'''
	assert initialized
	if not is_system:
		return sys.stderr
	if name is None:
		filename = (packagename or pname) + os.extsep + 'log'
	else:
		filename = os.path.join(packagename or pname, name)
	target = os.path.join('/var/log', filename)
	d = os.path.dirname(target)
	if not os.path.exists(d):
		os.makedirs(d)
	return open(target, 'a')
# }}}

# Spool files. {{{
def write_spool(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a spool file for writing.  The file is not truncated if it exists.
	Users don't have spool directories by default.  A directory named
	"spool" in the cache directory is created for that.
	@param name: Name of the spool file.
	@param text: Open as a text file if True (the default).
	@param dir: Create a directory if True, a file if False (the default).
	@param opened: Open or create the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = os.path.join(packagename or pname, name)
	target = os.path.join('/var/spool' if is_system else os.path.join(XDG_CACHE_HOME, 'spool'), filename)
	d = os.path.dirname(target)
	if opened and not os.path.exists(d):
		os.makedirs(d)
	return open(target, 'w+' if text else 'w+b') if opened and not dir else target

def read_spool(name = None, text = True, dir = False, opened = True, packagename = None):
	'''Open a spool file for reading.  The paramers should be identical to what was used to create the file with write_spool().
	@param name: Name of the spool file.
	@param text: Open as a text file if True (the default).
	@param dir: Return a directory name if True, a file or filename if False (the default).
	@param opened: Open the file if True (the default), report the name if False.
	@param packagename: Override the packagename.
	@return The opened file, or the name of the file or directory.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = os.path.join(packagename or pname, name)
	target = os.path.join('/var/spool' if is_system else os.path.join(XDG_CACHE_HOME, 'spool'), filename)
	if not os.path.exists(target):
		return None
	return open(target, 'r' if text else 'rb') if opened and not dir else target

def remove_spool(name = None, dir = False, packagename = None):
	'''Remove a spool file.  Use the same parameters as were used to create it with write_spool().
	@param name: The file to remove.
	@param dir: If True, remove a directory.  If False (the default), remove a file.
	@param packagename: Override the packagename.
	@return None.
	'''
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	if dir:
		shutil.rmtree(read_spool(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_spool(name, False, False, False, packagename))
# }}}

# Locks. {{{
def lock(name = None, info = '', packagename = None):
	'''Acquire a lock.
	@todo locks are currently not implemented.
	'''
	assert initialized
	# TODO

def unlock(name = None, packagename = None):
	'''Release a lock.
	@todo locks are currently not implemented.
	'''
	assert initialized
	# TODO
# }}}
