#!/usr/bin/python
#	vim:fileencoding=utf-8
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license.

import codecs, locale, os, os.path, sys

from portage import create_trees
from portage.const import USER_CONFIG_PATH
from portage.dbapi.dep_expand import dep_expand
from portage.exception import AmbiguousPackageName, InvalidAtom

from flaggie import PV
from flaggie.action import Action, ActionSet, ParserError, ParserWarning
from flaggie.cache import Caches
from flaggie.cleanup import DropIneffective, DropUnmatchedPkgs, \
		DropUnmatchedFlags, SortEntries, SortFlags
from flaggie.packagefile import PackageFiles, PackageFileConflict

def parse_actions(args, dbapi, settings, quiet = False, strict = False, \
		cleanupact = [], dataout = sys.stdout, output = sys.stderr):
	out = []
	cache = Caches(dbapi)
	actset = ActionSet(cache = cache)
	had_pkgs = False

	for i, a in enumerate(args):
		if not a:
			continue
		try:
			try:
				act = Action(a, output = dataout)
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
				output.write('At argv[%d]=\'%s\': %s\n' % (i + 1, a, e))
			if strict:
				if not quiet:
					output.write('Strict mode, aborting.\n')
				return None

	if actset and (actset.pkgs or not had_pkgs):
		out.append(actset)

	if cleanupact:
		actset = ActionSet(cache = cache)
		for a in cleanupact:
			actset.append(a(dbapi))
		out.append(actset)

	return out

def main(argv):
	cleanup_actions = set()
	quiet = False
	strict = False

	locale.setlocale(locale.LC_ALL, '')
	# Python3 does std{in,out,err} and argv recoding implicitly
	if not hasattr(argv[0], 'decode'):
		dataout = sys.stdout
		output = sys.stderr
	else:
		indec = codecs.getdecoder(locale.getpreferredencoding())
		argv = [indec(x)[0] for x in argv]
		dataout = codecs.getwriter(locale.getpreferredencoding())(sys.stderr, 'backslashescape')
		output = codecs.getwriter(locale.getpreferredencoding())(sys.stderr, 'backslashescape')

	for a in list(argv[1:]):
		if a.startswith('--'):
			if a == '--version':
				output.write('flaggie %s\n' % PV)
				return 0
			elif a == '--help':
				output.write('''Synopsis:
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

	--drop-unmatched-pkgs	Drop packages which no longer are available
				in portdb
	--drop-unmatched-flags	Drop flags which are not found in package's
				IUSE, KEYWORDS and/or LICENSE variables
	--destructive-cleanup	Shorthand for all of the above
		
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
format as taken by emerge).\n''' % os.path.basename(argv[0]))
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
			elif a == '--drop-unmatched-pkgs':
				cleanup_actions.add(DropUnmatchedPkgs)
			elif a == '--drop-unmatched-flags':
				cleanup_actions.add(DropUnmatchedFlags)
			elif a == '--destructive-cleanup':
				cleanup_actions.add(DropIneffective)
				cleanup_actions.add(SortEntries)
				cleanup_actions.add(SortFlags)
				cleanup_actions.add(DropUnmatchedPkgs)
				cleanup_actions.add(DropUnmatchedFlags)
			elif a == '--':
				argv.remove(a)
				break
			else:
				output.write('Error: unknown option: %s\n' % a)
				return 1
			argv.remove(a)

	trees = create_trees(
			config_root = os.environ.get('PORTAGE_CONFIGROOT'),
			target_root = os.environ.get('ROOT'))
	porttree = trees[max(trees)]['porttree']

	act = parse_actions(argv[1:], porttree.dbapi, porttree.settings, \
			quiet = quiet, strict = strict, cleanupact = cleanup_actions, \
			output = output, dataout = dataout)
	if act is None:
		return 1
	if not act:
		main([argv[0], '--help'])
		return 0

	try:
		pfiles = PackageFiles(os.path.join( \
			porttree.settings['PORTAGE_CONFIGROOT'], USER_CONFIG_PATH), porttree)
	except PackageFileConflict as e:
		output.write('%s\n' % e)
		return 1

	for actset in act:
		try:
			actset(pfiles)
		except NotImplementedError as e:
			output.write('Warning: %s\n' % e)

	pfiles.write()

	return 0
