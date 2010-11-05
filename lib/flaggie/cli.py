#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import os

from portage import create_trees
from portage.dbapi.dep_expand import dep_expand
from portage.exception import AmbiguousPackageName

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError
from flaggie.cache import Caches
from flaggie.packagefile import PackageFileSet

def parse_actions(args, dbapi, settings):
	out = []
	cache = Caches(dbapi)
	actset = ActionSet(cache = cache)

	for i, a in enumerate(args):
		if not a:
			continue
		try:
			try:
				act = Action(a)
			except Action.NotAnAction:
				if actset:
					out.append(actset)
					actset = ActionSet(cache = cache)
				try:
					atom = dep_expand(a, mydb = dbapi, settings = settings)
				except AmbiguousPackageName as e:
					raise ParserError('ambiguous package name, matching: %s' % e)
				if atom.startswith('null/'):
					raise ParserError('unable to determine the category (mistyped name?)')
				actset.append(atom)
			else:
				actset.append(act)
		except ParserError as e:
			raise ParserError('At argv[%d]=\'%s\': %s' % (i, a, e))

	if actset:
		out.append(actset)
	return out

def main(argv):
	for a in list(argv[1:]):
		if a == '--version':
			print('flaggie %s' % PV)
			return 0
		elif a == '--help':
			print('''Synopsis: %s [<global-actions>] [<packages> <actions>] [...]
	
Global actions are applied to the make.conf file. Actions are applied to
the package.* files, for the packages preceding them.

An action can be one of:
	+arg	explicitly enable arg
	-arg	explicitly disable arg
	%%arg	reset arg to the default state (remove it from the file)
	?arg	print the effective status of arg (due to the file)

The action argument must be either a USE flag, a keyword or a license
name. For the '%%' and '?' actions, it can be also one of 'use::', 'kw::'
or 'lic::' in order to apply the action to all of the flags, keywords
or licenses respectively.

A package specification can be any atom acceptable for Portage
(in the same format as taken by emerge).''' % argv[0])
			return 0
		elif a == '--':
			argv.remove(a)
			break
		elif a.startswith('--'):
			print('Error: unknown option: %s' % a)
			return 1

	trees = create_trees(
			config_root = os.environ.get('PORTAGE_CONFIGROOT'),
			target_root = os.environ.get('ROOT'))
	porttree = trees[max(trees)]['porttree']

	try:
		act = parse_actions(argv[1:], porttree.dbapi, porttree.settings)
	except ParserError as e:
		print(e)
		return 1

	if not act:
		main([argv[0], '--help'])
		return 0

	# (only for testing, to be replaced by something more optimal)
	pfiles = {
		'use': PackageFileSet('/etc/portage/package.use'),
		'kw': PackageFileSet('/etc/portage/package.keywords'),
		'lic': PackageFileSet('/etc/portage/package.license')
	}

	for actset in act:
		actset(pfiles)

	for f in pfiles.values():
		f.write()

	return 0
