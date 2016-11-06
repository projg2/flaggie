#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 2-clause BSD license.

from portage.exception import AmbiguousPackageName, InvalidAtom

from .action import Action

class BaseCleanupAction(Action.BaseAction):
	def __init__(self, dbapi):
		self._dbapi = dbapi

	def clarify(self, pkgs, cache):
		if pkgs:
			raise AssertionError('pkgs not empty in cleanup action')
		self._cache = cache

	def __call__(self, pkgs, pfiles):
		if pkgs:
			raise AssertionError('pkgs not empty in cleanup action')
		for f in pfiles:
			self._perform(f)

	def __lt__(self, other):
		try:
			idx = [cleanupact_order.index(x.__class__) for x in (self, other)]
		except ValueError: # cleanup actions always go to the end
			return False
		return idx[0] < idx[1]

class DropIneffective(BaseCleanupAction):
	def _perform(self, f):
		cache = {}

		for pe in list(f):
			if pe.package not in cache:
				cache[pe.package] = set()
			for flag in pe:
				if flag.name not in cache[pe.package]:
					cache[pe.package].add(flag.name)
				else:
					pe.remove(flag)

class DropUnmatchedFlags(BaseCleanupAction):
	def __call__(self, pkgs, pfiles):
		if pkgs:
			raise AssertionError('pkgs not empty in cleanup action')
		
		dbcache = {}

		for k, f in pfiles.files.items():
			cache = self._cache[k]
			for pe in f:
				if pe.package not in dbcache:
					try:
						dbcache[pe.package] = bool(self._dbapi.xmatch('match-all', pe.package))
					except (InvalidAtom, AmbiguousPackageName):
						dbcache[pe.package] = False

				if dbcache[pe.package]:
					flags = cache[pe.package]
					for flag in set([x.name for x in pe]):
						if k == 'kw' and (flag == '*' or flag == '**' or flag == '~*'):
							pass
						elif flag not in flags:
							del pe[flag]

class DropUnmatchedPkgs(BaseCleanupAction):
	def _perform(self, f):
		cache = {}

		class AllMatcher(object):
			def __eq__(self, other):
				return True

		am = AllMatcher()

		for pe in f:
			if pe.package not in cache:
				try:
					cache[pe.package] = bool(self._dbapi.xmatch('match-all', pe.package))
				except (InvalidAtom, AmbiguousPackageName):
					cache[pe.package] = False

			# implicitly remove the package through removing all of its flags
			if not cache[pe.package]:
				del pe[am]

class SortEntries(BaseCleanupAction):
	def _perform(self, f):
		f.sort()

class SortFlags(BaseCleanupAction):
	def _perform(self, f):
		for pe in f:
			pe.sort()

class MigrateFiles(BaseCleanupAction):
	def _perform(self, f):
		f.migrate()

cleanupact_order = (MigrateFiles, DropUnmatchedPkgs, DropUnmatchedFlags, \
		DropIneffective, SortEntries, SortFlags)
