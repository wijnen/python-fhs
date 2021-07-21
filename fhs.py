# This module implements fhs directory support in Python.
# vim: set fileencoding=utf-8 foldmethod=marker :

# {{{ Copyright 2013-2019 Bas Wijnen <wijnen@debian.org>
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
_options = {}
_option_order = []
_module_info = {}
_module_config = {}
_module_values = {}
_module_present = {}
_base = os.path.abspath(os.path.dirname(sys.argv[0]))
# }}}

# Configuration files. {{{
## XDG home directory.
XDG_CONFIG_HOME = os.getenv('XDG_CONFIG_HOME', os.path.join(HOME, '.config'))
## XDG config directory search path.
XDG_CONFIG_DIRS = tuple([XDG_CONFIG_HOME] + os.getenv('XDG_CONFIG_DIRS', '/etc/xdg').split(':'))

def write_config(name = None, text = True, dir = False, opened = True, packagename = None): # {{{
	'''Open a config file for writing.  The file is not truncated if it exists.
	@param name: Name of the config file.
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
			filename = (packagename or pname) + os.extsep + 'cfg'
	else:
		filename = name if is_system else os.path.join(packagename or pname, name)
	if is_system:
		if packagename and packagename != pname:
			d = os.path.join('/etc/xdg', pname, packagename)
		else:
			d = os.path.join('/etc/xdg', pname)
	else:
		d = XDG_CONFIG_HOME
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
# }}}

def read_config(name = None, text = True, dir = False, multiple = False, opened = True, packagename = None): # {{{
	'''Open a config file for reading.  The paramers should be identical to what was used to create the file with write_config().
	@param name: Name of the config file.
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
			filename = (packagename or pname) + os.extsep + 'cfg'
	else:
		filename = name
	seen = set()
	target = []
	if not is_system:
		t = os.path.join(XDG_CONFIG_HOME, filename if name is None else os.path.join(packagename or pname, name))
		if os.path.realpath(t) not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(os.path.realpath(t))
			target.append(r)
	dirs = ['/etc/xdg', '/usr/local/etc/xdg']
	if not is_system:
		for d in XDG_CONFIG_DIRS:
			dirs.insert(0, d)
	if packagename and packagename != pname:
		dirs = [os.path.join(x, pname, packagename) for x in dirs] + [os.path.join(x, packagename) for x in dirs]
	else:
		dirs = [os.path.join(x, pname) for x in dirs]
	if not is_system:
		dirs.insert(0, packagename or pname)
		dirs.insert(0, os.path.curdir)
		dirs.insert(0, _base)
	for d in dirs:
		t = os.path.join(d, filename)
		if os.path.realpath(t) not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(os.path.realpath(t))
			target.append(r)
	if multiple:
		return target
	else:
		return None
# }}}

def remove_config(name = None, dir = False, packagename = None): # {{{
	'''Remove a config file.  Use the same parameters as were used to create it with write_config().
	@param name: The file to remove.
	@param dir: If True, remove a directory.  If False (the default), remove a file.
	@param packagename: Override the packagename.
	@return None.
	'''
	assert initialized
	if dir:
		shutil.rmtree(read_config(name, False, True, False, False, packagename), ignore_errors = False)
	else:
		os.unlink(read_config(name, False, False, False, False, packagename))
# }}}

# Config file helper functions. {{{
def _protect(data, extra = ''): # {{{
	ret = ''
	extra += '\\'
	for x in str(data):
		o = ord(x)
		if o < 32 or o >= 127 or x in extra:
			ret += '\\%x;' % o
		else:
			ret += x
	return ret
# }}}

def _unprotect(data): # {{{
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

def decode_value(value, argtype): # {{{
	'''Parse a string value into its proper type.
	This function has special handling for some types and supports returning None.
	@param value: string such as stored in the config file.
	@param argtype: type or converter function to make it the required type.
	'''
	if value == 'None':
		return None
	if argtype is str:
		if len(value) < 2 or not value.startswith("'") or not value.endswith("'"):
			raise ValueError('str value without quotes')
		return value[1:-1].replace(r"'\''", "'")
	if argtype is bool:
		if value not in ('False', 'True'):
			raise ValueError('incorrect bool value %s' % value)
		return value == 'True'
	return argtype(value)
# }}}

def encode_value(value): # {{{
	'''Encode a value into a string which can be stored in a config file.
	The type of the value is used to decide how to encode it.
	'''
	if value is None:
		return 'None'
	if isinstance(value, str):
		return "'" + value.replace("'", r"'\''") + "'"
	return str(value)
# }}}

def help_text(main, options, option_order): # {{{
	if _info['help']:
		print(_info['help'], file = sys.stderr)
	else:
		if _info['version']:
			print('this is %s version %s\n' % (pname, _info['version']), file = sys.stderr)
		else:
			print('this is %s\n' % pname, file = sys.stderr)

	print('\nSupported option arguments:', file = sys.stderr)
	for module in (False, True):
		for opt in option_order:
			option = options[opt]
			if (option['module'] is not None) != module:
				continue
			m = ' (This option can be passed multiple times)' if option['multiple'] else ''
			if option['argtype'] is bool:
				optname = '--' + opt
				if option['short'] is not None:
					optname += ', -' + option['short']
				print('\t%s\n\t\t%s%s' % (optname, option['help'], m), file = sys.stderr)
			elif option['optional']:
				optname = '--' + opt + '[=<value>]'
				if option['short'] is not None:
					optname += ', -' + option['short'] + '[<value>]'
				default = ' Default: %s' % str(option['default']) if option['default'] is not None else ''
				print('\t%s\n\t\t%s%s%s' % (optname, option['help'], default, m), file = sys.stderr)
			else:
				optname = '--' + opt + '=<value>'
				if option['short'] is not None:
					optname += ', -' + option['short'] + '<value>'
				default = ' Default: %s' % str(option['default']) if option['default'] is not None else ''
				print('\t%s\n\t\t%s%s%s' % (optname, option['help'], default, m), file = sys.stderr)

	if _info['contact'] is not None:
		print('\nPlease send feedback and bug reports to %s' % _info['contact'], file = sys.stderr)
# }}}

def version_text(): # {{{
	if _info['version']:
		print('%s version %s' % (pname, _info['version']), file = sys.stderr)
	else:
		print('%s' % pname, file = sys.stderr)
	if _info['contact']:
		print('\tPlease send feedback and bug reports to %s' % _info['contact'], file = sys.stderr)

	if len(_module_info) > 0:
		print('\nUsing modules:', file = sys.stderr)
		for mod in _module_info:
			print('\t%s version %s\n\t\t%s' % (mod, _module_info[mod]['version'], _module_info[mod]['desc']), file = sys.stderr)
			if _module_info[mod]['contact'] is not None:
				print('\t\tPlease send feedback and bug reports for %s to %s' % (mod, _module_info[mod]['contact']), file = sys.stderr)
# }}}

def load_config(filename, values = None, present = None, options = None): # {{{
	if present is None:
		present = {}
	if values is None:
		new_values = True
		values = {}
	else:
		new_values = False
	config = read_config(filename + os.extsep + 'ini')
	if config is None:
		return {}
	for cfg in config:
		if cfg.strip() == '' or cfg.strip().startswith('#'):
			continue
		if '=' not in cfg:
			print('invalid line in config file %s: %s' % (filename, cfg), file = sys.stderr)
		key, value = cfg.split('=', 1)
		key = _unprotect(key)
		if not new_values and key not in values:
			print('invalid key %s in config file' % key, file = sys.stderr)
			continue
		if key in present and present[key]:
			continue
		try:
			if options is not None and options[key]['multiple']:
				values[key] = [decode_value(_unprotect(v), options[key]['argtype']) for v in value.split(',')]
			else:
				values[key] = _unprotect(value) if options is None else decode_value(_unprotect(value), options[key]['argtype'])
		except ValueError:
			print('Warning: error loading value for %s; ignoring' % key, file = sys.stderr)
			continue
		if present is not None:
			present[key] = True
	return values
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
		filename = 'commandline' + os.extsep + 'ini'
	else:
		filename = name + os.extsep + 'ini'
	keys = list(config.keys())
	keys.sort()
	with write_config(filename) as f:
		for key in keys:
			if isinstance(config[key], list):
				value = ','.join(_protect(encode_value(x), ',') for x in config[key])
			else:
				value = _protect(encode_value(config[key]))
			f.write('%s=%s\n' % (_protect(key, '='), value))
# }}}
# }}}

# Commandline argument handling. {{{
def option(name, help, short = None, multiple = False, optional = False, default = None, noarg = None, argtype = None, module = None, options = None, option_order = None): # {{{
	'''Register commandline argument.
	@param name: Name of the option argument. Should not include the "--" prefix.
	@param help: Help text when displaying the --help output.
	@param multiple: If True, this option may be specified multiple times
		and the value will be a list of the arguments.
	@param optional: If True, this option's argument may be omitted.
	@param default: Default value of this argument. This is used if the
		option is not passed and multiple is False.
	@param noarg: Default value when option is passed without argument.
		This is ignored unless optional is True.
	@param argtype: Type of the argument. If this is None and a default is
		given, type(default) is used. If default is None, str is used.
		If argtype is bool, no argument is allowed and default, noarg
		default to False, True.
		This type is called to construct the value. It can
		also be used as a callback.
	'''
	if options is None:
		assert not initialized
		options = _options
	if option_order is None:
		option_order = _option_order
	if name in options:
		raise ValueError('duplicate registration of argument name %s' % name)
	if not isinstance(name, str) or len(name) == 0 or name.startswith('-'):
		raise ValueError('argument must not start with "-": %s' % name)
	if short is not None:
		if any(options[x]['short'] == short for x in options):
			raise ValueError('duplicate short option %s defined' % short)
		if len(short) != 1:
			raise ValueError('length of short option %s for %s must be 1' % (short, name))
		if short == '-':
			raise ValueError('short option for %s cannot be "-"' % name)
	if argtype is None:
		if default is not None:
			argtype = type(default)
		else:
			argtype = str
	if argtype is bool:
		if default is None and noarg is None:
			default, noarg = False, True
	if optional:
		if argtype is bool:
			if not isinstance(noarg, bool):
				raise ValueError('noarg value for %s must be of type bool if argtype is bool' % name)
		else:
			try:
				# Testing suggests that this works for floats, but can rounding errors cause a false positive here?
				if decode_value(encode_value(noarg), argtype) != noarg:
					raise ValueError('noarg value %s for %s changes when saving to config file' % (str(noarg), name))
			except:
				raise ValueError('noarg value %s for %s cannot be restored from config file' % (str(noarg), name))
	options[name] = {'help': help, 'short': short, 'multiple': multiple, 'optional': optional, 'default': default, 'noarg': noarg, 'argtype': argtype, 'module': module}
	option_order.append(name)
	return options[name]
# }}}

def parse_args(argv = None, options = None, extra = False): # {{{
	if argv is None:
		argv = sys.argv
	if options is None:
		options = _options
	shorts = {options[name]['short']: name for name in options} 
	values = {name: [] if options[name]['multiple'] else options[name]['default'] for name in options}
	present = {name: False for name in options}
	pos = 1
	while pos < len(argv):
		current = argv[pos]
		nextarg = argv[pos + 1] if pos + 1 < len(argv) else None
		if current == '--':
			argv.pop(pos)
			break
		if len(current) < 2 or not current.startswith('-'):
			pos += 1
			continue
		if current.startswith('--'):
			# This is a long option.
			if '=' in current:
				optname, arg = current.split('=', 1)
			else:
				optname, arg = current, None
			optname = optname[2:]
			if optname not in options:
				print('Warning: ignoring unrecognized option %s' % optname)
				argv.pop(pos)
				continue
			opt = options[optname]
			argtype = opt['argtype']
			if argtype is bool:
				# This option takes no argument.
				value = opt['noarg']
			elif opt['optional']:
				# This option takes an optional argument.
				if arg is not None:
					value = opt['argtype'](arg)
				else:
					value = opt['noarg']
			else:
				# This option requires an argument.
				if arg is not None:
					value = opt['argtype'](arg)
				else:
					argv.pop(pos)
					if pos >= len(argv):
						print('Warning: option %s requires an argument' % optname, file = sys.stderr)
						continue
					value = opt['argtype'](argv[pos])
			if opt['multiple']:
				values[optname].append(value)
			else:
				if present[optname]:
					print('Warning: option %s must only be passed once' % optname, file = sys.stderr)
				values[optname] = value
			present[optname] = True
		else:
			# This is a short options argument.
			optpos = 1
			while optpos < len(current):
				o = current[optpos]
				optpos += 1
				if o not in shorts:
					print('Warning: short option %s is not recognized' % o, file = sys.stderr)
					continue
				optname = shorts[o]
				opt = options[optname]
				argtype = opt['argtype']
				if argtype is bool:
					# This option takes no argument.
					value = opt['noarg']
				elif opt['optional']:
					# This option takes an optional argument.
					if optpos < len(current):
						value = opt['argtype'](current[optpos:])
					else:
						value = opt['noarg']
					optpos = len(current)
				else:
					# This option requires an argument.
					if optpos < len(current):
						value = opt['argtype'](current[optpos:])
					else:
						argv.pop(pos)
						if pos >= len(argv):
							print('Warning: option %s (%s) requires an argument' % (o, optname), file = sys.stderr)
							continue
						value = opt['argtype'](argv[pos])
					optpos = len(current)
				if opt['multiple']:
					values[optname].append(value)
				else:
					if present[optname]:
						print('Warning: option %s (%s) must only be passed once' % (o, optname), file = sys.stderr)
					values[optname] = value
				present[optname] = True
		argv.pop(pos)
	if extra:
		return values, present
	else:
		return values
# }}}

def init(config = None, help = None, version = None, contact = None, packagename = None, system = None, game = False):	# {{{
	'''Initialize the module.
	This function must be called before any other in this module (except
	module_init(), which must be called before this function).
	Configuration is read from the commandline, and from the configuration
	files named <packagename>.ini in any of the configuration directories,
	or specified with --configfile.  A configuration file must contain
	name=value pairs.  The configuration that is used can be saved using
	--saveconfig, which can optionally have the filename to save to as a
	parameter.
	@param config: Configuration dict. Deprecated. Keep set to None.
	@param packagename: The name of the program.  This is used as a default
		for all other functions.  It has a default of the basename of
		the program.
	@param system: If True, system paths will be used for writing and user
		paths will be ignored for reading.
	@param game: If True, game system directories will be used (/usr/games,
		/usr/share/games, etc.) instead of regular system directories.
	@return Configuration from commandline and config file.
		This is a dict with the same keys as were previously passed
		through calls to option(), with the values that were specified
		as their values.  
	'''
	global initialized
	assert not initialized
	global pname
	if packagename is not None:
		pname = packagename
	global is_system
	global is_game
	is_game = game
	if config is not None:
		print('Warning: using the config parameter for fhs.init() is DEPRECATED! Use option() instead.', file = sys.stderr)
		for key in config:
			option(key, 'no help for this option', default = config[key])
	global XDG_RUNTIME_DIR
	global _values, _present
	global _info
	_info = {'help': help, 'version': version, 'contact': contact}
	# If these default options are passed by the user, this will raise an exception.
	first_options = {}
	option_order = []
	option('help', 'Show this help text', short = None if any(_options[o]['short'] == 'h' for o in _options) else 'h', argtype = bool, options = first_options, option_order = option_order) 
	option('version', 'Show version information', short = None if any(_options[o]['short'] == 'v' for o in _options) else 'v', argtype = bool, options = first_options, option_order = option_order) 
	option('configfile', 'Use this file for loading and/or saving commandline configuration', default = 'commandline', options = first_options, option_order = option_order)
	option('saveconfig', 'Save active commandline configuration as default or to the named file', optional = True, default = None, noarg = '', argtype = str, options = first_options, option_order = option_order)
	if system is None:
		option('system', 'Use only system paths', argtype = bool, options = first_options, option_order = option_order)
	else:
		is_system = system
	options = first_options.copy()
	options.update(_options)
	option_order += _option_order
	try:
		_values, _present = parse_args(sys.argv, options, extra = True)
	except ValueError as err:
		# Error parsing options.
		print('Error parsing arguments: %s' % str(err))
		help_text(help, options, option_order)
		sys.exit(1)
	if _values['help']:
		help_text(help, options, option_order)
		sys.exit(1)
	_values.pop('help')
	if _values['version']:
		version_text()
		sys.exit(1)
	_values.pop('version')
	configfile = _values.pop('configfile')
	saveconfig = _values.pop('saveconfig')
	if system is None:
		is_system = _values['system']

	initialized = True
	if saveconfig == '':
		saveconfig = configfile
	load_config(configfile, _values, _present, options)
	if saveconfig is not None:
		save_config({key: _values[key] for key in _values if _present[key]}, saveconfig, packagename)
	# Split out the module options into their own object.
	for module in _module_config:
		_module_values[module] = {key: _values.pop(module + '-' + key) for key in _module_config[module]}
		_module_present[module] = {key: _present.pop(module + '-' + key) for key in _module_config[module]}
	# system may have been updated. Record the new value. Do this after
	# save_config, because it should save in the location where read_config
	# searches for it.
	if system is None:
		is_system = _values.pop('system')
	@atexit.register
	def clean_temps():
		for f in _tempfiles:
			try:
				os.unlink(f)
			except:
				shutil.rmtree(f, ignore_errors = True)
	if XDG_RUNTIME_DIR is None:
		XDG_RUNTIME_DIR = write_temp(dir = True)
	return _values
# }}}

def get_config(extra = False): # {{{
	'''Retrieve commandline configuration.
	Return the stored result of parsing the commandline and reading the
	config file.

	If init() was not yet called, it is called implicitly with default
	settings.

	@param extra: if True, return dict of which values were not using their defaults as well.
	@return configuration dict, and possibly present dict, with the same
		format as the return value of init().
	'''
	if not initialized:
		print('Warning: init() should be called before get_config() to set program information', file = sys.stderr)
		init()
	if extra:
		return _values, _present;
	else:
		return _values;
# }}}
# }}}

# Module commandline argument handling. {{{
def module_info(modulename, desc, version, contact): # {{{
	'''Register information about a module.
	This should be called by modules that use python-fhs to get their own commandline arguments.
	@param modulename: The name of the calling module.
	@param desc: Module description in --version output.
	@param version: Version number in --version output.
	@param contact: Contact information in --version output.
	'''
	assert not initialized
	if modulename in _module_info:
		print('Warning: duplicate registration of information for module %s' % modulename, file = sys.stderr)
		return
	_module_info[modulename] = {'desc': desc, 'version': version, 'contact': contact}
	_module_config[modulename] = set()
# }}}

def module_option(modulename, name, help, short = None, multiple = False, optional = False, default = None, noarg = None, argtype = None, options = None, option_order = None): # {{{
	'''Register a commandline option for a module.
	This is identical to option(), except it adds the option with the module's name as a prefix and can be retrieved through module_get_config().
	@param modulename: Name of the module.
	Other options and return value are identical to those of option().
	'''
	assert not initialized
	assert modulename in _module_info
	_module_config[modulename].add(name)
	return option(modulename + '-' + name, help, short, multiple, optional, default, noarg, argtype, modulename, options, option_order)
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
	print('Warning: module %s uses module_init() which is DEPRECATED! It should use module_option() instead.' % modulename, file = sys.stderr)
	assert not initialized
	module_info(modulename, 'no information about this module available', 'unknown', None)
	for key in config:
		module_option(modulename, key, 'no help for this module option', default = config[key])
# }}}

def module_get_config(modulename, extra = False): # {{{
	'''Retrieve module configuration.
	A module can add configuration options by calling module_option() before
	the program calls init().  This function is used to retrieve the
	configuration.  If init() has not been called yet, it will be called
	implicitly with default settings.
	@param modulename: Name of the module.  Must be identical to the name
		that was passed to module_option().
	@return configuration dict, with the same format as the return value of
		init().  This dict does not include the automatic module prefix
		of the module options.
	'''
	if not initialized:
		init()
	if extra:
		return _module_values[modulename], _module_present[modulename];
	else:
		return _module_values[modulename];
# }}}
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
class _TempFile:
	def __init__(self, f, name):
		# Avoid calling file.__setattr__.
		super().__setattr__('_file', f)
		super().__setattr__('filename', name)
	def remove(self):
		assert initialized
		assert self.filename is not None
		self.close()
		os.unlink(self.filename)
		_tempfiles.remove(self.filename)
		super().__setattr__('_file', None)
		super().__setattr__('filename', None)
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
		if os.path.realpath(t) not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(os.path.realpath(t))
			target.append(r)
	dirs = ['/var/local/lib', '/var/lib', '/usr/local/lib', '/usr/lib', '/usr/local/share', '/usr/share']
	if is_game:
		dirs = ['/var/local/games', '/var/games', '/usr/local/lib/games', '/usr/lib/games', '/usr/local/share/games', '/usr/share/games'] + dirs
	if not is_system:
		for d in XDG_DATA_DIRS:
			dirs.insert(0, d)
	if packagename and packagename != pname:
		dirs = [os.path.join(x, pname, packagename) for x in dirs] + [os.path.join(x, packagename) for x in dirs]
	else:
		dirs = [os.path.join(x, pname) for x in dirs]
	if not is_system:
		dirs.insert(0, packagename or pname)
		dirs.insert(0, os.path.curdir)
		dirs.insert(0, _base)
	for d in dirs:
		t = os.path.join(d, filename)
		if os.path.realpath(t) not in seen and os.path.exists(t) and (dir if os.path.isdir(t) else not dir):
			r = t if dir or not opened else open(t, 'r' if text else 'rb')
			if not multiple:
				return r
			seen.add(os.path.realpath(t))
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
