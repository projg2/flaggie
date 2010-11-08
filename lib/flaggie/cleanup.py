#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

from portage.exception import AmbiguousPackageName, InvalidAtom

class BaseCleanupAction(object):
	def __init__(self, *args):
		if args:
			self(*args)

	def __call__(self, pfiles, dbapi):
		self._dbapi = dbapi
		for f in pfiles:
			self._perform(f)

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
