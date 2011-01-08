#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import fnmatch

class ParserError(Exception):
	pass

class ParserWarning(Exception):
	pass

class Action(object):
	class BaseAction(object):
		class Pattern(object):
			def __init__(self, s):
				self.pattern = s

			def __eq__(self, s):
				return fnmatch.fnmatchcase(s, self.pattern)

			def __hash__(self):
				return hash(self.pattern)

		def __init__(self, arg, key, output = None):
			self.args = set((arg,))
			self.ns = None
			self.output = output

		def clarify(self, pkgs, cache):
			if len(self.args) > 1:
				raise AssertionError('clarify() needs to be called before actions are joined.')
			self._cache = cache
			arg = self.args.pop()

			splitarg = arg.split('::', 1)
			if len(splitarg) > 1:
				arg = splitarg[1]
				nsarg = self.Pattern(splitarg[0])
				ns = set()
				for k in cache:
					if nsarg == k:
						ns.add(k)
				if not ns:
					raise ParserError('Namespace not matched: %s' % splitarg[0])
			else:
				ns = None

			if not arg:
				arg = '?*'

			# Check whether the argument looks like a pattern but denote that
			# for keywords '**' and '*' have special meaning.
			if (ns and 'kw' not in ns) or arg not in ('**', '*'):
				for schr in ('*', '?', '['):
					if schr in arg:
						if not ns:
							ns = frozenset(('use',))
						self.ns = ns
						self.args.add(self.Pattern(arg))
						return

			warn = None
			if not pkgs:
				wis = cache.glob_whatis(arg, restrict = ns)
				if len(wis) > 1:
					raise ParserError('Ambiguous argument: %s (matches %s).' % \
							(arg, ', '.join(wis)))
				elif wis:
					ns = wis.pop()
				elif ns:
					ns = ns.pop()
					warn = '%s seems to be an incorrect global %s' % \
							(arg, cache.describe(ns))
				else:
					ns = 'use'
					warn = '%s seems to be an incorrect global flag' % arg
			else:
				for p in pkgs:
					wis = cache.whatis(arg, p, restrict = ns)
					if wis:
						gwis = wis
					elif ns:
						gwis = ns
					else:
						gwis = cache.glob_whatis(arg)

					if len(gwis) > 1:
						raise ParserError('Ambiguous argument: %s (matches %s).' % \
								(arg, ', '.join(wis)))
					elif wis:
						ns = wis.pop()
					else:
						if gwis:
							ns = gwis.pop()
							warn = '%s seems to be an incorrect %s for %s' % \
									(arg, cache.describe(ns), p)
						else:
							ns = 'use'
							warn = '%s seems to be an incorrect flag for %s' % (arg, p)

			self.ns = frozenset((ns,))
			self.args.add(arg)
			if warn:
				raise ParserWarning(warn)

		def append(self, arg):
			if isinstance(arg, self.__class__):
				self.args.update(arg.args)
			else:
				self.args.add(arg)

		def __lt__(self, other):
			try:
				idx = [Action.order.index(x.__class__) for x in (self, other)]
			except ValueError: # an external class
				return True
			return idx[0] < idx[1]

	class EffectiveEntryOp(BaseAction):
		def grab_effective_entry(self, p, arg, f, rw = False):
			entries = f[p]
			for pe in entries:
				flags = pe[arg]
				for f in flags:
					if rw:
						pe.modified = True
					return f
			else:
				if not rw:
					return None
				# No matching flag found. Try to append to the last
				# package entry if there's one. Otherwise, append
				# a new entry.
				for pe in f[p]:
					return pe.append(arg)
				else:
					return f.append(p).append(arg)

		def expand_patterns(self, args, pkg):
			out = []
			for a in args:
				for ns in self.ns:
					if isinstance(a, self.Pattern):
						for f in self._cache[ns].get_effective(pkg):
							if a == f:
								out.append((ns, f))
					else:
						out.append((ns, a))
			return out

	class enable(EffectiveEntryOp):
		def __call__(self, pkgs, pfiles, mkconf):
			for p in pkgs:
				for ns, arg in self.expand_patterns(self.args, p):
					f = self.grab_effective_entry(p, arg, pfiles[ns], rw = True)
					f.modifier = ''
			if not pkgs:
				raise NotImplementedError('Global actions are not supported yet.')

	class disable(EffectiveEntryOp):
		def __call__(self, pkgs, pfiles, mkconf):
			for p in pkgs:
				for ns, arg in self.expand_patterns(self.args, p):
					f = self.grab_effective_entry(p, arg, pfiles[ns], rw = True)
					f.modifier = '-'
			if not pkgs:
				raise NotImplementedError('Global actions are not supported yet.')

	class reset(BaseAction):
		def __call__(self, pkgs, pfiles, mkconf):
			for ns in self.ns:
				puse = pfiles[ns]
				for p in pkgs:
					for pe in puse[p]:
						for f in self.args:
							del pe[f]
				if not pkgs:
					raise NotImplementedError('Global actions are not supported yet.')

	class output(BaseAction):
		def __call__(self, pkgs, pfiles, mkconf):
			for ns in self.ns:
				puse = pfiles[ns]
				for p in pkgs:
					l = [p]
					flags = {}
					for pe in puse[p]:
						for arg in self.args:
							for f in pe[arg]:
								if f.name not in flags:
									flags[f.name] = f
					for arg in self.args:
						if arg not in flags and not isinstance(arg, self.Pattern):
							flags[arg] = None
					if not flags:
						continue
					for fn in sorted(flags):
						l.append(flags[fn].toString() if flags[fn] is not None else '?%s' % fn)

					print(' '.join(l))
				if not pkgs:
					raise NotImplementedError('Global actions are not supported yet.')

	mapping = {
		'+': enable,
		'-': disable,
		'%': reset,
		'?': output
	}
	order = (enable, disable, reset, output)

	class NotAnAction(Exception):
		pass

	def __new__(cls, *args, **kwargs):
		a = args[0]
		if a[0] in cls.mapping:
			newargs = (a[1:], a[0]) + args[1:]
			return cls.mapping[a[0]](*newargs, **kwargs)
		else:
			raise cls.NotAnAction

class ActionSet(list):
	def __init__(self, cache = None):
		list.__init__(self)
		self._cache = cache
		self.pkgs = []

	def append(self, item):
		if isinstance(item, Action.BaseAction):
			exc = None
			try:
				item.clarify(self.pkgs, self._cache)
			except ParserWarning as e:
				exc = e

			for a in self:
				if isinstance(item, a.__class__) and item.ns == a.ns:
					a.append(item)
					break
			else:
				list.append(self, item)

			if exc is not None:
				raise exc
		else:
			self.pkgs.append(item)

	def __call__(self, pfiles, mkconf):
		self.sort()
		for a in self:
			a(self.pkgs, pfiles, mkconf)
