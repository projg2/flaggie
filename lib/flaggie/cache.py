#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import os, os.path

from portage.dep import use_reduce

class Caches(object):
	class DBAPICache(object):
		aux_key = None

		def __init__(self, dbapi):
			if not self.aux_key:
				raise AssertionError('DBAPICache.aux_key needs to be overriden.')
			self.dbapi = dbapi
			self.cache = {}

		@property
		def glob(self):
			raise AssertionError('DBAPICache.glob() needs to be overriden.')

		def _aux_parse(self, arg):
			return arg.split()

		def __getitem__(self, k):
			if k not in self.cache:
				flags = set()
				# get widest match possible to make sure we do not complain without a reason
				for p in self.dbapi.xmatch('match-all', k):
					flags.update(self._aux_parse(self.dbapi.aux_get(p, \
							(self.aux_key,))[0]))
				self.cache[k] = flags
			return self.cache[k]

	class FlagCache(DBAPICache):
		aux_key = 'IUSE'

		@property
		def glob(self):
			if None not in self.cache:
				flags = set()
				for r in self.dbapi.porttrees:
					try:
						f = open(os.path.join(r, 'profiles', 'use.desc'), 'r')
					except IOError:
						pass
					else:
						for l in f:
							ll = l.split(' - ', 1)
							if len(ll) > 1:
								flags.add(ll[0])
						f.close()
				self.cache[None] = flags

			return self.cache[None]

		def _aux_parse(self, arg):
			return [x.lstrip('+-') for x in arg.split()]

	class KeywordCache(DBAPICache):
		aux_key = 'KEYWORDS'

		@property
		def glob(self):
			if None not in self.cache:
				kws = set()
				for r in self.dbapi.porttrees:
					try:
						f = open(os.path.join(r, 'profiles', 'arch.list'), 'r')
					except IOError:
						pass
					else:
						for l in f:
							if l.strip() and not l.startswith('#'):
								kws.add(l.strip())
						f.close()

				# testing keywords
				for k in kws.copy():
					kws.add('~%s' % k)
				# and the ** special keyword
				kws.add('**')
				self.cache[None] = kws

			return self.cache[None]

		def __getitem__(self, k):
			ret = Caches.DBAPICache.__getitem__(self, k)
			ret.add('**')
			return ret

	class LicenseCache(DBAPICache):
		aux_key = 'LICENSE'

		@property
		def glob(self):
			if None not in self.cache:
				lic = set()
				for r in self.dbapi.porttrees:
					try:
						lic.update(os.listdir(os.path.join(r, 'licenses')))
					except OSError:
						pass
				self.cache[None] = lic

			return self.cache[None]

		def _aux_parse(self, arg):
			lic = use_reduce(arg, matchall = True, flat = True)
			if '||' in lic:
				lic.remove('||')
			return lic

	def __init__(self, dbapi):
		self.caches = {
			'use': self.FlagCache(dbapi),
			'kw': self.KeywordCache(dbapi),
			'lic': self.LicenseCache(dbapi)
		}

	def glob_whatis(self, arg, restrict = None):
		if not restrict:
			restrict = frozenset(self.caches)
		ret = set()
		for k in self.caches:
			if k in restrict and arg in self.caches[k].glob:
				ret.add(k)
		return ret

	def whatis(self, arg, pkg, restrict = None):
		if not restrict:
			restrict = frozenset(self.caches)
		ret = set()
		for k in self.caches:
			if k in restrict and arg in self.caches[k][pkg]:
				ret.add(k)
		return ret

	def describe(self, ns):
		if ns == 'use':
			return 'flag'
		elif ns == 'kw':
			return 'keyword'
		elif ns == 'lic':
			return 'license'
		else:
			raise AssertionError('Unexpected ns %s' % ns)
