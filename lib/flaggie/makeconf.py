#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, os.path, string

from flaggie.packagefile import PackageFileSet

class MakeConfVariable(object):
	def __init__(self, key, makeconf):
		self._key = key
		self._makeconf = makeconf

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
				return self.s

			def toString(self):
				return self.s

			def __repr__(self):
				return '%s(%s)' % (self.__class__.__name__, self.toString())

		class Whitespace(Token):
			def hasNL(self):
				return '\n' in self.s

		class UnquotedWord(Token):
			pass

		class VariableRef(UnquotedWord):
			def toString(self):
				return '$%s' % self.s

		class QuotedString(Token):
			def toString(self):
				raise NotImplementedError('QuotedString.toString() needs to be overriden')

		class SingleQuotedString(QuotedString):
			def toString(self):
				return "'%s'" % self.s

		class DoubleQuotedString(QuotedString):
			lquo = True
			rquo = True

			def toString(self):
				out = ''
				if self.lquo:
					out += '"'
				out += self.s
				if self.rquo:
					out += '"'

				return out

		class DoubleQuotedVariableRef(VariableRef, DoubleQuotedString):
			pass

		class DoubleQuotedBracedVariableRef(DoubleQuotedVariableRef):
			def toString(self):
				return '${%s}' % self.s

		def __init__(self, path):
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
							token = newtoken(self.SingleQuotedString, token)
						elif c == '"':
							token = newtoken(self.DoubleQuotedString, token)
						elif c == '$':
							token = newtoken(self.VariableRef, token)
						else:
							token = newtoken(self.UnquotedWord, token)
							token += c
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
							if n == '{':
								token.rquo = False
								token = newtoken(self.DoubleQuotedBracedVariableRef)
							elif n in string.whitespace:
								token += c + n
							else:
								token.rquo = False
								token = newtoken(self.DoubleQuotedVariableRef)
								token += n
					else:
						token += c

			f.close()

	def __init__(self, path, dbapi):
		mf = self.MakeConfFile(path)
		self.files = {path: mf}

		self.variables = {
			'use': MakeConfVariable('USE', mf),
			'kw': MakeConfVariable('ACCEPT_KEYWORDS', mf),
			'lic': MakeConfVariable('ACCEPT_LICENSE', mf)
		}
		
		self.parse(mf)

	def parse(self, mf):
		cleanline = True

		ti = iter(mf)
		for t in ti:
			if isinstance(t, self.MakeConfFile.Whitespace):
				if t.hasNL():
					cleanline = True
			elif not cleanline:
				continue
			elif t == 'source':
				try:
					nt = next(ti)
					if not isinstance(nt, self.MakeConfFile.Whitespace):
						cleanline = False
					elif not nt.hasNL():
						fn = ''
						nt = next(ti)
						try:
							while not isinstance(nt, self.MakeConfFile.Whitespace):
								fn += nt.data
								nt = next(ti)
						except StopIteration:
							pass
						else:
							if nt.hasNL():
								cleanline = True

						if fn not in self.files:
							self.files[fn] = self.MakeConfFile(fn)
						self.parse(self.files[fn])
				except StopIteration:
					break
			elif t == 'export':
				continue
			else:
				# XXX: we get variables here
				cleanline = False

	def write(self):
		for f in self.files.values():
			f.write()
