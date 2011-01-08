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

		class QuotedString(Token):
			pass

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
					tmptoken = newtoken(self.Whitespace)
					tmptoken += l
					continue

				for c in l:
					if not isinstance(token, self.QuotedString):
						if c in string.whitespace:
							token = newtoken(self.Whitespace, token)
							token += c
						else:
							token = newtoken(self.UnquotedWord, token)
							token += c

				if not isinstance(token, self.QuotedString):
					token = None

			f.close()

	def __init__(self, path, dbapi):
		self.files = []
		self.files.append(self.MakeConfFile(path, self))

	def write(self):
		for f in self.files:
			f.write()
