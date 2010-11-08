#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import os, os.path

from portage import create_trees
from portage.const import USER_CONFIG_PATH
from portage.dbapi.dep_expand import dep_expand
from portage.exception import AmbiguousPackageName, InvalidAtom

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError, ParserWarning
from flaggie.cache import Caches
from flaggie.cleanup import DropIneffective, SortEntries, SortFlags
from flaggie.packagefile import PackageFiles

def parse_actions(args, dbapi, settings, quiet = False, strict = False):
	out = []
	cache = Caches(dbapi)
	actset = ActionSet(cache = cache)
	had_pkgs = False

	for i, a in enumerate(args):
		if not a:
			continue
		try:
			try:
				act = Action(a)
			except Action.NotAnAction:
				if actset:
					# Avoid transforming actset with all atoms being
					# incorrect into global actions.
					if actset.pkgs or not had_pkgs:
						out.append(actset)
					actset = ActionSet(cache = cache)
				had_pkgs = True
				try:
					atom = dep_expand(a, mydb = dbapi, settings = settings)
				except AmbiguousPackageName as e:
					raise ParserError('ambiguous package name, matching: %s' % e)
				except InvalidAtom as e:
					raise ParserError('invalid package atom: %s' % e)
				if atom.startswith('null/'):
					raise ParserError('unable to determine the category (mistyped name?)')
				actset.append(atom)
			except ParserWarning as w:
				actset.append(act)
				raise
			else:
				actset.append(act)
		except (ParserError, ParserWarning) as e:
			if not quiet or strict:
				print('At argv[%d]=\'%s\': %s' % (i + 1, a, e))
			if strict:
				if not quiet:
					print('Strict mode, aborting.')
				return None

	if actset and (actset.pkgs or not had_pkgs):
		out.append(actset)
	return out

def main(argv):
	cleanup_actions = set()
	quiet = False
	strict = False

	for a in list(argv[1:]):
		if a.startswith('--'):
			if a == '--version':
				print('flaggie %s' % PV)
				return 0
			elif a == '--help':
				print('''Synopsis:
%s [<options>] [<global-actions>] [<packages> <actions>] [...]

Options:
	--quiet			Silence argument errors and warnings
	--strict		Abort if at least a single flag is invalid

	--drop-ineffective	Drop ineffective flags (those which are
				overriden by later declarations)
	--sort-entries		Sort package.* file entries by package
				(please note this will drop comments)
	--sort-flags		Sort package.* flags by name
	--sort			Shorthand for --sort-entries and --sort-flags
	--cleanup		Shorthand for --drop-ineffective and --sort
		
Global actions are applied to the make.conf file. Actions are applied to
the package.* files, for the packages preceding them.

An action can be one of:
	+arg	explicitly enable arg
	-arg	explicitly disable arg
	%%arg	reset arg to the default state (remove it from the file)
	?arg	print the effective status of arg (due to the file)

The action argument must be either a USE flag, a keyword or a license name.
For the '%%' and '?' actions, it can be also one of 'use::', 'kw::' or 'lic::'
in order to apply the action to all of the flags, keywords or licenses
respectively.

A package specification can be any atom acceptable for Portage (in the same
format as taken by emerge).''' % os.path.basename(argv[0]))
				return 0
			elif a == '--quiet':
				quiet = True
			elif a == '--strict':
				strict = True
			elif a == '--drop-ineffective':
				cleanup_actions.add(DropIneffective)
			elif a == '--sort-entries':
				cleanup_actions.add(SortEntries)
			elif a == '--sort-flags':
				cleanup_actions.add(SortFlags)
			elif a == '--sort':
				cleanup_actions.add(SortEntries)
				cleanup_actions.add(SortFlags)
			elif a == '--cleanup':
				cleanup_actions.add(DropIneffective)
				cleanup_actions.add(SortEntries)
				cleanup_actions.add(SortFlags)
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

	act = parse_actions(argv[1:], porttree.dbapi, porttree.settings, \
			quiet = quiet, strict = strict)
	if act is None:
		return 1
	if not act and not cleanup_actions:
		main([argv[0], '--help'])
		return 0

	pfiles = PackageFiles(os.path.join( \
		porttree.settings['PORTAGE_CONFIGROOT'], USER_CONFIG_PATH))
	for actset in act:
		try:
			actset(pfiles)
		except NotImplementedError as e:
			print('Warning: %s' % e)

	for a in cleanup_actions:
		a(pfiles)

	pfiles.write()

	return 0
