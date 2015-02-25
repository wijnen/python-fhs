#!/usr/bin/env python

import distutils.core
distutils.core.setup (
		name = 'fhs',
		py_modules = ['fhs'],
		version = '0.1',
		description = 'Use FHS and XDG basedir paths',
		author = 'Bas Wijnen',
		author_email = 'wijnen@debian.org',
		)
