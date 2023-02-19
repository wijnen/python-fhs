#!/usr/bin/python3

import sys
import os
import fhs

# config and commandline.

# def remove_config(name = None, dir = False, packagename = None): # {{{

fhs.option('test', 'test option', default = 'try this')
fhs.option('go', 'other test option', multiple = True)
fhs.option('num', 'integer test option', default = 28)
fhs.option('verbose', 'yet another test option', short = 'v', argtype = bool)

fhs.module_info('mod', 'test module', '0.1', 'Bas Wijnen <wijnen@debian.org>')
fhs.module_option('mod', 'test', 'module test option', default = 1.5)

config = fhs.init(help = 'script for testing fhs module', version = '0.1', contact = 'Bas Wijnen <wijnen@debian.org>')
config2 = fhs.get_config()

for k in config:
	if k not in config2:
		print('key %s only in config.' % k, file = sys.stderr)
		continue
	if config[k] != config2[k]:
		print('values for key %s are not equal: %s != %s' % (k, config[k], config2[k]), file = sys.stderr)
for k in config2:
	if k not in config:
		print('key %s only in config2.' % k, file = sys.stderr)

for k in ('test', 'go', 'num', 'verbose'):
	print('value of %s is %s' % (k, repr(config[k])))

modconfig = fhs.module_get_config('mod')
print('value of mod-test is %s' % repr(modconfig['test']))

# runtime

filename = 'runtimetest'
test = 'Runtime test'
with fhs.write_runtime(filename) as f:
	f.write(test)

with fhs.read_runtime(filename) as f:
	if f.read() != test:
		print('runtime test failed', file = sys.stderr)

fn = fhs.read_runtime(filename, opened = False)
if fn is None:
	print('runtime file does not exist', file = sys.stderr)
fhs.remove_runtime(fn)
fn = fhs.read_runtime(filename, opened = False)
if fn is not None:
	print('runtime file is not removed', file = sys.stderr)

# temp

with fhs.write_temp() as f:
	test = 'Temp test'
	filename = f.filename
	f.write(test)
	f.seek(0)
	if f.read() != test:
		print('Temp file cannot be read back correctly.', file = sys.stderr)

d = fhs.write_temp(dir = True)
with open(os.path.join(d, 'temptest'), 'w') as f:
	f.write(test)
if not os.path.isdir(d):
	print('temp dir is not a directory or does not exist', file = sys.stderr)
fhs.remove_temp(d)
if os.path.isdir(d):
	print('temp dir is not removed', file = sys.stderr)

# data

filename = 'datatest'
test = 'Data test'
with fhs.write_data(filename) as f:
	f.write(test)

with fhs.read_data(filename) as f:
	if f.read() != test:
		print('data test failed', file = sys.stderr)

fn = fhs.read_data(filename, opened = False)
if fn is None:
	print('data file does not exist', file = sys.stderr)
fhs.remove_data(fn)
fn = fhs.read_data(filename, opened = False)
if fn is not None:
	print('data file is not removed', file = sys.stderr)

f = fhs.read_data('test-data.txt', packagename = 'fhs-test')
with fhs.read_data('test-data.txt', packagename = 'fhs-test') as f:
	print('file contents: %s' % f.read())

# cache

filename = 'cachetest'
test = 'Cache test'
with fhs.write_cache(filename) as f:
	f.write(test)

with fhs.read_cache(filename) as f:
	if f.read() != test:
		print('cache test failed', file = sys.stderr)

fn = fhs.read_cache(filename, opened = False)
if fn is None:
	print('cache file does not exist', file = sys.stderr)
fhs.remove_cache(fn)
fn = fhs.read_cache(filename, opened = False)
if fn is not None:
	print('cache file is not removed', file = sys.stderr)

# log
# Log files are only supported in /var/log, which is not writable for this test.
#def write_log(name = None, packagename = None):

# spool

filename = 'spooltest'
test = 'Spool test'
with fhs.write_spool(filename) as f:
	f.write(test)

with fhs.read_spool(filename) as f:
	if f.read() != test:
		print('spool test failed', file = sys.stderr)

fn = fhs.read_spool(filename, opened = False)
if fn is None:
	print('spool file does not exist', file = sys.stderr)
fhs.remove_spool(fn)
fn = fhs.read_spool(filename, opened = False)
if fn is not None:
	print('spool file is not removed', file = sys.stderr)

# lock
# Lock files are currently not implemented.
#def lock(name = None, info = '', packagename = None):
#def unlock(name = None, packagename = None):
