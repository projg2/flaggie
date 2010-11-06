#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import os, os.path

from portage import create_trees
from portage.dbapi.dep_expand import dep_expand
from portage.exception import AmbiguousPackageName

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError
from flaggie.cache import Caches
from flaggie.packagefile import PackageFiles

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
	sort_entries = False
	sort_flags = False

	for a in list(argv[1:]):
		if a.startswith('--'):
			if a == '--version':
				print('flaggie %s' % PV)
				return 0
			elif a == '--help':
				print('''Synopsis:
%s [<options>] [<global-actions>] [<packages> <actions>] [...]

Options:
	--sort-entries	Sort package.* file entries by package
			(please note this will drop comments)
	--sort-flags	Sort package.* flags by name
	--sort		Shorthand for --sort-entries and --sort-flags
		
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
(in the same format as taken by emerge).''' % os.path.basename(argv[0]))
				return 0
			elif a == '--sort-entries':
				sort_entries = True
			elif a == '--sort-flags':
				sort_flags = True
			elif a == '--sort':
				sort_entries = True
				sort_flags = True
			elif a == '--':
				argv.remove(a)
				break
			else:
				print('Error: unknown option: %s' % a)
				return 1
			argv.remove(a)

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

	pfiles = PackageFiles()
	for actset in act:
		try:
			actset(pfiles)
		except NotImplementedError as e:
			print('Warning: %s' % e)

	if sort_flags:
		for f in pfiles:
			for pe in f:
				pe.sort()
	if sort_entries:
		for f in pfiles:
			f.sort()

	pfiles.write()

	return 0
