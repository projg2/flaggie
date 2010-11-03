#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, glob, sys, os.path
from optparse import OptionParser
import portage
from portage.dbapi.dep_expand import dep_expand

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError
from flaggie.cache import Caches

def print_help(option, arg, val, parser):
	class PseudoOption:
		def __init__(self, opt, help):
			parser.formatter.option_strings[self] = opt
			self.help = help
			self.dest = ''

	parser.print_help()
	print('''
Actions:''')

	actions = [
		('+flag', 'explicitly enable flag'),
		('-flag', 'explicitly disable flag'),
		('%flag', 'reset flag to the default state (remove it completely)'),
		('%', 'reset all package flags to the default state (drop the package from package.use)'),
		('?flag', 'print the status of a particular flag'),
		('?', 'print package flags')
	]

	parser.formatter.indent()
	for a,b in actions:
		sys.stdout.write(parser.formatter.format_option(PseudoOption(a, b)))
	parser.formatter.dedent()
	sys.exit(0)

class PackageFileSet:
	class PackageFile(list):
		class Whitespace(object):
			def __init__(self, l):
				self.data = l

			def toString(self):
				return self.data

			@property
			def modified(self):
				return False

			@modified.setter
			def modified(self, newval):
				pass

		class PackageEntry:
			class InvalidPackageEntry(Exception):
				pass

			class PackageFlag:
				def __init__(self, s):
					if s[0] in ('-', '+'):
						self.modifier = s[0]
						self.name = s[1:]
					else:
						self.modifier = ''
						self.name = s

				def toString(self):
					return '%s%s' % (self.modifier, self.name)

			def __init__(self, l):
				sl = l.split()
				if not sl or sl[0].startswith('#'): # whitespace
					raise self.InvalidPackageEntry()

				self.as_str = l
				self.modified = False
				self.package = sl.pop(0)
				self.flags = [self.PackageFlag(x) for x in sl]

			def toString(self):
				if not self.modified:
					return self.as_str
				else:
					return ' '.join([self.package] + \
							[x.toString() for x in self.flags]) + '\n'

			def append(self, flag):
				if not isinstance(flag, self.PackageFlag):
					flag = self.PackageFlag(flag)
				self.flags.append(flag)
				self.modified = True
				return flag

			def __iter__(self):
				""" Iterate over all flags in the entry. """
				for f in reversed(self.flags):
					yield f

			def __len__(self):
				return len(self.flags)

			def __getitem__(self, flag):
				""" Iterate over occurences of flag in the entry,
					returning them in the order of occurence. """
				for f in self:
					if f.name == flag:
						yield f

			def __delitem__(self, flag):
				""" Remove all occurences of a flag. """
				flags = []
				for f in self.flags:
					if f.name == flag:
						flags.append(f)
				for f in flags:
					self.flags.remove(f)

				self.modified = True

		def __init__(self, path):
			self.path = path
			# _modified is for when items are removed
			self._modified = False
			f = codecs.open(path, 'r', 'utf8')
			for l in f:
				try:
					e = self.PackageEntry(l)
				except self.PackageEntry.InvalidPackageEntry:
					e = self.Whitespace(l)
				self.append(e)
			f.close()

		@property
		def modified(self):
			if self._modified:
				return True
			for e in self:
				if e.modified:
					return True
			return False

		@modified.setter
		def modified(self, val):
			self._modified = val

		def write(self):
			if not self.modified:
				return

			f = codecs.open(self.path, 'w', 'utf8')
			for l in self:
				f.write(l.toString())
			f.close()

			for e in self:
				e.modified = False
			self.modified = False

	def __init__(self, path):
		self.files = []
		if os.path.isdir(path):
			files = sorted(glob.glob(os.path.join(path, '*')))
		else:
			files = [path]

		for path in files:
			self.files.append(self.PackageFile(path))

	def write(self):
		for f in self.files:
			f.write()

	def append(self, pkg):
		f = self.files[-1]
		if not isinstance(pkg, f.PackageEntry):
			pkg = f.PackageEntry(pkg)
		pkg.modified = True
		f.append(pkg)
		return pkg

	def remove(self, pkg):
		found = False
		for f in self.files:
			try:
				f.remove(pkg)
			except ValueError:
				pass
			else:
				f.modified = True
				found = True
		if not found:
			raise ValueError('%s not found in package.* files.' % pkg)

	def __iter__(self):
		""" Iterate over package entries. """
		for f in reversed(self.files):
			for e in reversed(f):
				if isinstance(e, f.PackageEntry):
					yield e

	def __getitem__(self, pkg):
		""" Get package entries for a package in order of effectiveness
			(the last declarations in the file are effective, and those
			will be returned first). """
		for e in self:
			if e.package == pkg:
				yield e

	def __delitem__(self, pkg):
		""" Delete all package entries for a package. """
		for f in self.files:
			entries = []
			for e in f:
				if e.package == pkg:
					entries.append(e)
			for e in entries:
				f.remove(e)
			f.modified = True

def get_dbapi():
	ptrees = portage.create_trees()
	# XXX: support ${ROOT}
	dbapi = ptrees['/']['porttree'].dbapi

	return dbapi

def parse_actions(args, dbapi):
	out = []
	cache = Caches(dbapi)
	actset = ActionSet(cache = cache)

	for i, a in enumerate(args):
		if not a:
			continue
		try:
			try:
				a = Action(a)
			except Action.NotAnAction:
				if actset:
					out.append(actset)
					actset = ActionSet(cache = cache)
				try:
					atom = dep_expand(a, mydb = dbapi, settings = portage.settings)
				except portage.exception.AmbiguousPackageName as e:
					raise ParserError, 'ambiguous package name, matching: %s' % e
				if atom.startswith('null/'):
					raise ParserError, 'unable to determine the category (mistyped name?)'
				actset.append(atom)
			else:
				actset.append(a)
		except ParserError as e:
			raise ParserError, 'At argv[%d]=\'%s\': %s' % (i, a, e)

	if actset:
		out.append(actset)
	return out
def main(argv):
	opt = OptionParser(
			usage='%prog [options] [<global-use-actions>] [<package> <actions>] [...]',
			version='%%prog %s' % PV,
			description='Easily manipulate USE flags in make.conf and package.use.',
			add_help_option=False
	)
	opt.disable_interspersed_args()
	opt.add_option('-h', '--help', action='callback', callback=print_help,
			help = 'print help message and exit')
	(opts, args) = opt.parse_args(argv[1:])

	dbapi = get_dbapi()
	try:
		act = parse_actions(args, dbapi)
	except ParserError as e:
		print(e)
		return 1

	if not act:
		print_help(None, '', '', opt)

	# (only for testing, to be replaced by something more optimal)
	puse = PackageFileSet('/etc/portage/package.use')
	pkw = PackageFileSet('/etc/portage/package.keywords')

	for actset in act:
		actset(puse, pkw)

	pkw.write()
	puse.write()

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
