#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import sys
from optparse import OptionParser
import portage
from portage.dbapi.dep_expand import dep_expand

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError
from flaggie.cache import Caches
from flaggie.packagefile import PackageFileSet

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
