# This module implements fhs directory support in Python.
# vim: set foldmethod=marker :

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
initialized = False
is_system = False
is_game = False
pname = os.getenv('PACKAGE_NAME', os.path.basename(sys.argv[0]))
HOME = os.path.expanduser('~')
tempfiles = []
# }}}

__all__ = ( # {{{
	# Call this function first, to set up the module and load the configuration.
	'init',
	# Save a changed configuration.
	'save_config',
	# Runtimefile
	'write_runtime',
	'read_runtime',
	# Tempfile
	'write_temp',
	# Datafile
	'write_data',
	'read_data',
	# Cachefile
	'write_cache',
	'read_cache',
	# Lock
	'lock',
	'unlock',
	# Logfile
	'write_log',
	# Spoolfile
	'write_spool',
	'read_spool',
	# Whether we are running as a system service.
	'is_system'
	)
# }}}

# Configuration files. {{{
XDG_CONFIG_HOME = os.getenv('XDG_CONFIG_HOME', os.path.join(HOME, '.config'))
XDG_CONFIG_DIRS = tuple([XDG_CONFIG_HOME] + os.getenv('XDG_CONFIG_DIRS', '/etc/xdg').split(':'))
# config read/write helpers {{{
def protect(data, extra = ''):
	ret = ''
	extra += '%'
	for x in data:
		o = ord(x)
		if o < 32 or o >= 127 or x in extra:
			ret += '%%%02x' % o
		else:
			ret += x
	return ret

def unprotect(data):
	ret = ''
	while len(data) > 0:
		if data[0] == '%':
			ret += chr(int(data[1:3], 16))
			data = data[3:]
		else:
			if 32 <= ord(data[0]) < 127:
				# newlines can happen; only this range is valid.
				ret += data[0]
			data = data[1:]
	return ret
# }}}

def init(config, packagename = None, system = None, game = False, argv = None):	# {{{
	'''Initialize the module.
	The config argument should be set to a dict of possible arguments,
	with their defaults as values.  Required arguments are given a value of None.
	packagename has a default of the basename of the program.
	If system is True, system paths will be used for writing and user paths will be ignored for reading.
	Returns configuration from commandline and config file.'''
	global pname
	if argv is None and packagename is not None:
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
	for k in config:
		if config[k] is None:
			a.add_argument('--' + k, help = 'required if not in config file')
		else:
			a.add_argument('--' + k, help = 'default: %s' % config[k])
	args = a.parse_args(argv)
	for k in config:
		if getattr(args, k.replace('-', '_')) is not None:
			ret[k] = getattr(args, k.replace('-', '_'))
	filename = args.configfile if args.configfile else (packagename or pname) + os.extsep + 'ini'
	for d in XDG_CONFIG_DIRS:
		p = os.path.join(d, (packagename or pname), filename)
		if os.path.exists(p):
			with open(p) as f:
				for l in f.xreadlines():
					key, value = l.split('=', 1)
					key = unprotect(key)
					if key in ret:
						continue
					ret[key] = unprotect(value)
	for k in config:
		if k not in ret:
			if config[k] is None:
				sys.stderr.write('Required but not defined: %s\n' % k)
				sys.exit(1)
			ret[k] = config[k]
	if args.saveconfig != False:
		save_config(ret, args.configfile if config and args.configfile else filename, packagename)
	global is_system
	if argv is None:
		if system is None:
			is_system = args.system
		else:
			is_system = system
	global initialized
	initialized = True
	@atexit.register
	def clean_temps():
		for f in tempfiles:
			shutil.rmtree(f, ignore_errors = True)
	return ret
# }}}

def save_config(config, name = None, packagename = None):	# {{{
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
	keys = config.keys()
	keys.sort()
	with open(target, 'w') as f:
		for key in keys:
			f.write('%s=%s\n' % (protect(key, '='), protect(config[key])))
# }}}
# }}}

# Runtime files. {{{
XDG_RUNTIME_DIR = os.getenv('XDG_RUNTIME_DIR')
def runtime_get(name, packagename, dir):
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
	d, target = runtime_get(name, packagename, dir)
	if opened and not os.path.exists(d):
		os.makedirs(d)
	return open(target, 'w+' if text else 'w+b') if opened and not dir else target

def read_runtime(name = None, text = True, dir = False, opened = True, packagename = None):
	d, target = runtime_get(name, packagename, dir)
	if os.path.exists(target):
		return open(target, 'r' if text else 'rb') if opened and not dir else target
	return None

def remove_runtime(name = None, dir = False, packagename = None):
	assert initialized
	if dir:
		shutil.rmtree(read_runtime(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_runtime(name, False, False, False, packagename))
# }}}

# Temp files. {{{
class TempFile(object):
	def __init__(self, f, name):
		# Avoid calling file.__setattr__.
		object.__setattr__(self, '_file', f)
		object.__setattr__(self, 'filename', name)
	def remove(self):
		assert initialized
		self.close()
		os.unlink(self.filename)
		tempfiles.remove(self.filename)
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
	assert initialized
	if dir:
		ret = tempfile.mkdtemp(prefix = (packagename or pname) + '-')
		tempfiles.append(ret)
	else:
		f = tempfile.mkstemp(text = text, prefix = (packagename or pname) + '-')
		tempfiles.append(f[1])
		ret = TempFile(os.fdopen(f[0], 'w+' if text else 'w+b'), f[1])
	return ret

def remove_temp(name):
	assert initialized
	assert name in tempfiles
	tempfiles.remove(name)
	shutil.rmtree(name, ignore_errors = False)
# }}}

# Data files. {{{
XDG_DATA_HOME = os.getenv('XDG_DATA_HOME', os.path.join(HOME, '.local', 'share'))
XDG_DATA_DIRS = os.getenv('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')
def write_data(name = None, text = True, dir = False, opened = True, packagename = None):
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
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	else:
		filename = os.path.join(packagename or pname, name)
	seen = set()
	target = []
	if not is_system:
		t = os.path.join(XDG_DATA_HOME, filename)
		if t not in seen and os.path.exists(t):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(t)
			target.append(r)
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = packagename or pname + os.extsep + 'dat'
	else:
		filename = name
	dirs = ['/var/local/lib', '/var/lib', '/usr/local/lib', '/usr/lib', '/usr/local/share', '/usr/share']
	if is_game:
		dirs = ['/var/local/games', '/var/games', '/usr/local/lib/games', '/usr/lib/games', '/usr/local/share/games', '/usr/share/games'] + dirs
	if packagename and packagename != pname:
		dirs = [os.path.join(x, pname, packagename) for x in dirs]
	else:
		dirs = [os.path.join(x, pname) for x in dirs]
	if not is_system:
		dirs = [os.path.join(x, packagename or pname) for x in XDG_DATA_DIRS] + dirs + [os.path.curdir]
	for d in dirs:
		t = os.path.join(d, filename)
		if t not in seen and os.path.exists(t):
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
	assert initialized
	if dir:
		shutil.rmtree(read_data(name, False, True, False, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_data(name, False, False, False, False, packagename))
# }}}

# Cache files. {{{
XDG_CACHE_HOME = os.getenv('XDG_CACHE_HOME', os.path.join(HOME, '.cache'))
def write_cache(name = None, text = True, dir = False, opened = True, packagename = None):
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
	assert initialized
	if dir:
		shutil.rmtree(read_cache(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_cache(name, False, False, False, packagename))
# }}}

# Log files. {{{
def write_log(name = None, packagename = None):
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

def remove_sppol(name = None, dir = False, packagename = None):
	assert initialized
	if name is None:
		if dir:
			filename = packagename or pname
		else:
			filename = (packagename or pname) + os.extsep + 'dat'
	target = os.path.join('/var/spool' if is_system else os.path.join(XDG_CACHE_HOME, 'spool'), filename)
	if dir:
		shutil.rmtree(read_spool(name, False, True, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_spool(name, False, False, False, packagename))
# }}}

# Locks. {{{
def lock(name = None, info = '', packagename = None):
	assert initialized
	# TODO

def unlock(name = None, packagename = None):
	assert initialized
	# TODO
# }}}
