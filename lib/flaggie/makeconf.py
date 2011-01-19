#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, os.path, re, string

from flaggie.packagefile import PackageFileSet

wsregex = re.compile('(?u)(\s+)')

class MakeConfVariable(object):
	class FlattenedToken(PackageFileSet.PackageFile.PackageEntry):
		class MakeConfFlag(PackageFileSet.PackageFile.PackageEntry.PackageFlag):
			def __init__(self, s, lta = []):
				PackageFileSet.PackageFile.PackageEntry.PackageFlag.__init__( \
					self, s + ''.join([f.toString() for t, f in lta]))

				self._origs = s
				self._partialflags = lta
				self._removed = False

			@property
			def modified(self):
				return self._origs is None

			@modified.setter
			def modified(self, val):
				if val:
					self._origs = None
					for t, pf in self._partialflags:
						t.modified = True
						pf.modified = True
				else:
					raise NotImplementedError('Disable modified for MakeConfFlag is not supported.')

			@property
			def removed(self):
				return self._removed

			@removed.setter
			def removed(self, val):
				# This also cleans up partial flags.
				self.modified = True
				self._removed = val

			@property
			def modifier(self):
				return self._modifier

			@modifier.setter
			def modifier(self, val):
				self._modifier = val
				self.modified = True

			def toString(self, raw = False):
				if self.removed:
					return ''
				elif not self.modified:
					return self._origs
				else:
					return PackageFileSet.PackageFile.PackageEntry.PackageFlag.toString(self)

		class ExpandedFlag(MakeConfFlag):
			def __init__(self, s, use_expanded_from):
				self.prefix = '%s_' % use_expanded_from
				MakeConfVariable.FlattenedToken.MakeConfFlag.__init__(self, s)

			def toString(self, raw = False):
				ret = MakeConfVariable.FlattenedToken.MakeConfFlag.toString(self)
				if raw:
					if ret.startswith('-'):
						ret = ''
					else:
						ret = ret.replace(self.prefix, '', 1)
				return ret

		class Whitespace(object):
			def __init__(self, s):
				self.s = s

			def toString(self, raw = False):
				return self.s

			@property
			def modified(self):
				return False

		class PartialFlag(Whitespace):
			@property
			def modified(self):
				return not self.s

			@modified.setter
			def modified(self, val):
				if val:
					self.s = ''
				else:
					raise NotImplementedError('Disabling modified for PartialFlag is not supported.')

		def __init__(self, token):
			self.use_expanded = False
			self._token = token
			token.flags = []

		@property
		def data(self):
			return self._token.data

		@property
		def modified(self):
			return self._token.modified

		@modified.setter
		def modified(self, val):
			self._token.modified = val

		@property
		def flags(self):
			return self._token.flags

		def toString(self):
			return self._token.toString()

		def append(self, flag):
			nonempty = bool(self.flags)

			if nonempty and isinstance(self._token, MakeConf.MakeConfFile.UnquotedWord):
				self._token.quoted = True

			if not isinstance(flag, self.MakeConfFlag):
				if self.use_expanded:
					flag = self.ExpandedFlag(flag, self.use_expanded)
				else:
					flag = self.MakeConfFlag(flag)
				if nonempty:
					self.flags.append(self.Whitespace(' '))

			self.flags.append(flag)
			self.modified = True
			return flag

		def __iter__(self):
			""" Iterate over all flags in the entry. """
			for f in reversed(self.flags):
				if isinstance(f, self.MakeConfFlag):
					yield f

		def __delitem__(self, flag):
			""" Remove all occurences of a flag. """
			for f in self.flags:
				if isinstance(f, self.MakeConfFlag) and flag == f.name:
					f.removed = True
					self.modified = True

	def __init__(self, key, tokens):
		def flattentokens(l):
			out = []
			for t in l:
				if isinstance(t, MakeConfVariable):
					out.extend(flattentokens(t._tokens))
				else:
					out.append(self.FlattenedToken(t))
			return out

		self._key = key
		self._tokens = tokens
		self._flattokens = flattentokens(tokens)
		self._parsed = False
		self._useexpanded = {}

	def parseflags(self):
		if self._parsed:
			return
		ftokens = self._flattokens

		fti = iter(ftokens)
		for t in fti:
			nt = None
			while True:
				if nt:
					sl = nsl
					nt = None
				else:
					sl = wsregex.split(t.data)
					# 'flag1 flag2' -> flag1, ' ', flag2
					# ' flag1 flag2' -> '', ' ', flag1, ' ', flag2
					# 'flag1 flag2 ' -> flag1, ' ', flag2, ' ', ''
					# ' ' -> '', ' ', ''
					# '' -> ''

				lta = []
				if sl[-1]:
					while True:
						try:
							nt = next(fti)
						except StopIteration:
							nt = None
							break
						else:
							nsl = wsregex.split(nt.data)
							if len(nsl) == 1 and not nsl[0]:
								pass
							elif not nsl[0]: # the whitespace we were hoping for
								break
							else:
								pf = self.FlattenedToken.PartialFlag(nsl[0])
								nt.flags.append(pf)
								lta.append((nt, pf))
								if len(nsl) != 1:
									nsl[0] = ''
									break

				lasti = len(sl) - 1
				for i, e in enumerate(sl):
					if i%2 == 0:
						if e:
							strippedtoken = e.lstrip('+-')
							if t.use_expanded:
								assert(not lta or i != lasti)
								flagname = '%s_%s' % (t.use_expanded, e)
								self._useexpanded[t.use_expanded].remove(flagname)
								t.flags.append(self.FlattenedToken.ExpandedFlag(flagname, t.use_expanded))
							elif [x for x in self._useexpanded if strippedtoken.startswith(x)]:
								# inactive due to USE_EXPAND
								t.flags.append(self.FlattenedToken.PartialFlag(e))
							elif lta and i == lasti:
								t.flags.append(self.FlattenedToken.MakeConfFlag(e, lta))
							else:
								t.flags.append(self.FlattenedToken.MakeConfFlag(e))
					else:
						t.flags.append(self.FlattenedToken.Whitespace(e))

				if nt:
					t = nt
				else:
					break

		# Add disabled USE_EXPAND flags.
		for t in reversed(self._flattokens):
			if t.use_expanded:
				for f in self._useexpanded.pop(t.use_expanded):
					t.append('-%s' % f)
				t.modified = False

		self._parsed = True

	def add_expand(self, var, flagcache):
		if self._parsed:
			raise NotImplementedError('Appending to a parsed variable not supported')

		key = var._key.lower()
		values = [f for f in flagcache.glob if f.startswith(key)]
		self._useexpanded[key] = set(values)

		newtokens = []
		for t in var._flattokens:
			t.use_expanded = key
			newtokens.append(t)
		newtokens.append(self.FlattenedToken(MakeConf.MakeConfFile.Whitespace(' ')))
		newtokens.extend(self._flattokens)
		self._flattokens = newtokens

	def __iter__(self):
		self.parseflags()

		for t in reversed(self._flattokens):
			yield t

	def __repr__(self):
		return 'MakeConfVariable(%s, %s)' % (self._key, self._tokens)

class FakeVariable(MakeConfVariable):
	def __init__(self, key):
		MakeConfVariable.__init__(self, key,
			(MakeConf.MakeConfFile.DoubleQuotedString(''),))

class NewVariable(FakeVariable):
	def __init__(self, key):
		FakeVariable.__init__(self, key)

	@property
	def key(self):
		return self._key

class MakeConf(object):
	class NewMakeConfFile(PackageFileSet.PackageFile):
		class Token(object):
			def __init__(self, s = ''):
				self._modified = False
				self.s = s

			def __len__(self):
				return len(self.s)

			def __eq__(self, other):
				return self.s == other

			def __iadd__(self, s):
				self.s += s
				return self

			@property
			def modified(self):
				return self._modified

			@modified.setter
			def modified(self, val):
				self._modified = val

			@property
			def data(self):
				if self.modified:
					return ''.join([f.toString(True) for f in self.flags])
				else:
					return self.s

			def toString(self):
				return self.data

			def __repr__(self):
				return '%s(%s)' % (self.__class__.__name__, self.toString())

		class Whitespace(Token):
			def hasNL(self):
				return '\n' in self.data

		class UnquotedWord(Token):
			quoted = False

			def toString(self):
				if self.quoted:
					return '"%s"' % self.data
				else:
					return self.data

		class VariableRef(UnquotedWord):
			def toString(self):
				return '$%s' % self.s

			@property
			def data(self):
				ret = self.s
				if ret.startswith('{') and ret.endswith('}'):
					return ret[1:-1]
				return ret

		class QuotedString(Token):
			def toString(self):
				raise NotImplementedError('QuotedString.toString() needs to be overriden')

		class SingleQuotedString(QuotedString):
			def toString(self):
				return "'%s'" % self.data

		class DoubleQuotedString(QuotedString):
			lquo = True
			rquo = True

			def toString(self):
				out = ''
				if self.lquo:
					out += '"'
				out += self.data
				if self.rquo:
					out += '"'

				return out

		class DoubleQuotedVariableRef(VariableRef, DoubleQuotedString):
			@property
			def data(self):
				return self.s

		class DoubleQuotedBracedVariableRef(DoubleQuotedVariableRef):
			def toString(self):
				return '${%s}' % self.data

		@property
		def data(self):
			data = ''
			for l in self:
				data += l.toString()
			return data

		def __init__(self, path):
			list.__init__(self)
			self.path = path
			# not used in MakeConfFile
			self._modified = False
			self.trailing_whitespace = []

	class MakeConfFile(NewMakeConfFile):
		def __init__(self, path, basedir = None):
			MakeConf.NewMakeConfFile.__init__(self, path)

			def newtoken(kind, oldtoken = None):
				if isinstance(oldtoken, kind):
					return oldtoken

				token = kind()
				self.append(token)
				return token

			token = None
			if basedir:
				path = os.path.join(basedir, path)
			f = codecs.open(path, 'r', 'utf8')
			for l in f:
				if not isinstance(token, self.QuotedString) and l.startswith('#'):
					token = newtoken(self.Whitespace, token)
					token += l
					continue

				ci = iter(l)
				for c in ci:
					if c == '\\':
						if not isinstance(token, self.QuotedString):
							token = newtoken(self.UnquotedWord, token)
						try:
							token += c + next(ci)
						except StopIteration:
							token += c
					elif not isinstance(token, self.QuotedString):
						if c in string.whitespace:
							token = newtoken(self.Whitespace, token)
							token += c
						elif c == "'":
							token = newtoken(self.SingleQuotedString)
						elif c == '"':
							token = newtoken(self.DoubleQuotedString)
						elif c == '$':
							token = newtoken(self.VariableRef, token)
						else:
							token = newtoken(self.UnquotedWord, token)
							token += c
							if c == '=':
								token = None
					elif isinstance(token, self.SingleQuotedString) and c == "'":
						token = None
					elif isinstance(token, self.DoubleQuotedString) and c == '"':
						token = None
					elif isinstance(token, self.DoubleQuotedBracedVariableRef) and c == '}':
						token = newtoken(self.DoubleQuotedString)
						token.lquo = False
					elif isinstance(token, self.DoubleQuotedVariableRef) and c in string.whitespace:
						token = newtoken(self.DoubleQuotedString)
						token.lquo = False
						token += c
					elif c == '$':
						try:
							n = next(ci)
						except StopIteration:
							token += c
						else:
							if n in string.whitespace:
								token += c + n
							else:
								token.rquo = False
								if n == '{':
									token = newtoken(self.DoubleQuotedBracedVariableRef)
								else:
									token = newtoken(self.DoubleQuotedVariableRef)
									token += n
					else:
						token += c

			f.close()

	def __init__(self, paths, dbapi, caches = None):
		self.files = {}
		self.variables = {}
		self.newvars = []
		self.masterfile = None

		flagcache = caches['use']
		use_expand_vars = frozenset(flagcache.use_expand_vars)

		for path in paths:
			if os.path.exists(path):
				mf = self.MakeConfFile(path)
				self.files[path] = mf
				self.parse(mf, path)
				self.masterfile = mf

		if not self.masterfile:
			path = paths[0]
			mf = self.NewMakeConfFile(path)
			self.files[path] = mf
			self.masterfile = mf

		for key in use_expand_vars:
			if key in self.variables:
				self.variables['USE'].add_expand(self.variables[key],
						flagcache)

	def parse(self, mf, path):
		# 1) group tokens in lines
		lines = []
		words = []
		tokens = []
		for t in mf:
			if isinstance(t, self.MakeConfFile.Whitespace):
				if tokens:
					words.append(tokens)
					tokens = []
				if t.hasNL():
					if words:
						lines.append(words)
						words = []
			else:
				tokens.append(t)
		else:
			if tokens:
				words.append(tokens)
			if words:
				lines.append(words)

		def join(words):
			return ''.join([t.data for t in words])

		# 2) now go for it
		for l in lines:
			joined = join(l[0])
			if joined == 'source':
				fn = join(l[1])
				if fn not in self.files:
					self.files[fn] = self.MakeConfFile(fn, path)
				self.parse(self.files[fn], fn)
				continue
			elif joined == 'export':
				assignm = l[1]
			else:
				assignm = l[0]
			
			for i, t in enumerate(assignm):
				if isinstance(t, self.MakeConfFile.UnquotedWord) and t.data.endswith('='):
					key = join(assignm[:i+1])[:-1]
					val = []

					for t in assignm[i+1:]:
						if isinstance(t, self.MakeConfFile.VariableRef):
							try:
								val.append(self.variables[t.data])
							except KeyError:
								pass
						else:
							val.append(t)

					self.variables[key] = MakeConfVariable(key, val)
					break

	def __getitem__(self, k):
		if k == 'env': # env not supported as a global var
			return FakeVariable('DUMMY_%s' % k.upper())

		kmap = {
			'use': 'USE',
			'kw': 'ACCEPT_KEYWORDS',
			'lic': 'ACCEPT_LICENSE'
		}
		varname = kmap[k]

		if varname not in self.variables:
			nv = NewVariable(varname)
			self.newvars.append(nv)
			self.variables[varname] = nv

		return self.variables[varname]

	def write(self):
		for nv in self.newvars:
			for t in nv:
				if t.modified:
					nl = self.MakeConfFile.Whitespace('\n')
					out = []
					if self.masterfile:
						lt = self.masterfile[-1]
						if not isinstance(lt, self.MakeConfFile.Whitespace) or not lt.hasNL():
							out.append(nl)

					out.append(self.MakeConfFile.UnquotedWord('%s=' % nv.key))
					out.extend(list(nv))
					out.append(nl)

					self.masterfile.extend(out)
					break

		for f in self.files.values():
			f.write()
