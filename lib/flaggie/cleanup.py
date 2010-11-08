#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

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

class SortEntries(BaseCleanupAction):
	def _perform(self, f):
		f.sort()

class SortFlags(BaseCleanupAction):
	def _perform(self, f):
		for pe in f:
			pe.sort()
