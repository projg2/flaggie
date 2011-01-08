#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, os.path, string

from flaggie.packagefile import PackageFileSet

class MakeConf(object):
	class MakeConfFile(PackageFileSet.PackageFile):
		class Token(object):
			def __init__(self, s = ''):
				self.modified = False
				self.s = s

			def __len__(self):
				return len(self.s)

			def __iadd__(self, s):
				self.s += s
				return self

			def toString(self):
				return self.s

		class Whitespace(Token):
			pass

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

		def __init__(self, path, parent):
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
		self.files = []
		self.files.append(self.MakeConfFile(path, self))

	def write(self):
		for f in self.files:
			f.write()
