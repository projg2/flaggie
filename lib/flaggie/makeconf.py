#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, os.path, re, string

from flaggie.packagefile import PackageFileSet

wsregex = re.compile('(?u)(\s+)')

class MakeConfVariable(PackageFileSet.PackageFile.PackageEntry):
	class MakeConfFlag(PackageFileSet.PackageFile.PackageEntry.PackageFlag):
		def __init__(self, s, lta = []):
			self._origs = s
			self._partialflags = lta
			s += ''.join([x.toString() for x in lta])
			PackageFileSet.PackageFile.PackageEntry.PackageFlag.__init__(self, s)

		def toString(self):
			return self._origs

	class Whitespace(object):
		def __init__(self, s):
			self.s = s

		def toString(self):
			return self.s

	class PartialFlag(Whitespace):
		pass

	def __init__(self, key, tokens):
		def flattentokens(l, parentvar):
			out = []
			for t in l:
				if isinstance(t, MakeConfVariable):
					out.extend(flattentokens(t._tokens, t))
				else:
					out.append((parentvar, t))
			return out

		self._key = key
		self._tokens = tokens
		self._flattokens = flattentokens(tokens, self)
		self._parsed = False

	def parseflags(self):
		if self._parsed:
			return
		ftokens = self._flattokens

		fti = iter(ftokens)
		for mv, t in fti:
			nt = None
			while True:
				if nt:
					sl = nsl
					nt = None
				else:
					t.flags = []
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
							nmv, nt = next(fti)
						except StopIteration:
							nt = None
							break
						else:
							nsl = wsregex.split(nt.data)
							nt.flags = []
							if len(nsl) == 1 and not nsl[0]:
								pass
							elif not nsl[0]: # the whitespace we were hoping for
								break
							else:
								pf = self.PartialFlag(nsl[0])
								nt.flags.append(pf)
								lta.append(pf)
								if len(nsl) != 1:
									nsl[0] = ''
									break

				lasti = len(sl) - 1
				for i, e in enumerate(sl):
					if i%2 == 0:
						if e:
							if lta and i == lasti:
								t.flags.append(self.MakeConfFlag(e, lta))
							else:
								t.flags.append(self.MakeConfFlag(e))
					else:
						t.flags.append(self.Whitespace(e))

				if nt:
					mv = nmv
					t = nt
				else:
					break

		self._parsed = True

	def __iter__(self):
		self.parseflags()

		for mv, t in reversed(self._flattokens):
			for i, f in enumerate(reversed(t.flags)):
				if isinstance(f, self.MakeConfFlag):
					yield f

	def __repr__(self):
		return 'MakeConfVariable(%s, %s)' % (self._key, self._tokens)

class FakeVariable(MakeConfVariable):
	def __init__(self):
		self._flattokens = ()
		self._parsed = True

class MakeConf(object):
	class MakeConfFile(PackageFileSet.PackageFile):
		class Token(object):
			def __init__(self, s = ''):
				self.modified = False
				self.s = s

			def __len__(self):
				return len(self.s)

			def __eq__(self, other):
				return self.s == other

			def __iadd__(self, s):
				self.s += s
				return self

			@property
			def data(self):
				if self.modified:
					return ''.join([f.toString() for f in self.flags])
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
			pass

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

		def __init__(self, path, basedir = None):
			list.__init__(self)
			self.path = path
			# not used in MakeConfFile
			self._modified = False
			self.trailing_whitespace = []

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

	def __init__(self, path, dbapi):
		mf = self.MakeConfFile(path)
		self.files = {path: mf}
		self.variables = {}

		self.parse(mf, path)

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
			return FakeVariable()

		kmap = {
			'use': 'USE',
			'kw': 'ACCEPT_KEYWORDS',
			'lic': 'ACCEPT_LICENSE'
		}
		return self.variables[kmap[k]]

	def write(self):
		for f in self.files.values():
			f.write()
