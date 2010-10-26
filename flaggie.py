#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

PV = '0.1'

import sys, os.path
from optparse import OptionParser
import portage
from portage.dbapi.dep_expand import dep_expand

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

class ParserError(Exception):
	pass

class FlagCache:
	def __init__(self, dbapi):
		self.dbapi = dbapi
		self.cache = {}

	def glob(self):
		if None not in self.cache:
			flags = set()
			for r in self.dbapi.porttrees:
				try:
					f = open(os.path.join(r, 'profiles', 'use.desc'), 'r')
				except IOError:
					pass
				else:
					for l in f:
						ll = l.split(' - ', 1)
						if len(ll) > 1:
							flags.add(ll[0])
					f.close()
			self.cache[None] = flags
			
		return self.cache[None]

	def __getitem__(self, k):
		if k not in self.cache:
			flags = set()
			# get widest match possible to make sure we do not complain without a reason
			for p in self.dbapi.xmatch('match-all', k):
				flags |= set([x.lstrip('+') for x in self.dbapi.aux_get(p, ('IUSE',))[0].split()])
			self.cache[k] = flags
		return self.cache[k]

class Action:
	class _argopt:
		def __init__(self, arg, key):
			self.arg = arg if arg != '' else None

		def check_validity(self, pkgs, flagcache):
			if self.arg is None:
				return True
			if not pkgs:
				return self.arg in flagcache.glob()

			for p in pkgs:
				if self.arg in flagcache[p]:
					return True
				
			return False

	class _argreq(_argopt):
		def __init__(self, arg, key):
			if arg == '':
				raise ParserError, '%s action requires an argument!' % key
			self.arg = arg

	class enable(_argreq):
		pass

	class disable(_argreq):
		pass

	class reset(_argopt):
		pass

	class output(_argopt):
		pass

	mapping = {
		'+': enable,
		'-': disable,
		'%': reset,
		'?': output
	}

	class NotAnAction(Exception):
		pass

	@classmethod
	def get(cls, a):
		if a[0] in cls.mapping:
			return cls.mapping[a[0]](a[1:], a[0])
		else:
			raise cls.NotAnAction

def get_dbapi():
	ptrees = portage.create_trees()
	# XXX: support ${ROOT}
	dbapi = ptrees['/']['porttree'].dbapi

	return dbapi

def parse_actions(args, dbapi):
	out = [([], [])]
	i = 1

	for a in args:
		try:
			if a == '':
				continue
			try:
				out[-1][1].append(Action.get(a))
			except Action.NotAnAction:
				if out[-1][1]:
					out.append(([], []))
				try:
					atom = dep_expand(a, mydb = dbapi, settings = portage.settings)
				except portage.exception.AmbiguousPackageName as e:
					raise ParserError, 'ambiguous package name, matching: %s' % e
				if atom.startswith('null/'):
					raise ParserError, 'unable to determine the category (mistyped name?)'
				out[-1][0].append(atom)
		except ParserError as e:
			raise ParserError, 'At argv[%d]=\'%s\': %s' % (i, a, e)
		else:
			i += 1

	return out

def main(argv):
	opt = OptionParser(
			usage='%prog [options] <package-or-action> [...]',
			version='%%prog %s' % PV,
			description='Easily manipulate USE flags in make.conf and package.use. Specify package names (or DEPEND atoms) and any amount of actions following it. The actions will be applied to the package prepending them. If more than one package is specified one after another (without actions between them), the following actions will be applied to all of them. The actions prepending the first package will be applied to the global USE flags.',
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

	if not act[-1][1]:
		print_help(None, '', '', opt)

	flagcache = FlagCache(dbapi)
	for (pkgs, actions) in act:
		for a in actions:
			if not a.check_validity(pkgs, flagcache):
				print('Warning: %s seems to be incorrect flag for %s' % (a.arg, pkgs))
	
	print(act)

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
