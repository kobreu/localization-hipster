#!/usr/bin/python
from collections import defaultdict
import os
import sys

import shutil
import json
import re   
import codecs
import gspread
import argparse
import getpass
import csv
import xml.etree.ElementTree as ET
from pprint import pprint

langcolumnoffset = 1
keysrowoffset = 1

sys.dont_write_bytecode = True

HOOK_EXPORT_ALTER_TERMS = 'export_alter_terms'
HOOK_IMPORT = 'import_terms'
CONFIG_FILE = os.path.expanduser('~/.l10n-hipster-config')

def diff(a, b):
        b = set(b)
        return [aa for aa in a if aa not in b]

def tree():
    return defaultdict(tree)

def get_languages(sheet):
	langs_list = sheet.row_values(1)
	return langs_list[langcolumnoffset:]
	
def get_keys(sheet):
	return sheet.col_values(1)[keysrowoffset:]
	
def get_terms(sheet):
	keys = get_keys(sheet)
	langs = get_languages(sheet)
	termsdict = tree()
	offset = 0
	records = sheet.get_all_records()
	
	for record in records :
		keyparts = record['Key'].split('/')
		langoffset = 0
		for lang in langs :
			curr = termsdict[lang]
			for i in range(0, len(keyparts)-1):
				curr = curr[keyparts[i]]
			curr[keyparts[len(keyparts)-1]] = record[lang]
			langoffset = langoffset + 1
		offset = offset + 1
	return termsdict
	
def sync_keys(sheet, new_keys):
	keys = get_keys(sheet)
	new = diff(new_keys, keys)
	obs = diff(keys, new_keys)
	print "NEW"
	for n in new:
		print n
	print "OBSOLETE"
	for o in obs:
		print o
		
def sheetrange(sheet, row1, col1, row2, col2):
	return sheet.range(sheet.get_addr_int(row1, col1) + ":" + sheet.get_addr_int(row2, col2))
		
def clear_terms(sheet):
	# TODO what about the context??
	langs = get_languages(sheet)
	sheet.resize(1, langcolumnoffset+len(langs))
	#keys = get_keys(sheet)
	#print sheet.get_addr_int(50,5022220)
	#key_fields = sheet.range(sheet.get_addr_int(keysrowoffset+1, 1) + ":" + sheet.get_addr_int(keysrowoffset+len(keys),1))
	
	#print key_fields
	#print len(langs)
	#for i in range(0, len(langs)):
	#	for j in range(0, len(keys)):
	#		sheet.update_cell(keysrowoffset + j, 1, "")
	#		print "here"
	#		sheet.update_cell(keysrowoffset + j, langcolumnoffset+i, "")

def flatten(data, prefix) :
	#pprint(data)
	res = []
	for key in data :
		if isinstance(data[key],dict):
			#print "true"
			prefix.append(key)
			rec = flatten(data[key], prefix )
			prefix.pop()
			#pprint(rec)
			res.extend(rec)
		else :
			#pprint(data[key])
			prefix.append(key)
			res.append({('/').join(prefix): data[key]})
			prefix.pop()
	return res

def import_terms(sheet, lang, terms):
	#clear_terms(sheet)
	langs = get_languages(sheet)
	keys = get_keys(sheet)
	flattenedterms = flatten(terms, [])
	sheet.resize(keysrowoffset+len(flattenedterms), langcolumnoffset+len(langs))
	# find the row
	try:
		langcell = sheet.find(lang)
	except CellNotFound as cnf:
		# TODO: handle cell not found
		print "Column for language" + lang + " not found, please create!"
	keyrange = sheetrange(sheet, keysrowoffset+1, 1, keysrowoffset+len(flattenedterms), 1)
	keyrange2 = sheetrange(sheet, keysrowoffset+1, langcell.col, keysrowoffset+len(flattenedterms),langcell.col)
	for i in range(0, len(keyrange)):
		keyrange[i].value=flattenedterms[i].keys()[0]
		keyrange2[i].value=flattenedterms[i][flattenedterms[i].keys()[0]]
	sheet.update_cells(keyrange)	
	sheet.update_cells(keyrange2)
			
def get_json(file):
	file2=codecs.open (file , 'r', 'utf-8')
	print os.getcwd()
	print file2
	data = json.load(file2)
	file2.close()
	return data

adddict = { 'en-us' : 'en_US', 'de' : 'de_DE', 'es': 'es_ES', 'fr' : 'fr_FR', 'it' : 'it_IT'}

def load_project(config):
	project_config = open('.l10n', 'r')
	data = json.load(project_config)
	gc = gspread.login(config['user'], config['password'])
	wks = gc.open_by_key(data['Key']).sheet1
	return wks

def _import_custom(sheet, hooks, args):
	print hooks
	#terms = hooks_funcs.export_alter_terms(args.exporter, terms)
	#terms = custom_import.import_custom(args.file)
	#import_terms(sheet, args.l, terms)
	
def get_ios_strings(file):
	file=codecs.open (file , 'r', 'utf-8')
	lines = file.readlines()
	file.close()
	terms = tree()
	for line in lines:
		if re.search(r" = ", line):
			linesplitted = line.split("\"")
			terms[linesplitted[1]] = linesplitted[3]
	return terms
	
def get_android_strings(file):
	xmltree = ET.parse(file)
	root = xmltree.getroot()
	terms = tree()
	for child in root:
		terms[child.get('name')] = child.text
	return terms
	
def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')
	
def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]	
	
# all languages are in one file, so the returned terms are different from json, ios,...
def get_csv_strings(file):
	langs = []
	terms = tree()
	with codecs.open(file,'r', 'utf-8') as file:
		reader=unicode_csv_reader(file, delimiter=';', strict=True) # todo: make delimiter choosable
		for i, row in enumerate(reader):
			if i == 0:
				# first line contains the languages
				for j in range(1, len(row)-1):
					langs.append(row[j])
			else:
				for j in range(1, len(row)-1):
					terms[langs[j-1]][row[0]] = row[j]
	return terms
	
	
	
# TODO: custom import
def get_local_terms(file):
	if(".strings" in args.file):
		terms = get_ios_strings(args.file)
	if(".csv" in args.file):
		terms = get_csv_strings(args.file)
	if("strings.xml" in args.file):
		terms = get_android_strings(args.file)
	else:
		terms = get_json(args.file)
	return terms

def importt(args):
	wks = load_project(args.config)
	(hooks, hooks_funcs) = load_hooks()
	if(hasattr(hooks_funcs, HOOK_IMPORT)):	
		_import_custom(wks, (hooks, hooks_funcs), args)
	else:
		if(".strings" in args.file):
			terms = get_ios_strings(args.file)
			import_terms(wks, args.l, terms)
		if(".csv" in args.file):
			# Todo: message that args.l is ignored if it is set here
			terms = get_csv_strings(args.file)
			for lang in terms:
				import_terms(wks, lang, terms[lang])
		else:
			terms = get_json(args.file)
			import_terms(wks, args.l, terms)	
	
def init(args):
	gc = gspread.login(args.config['user'], args.config['password'])
	wks = gc.open_by_key(args.key).sheet1
	print wks
	try:
		wks.resize(1,2)
	except Exception as ex:
		print ex.read()
		raise ex
	#TODO ask: this will clear sheet 1 of...
	cell1 = sheetrange(wks, 1,1,1,2)
	cell1[0].value = 'Key'
	cell1[1].value = 'en_US'
	wks.update_cells(cell1)
	#cell1 = wks.cell(1,1)
	config = open('.l10n', 'w+')
	json.dump({'Key' : args.key},config)
	config.close()
	print "Initialized empty Localization Project (" + args.key + ")";
	
def _export_custom(terms, args):
	sys.path.append(os.path.abspath('.'))
	import custom_export
	custom_export.export_custom(terms)

def replace_placeholders(term):
	res = term
	c = 0

	while "%@" in res:
		c = c+1
		res = res.replace("%@", "%" + str(c) + "$s", 1)
	return res
	
def has_hook(hooks, hook):
	return hook in hooks
	
def load_hooks():
	if os.path.isfile('hooks.py'):
		sys.path.append(os.path.abspath('.'))
		has_hooks = []
		import hooks as hooks_funcs
		if hasattr(hooks_funcs, HOOK_EXPORT_ALTER_TERMS):
			has_hooks.append(HOOK_EXPORT_ALTER_TERMS)
		if hasattr(hooks_funcs, HOOK_IMPORT):
			has_hooks.append(HOOK_IMPORT)
		return (has_hooks, hooks_funcs)
	else:
		return ([], {})
			
def export(args):
	wks = load_project(args.config)
	terms = get_terms(wks)
	(hooks, hooks_funcs) = load_hooks()
	if has_hook(hooks, HOOK_EXPORT_ALTER_TERMS):
		# todo make this changeable
		terms = hooks_funcs.export_alter_terms(args.exporter, terms)
	if os.path.isfile('custom_export.py'):
		_export_custom(terms, args)
	elif args.exporter == 'json':
		for lang in terms:
			langfile = codecs.open(lang + '.json', 'w+', 'utf-8')
			json.dump(terms[lang], langfile, indent=4, ensure_ascii=False)
	elif args.exporter == 'ios':
		for lang in terms:
			foldername = lang.split("_")[0] + ".lproj"
			os.makedirs(foldername)
			langfile = codecs.open(foldername + "/Localizable.strings", 'w', 'utf-8')
			flattenedterms = flatten(terms[lang], [])
			for term in flattenedterms:
				for key in term:
					langfile.write("\"" + key + "\" = \"" + term[key].replace("\"", "\\\"") + "\";\n");
			langfile.close()
	elif args.exporter == 'android':
		for lang in terms:
			# TODO: adapt placeholders
			foldername = 'values' if lang.split("_")[0] == 'en' else 'values-' + lang.split("_")[0];
			os.makedirs(foldername)
			langfile = codecs.open(foldername + "/strings.xml", 'w', 'utf-8')
			langfile.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
			langfile.write("<resources>\n")
			flattenedterms = flatten(terms[lang], [])
			for term in flattenedterms:
				for key in term:
					value = replace_placeholders(term[key])
					langfile.write("<string name=\""+key+"\">\""+value+"\"</string>\n")
			langfile.write("</resources>")
			langfile.close()
	elif args.export == 'csv':
		with codecs.open("terms.csv", 'w', 'utf-8') as file:
			print "not yet implemented"
			

def compare(args):
	wks = load_project(args.config)
	local_terms = map(lambda x: x.keys()[0], flatten(get_local_terms(args.file), []))
	sync_keys(wks, local_terms)
	
def load_global_config():
	if(not os.path.isfile(CONFIG_FILE)):
		print "Set your Google Drive username with l10n config --user <USER>"
		sys.exit(0)
	else:
		config = open(CONFIG_FILE, 'r')
		data = json.load(config)
		# ask for password
		password = getpass.getpass('Google Drive Password:')
		data['password'] = password
		return data
	
def config(args):
		with open(CONFIG_FILE, 'w+') as file:
			try:
				config = json.load(file)
			except ValueError:
				config = {}
			config['user'] = args.user
			json.dump(config, file)
		
	
parser = argparse.ArgumentParser(description='i18n command line')
subparsers = parser.add_subparsers(help='TODO #1')

parser_init = subparsers.add_parser('init', help='init a project')
parser_init.add_argument('key', help='the google spreadsheet key')
parser_init.set_defaults(func=init)
parser_flush = subparsers.add_parser('flush', help='flush the translations')
parser_import = subparsers.add_parser('import', help='import')
parser_import.add_argument('file', default ='', type=str)
parser_import.add_argument('-l', default='en_US', type=str)
parser_import.set_defaults(func=importt)
parser_export = subparsers.add_parser('export', help='export')
parser_export.add_argument('--exporter', default='json', type=str)
parser_export.set_defaults(func=export)
parser_compare = subparsers.add_parser('compare', help='compare')
parser_compare.add_argument('file', help='file', type=str)
parser_compare.set_defaults(func=compare)
parser_compare = subparsers.add_parser('config', help='config')
parser_compare.add_argument('--user', type=str)
parser_compare.set_defaults(func=config)


args = parser.parse_args()
if args.func != config:
	config = load_global_config()
	args.config = config;
args.func(args)



'''
def tree():
    return defaultdict(tree)


client = POEditorAPI(api_token='a2909ab94ada1e7dd50206aa22d5fc76')
projects = client.list_projects()
#print projects
# create a new project
#client.create_project("name", "description")
# view project details
# list project languages
languages = client.list_project_languages("19498")
# 
termsdict = tree()
try:
	shutil.rmtree('dashboard')
except OSError:
	pass
os.makedirs('dashboard')
for language in languages:
	# get translations
	terms = client.view_project_terms("19498", language['code'])
	for term in terms:
		#print term
		termsplit = term['term'].split("/");
		lenn = len(termsplit)
		curr = termsdict
		print curr
		for i in range(0, lenn-1):
			curr = curr[termsplit[i]]
		curr[termsplit[len(termsplit)-1]] = term['definition']['form'] 
		#termsdict[]
	#print terms
	file=codecs.open ('dashboard/'+adddict[language['code']]+'.json' , 'w', 'utf-8')
	json.dump(termsdict, file, sort_keys=True, indent=4, ensure_ascii=False)
	pprint(dict(termsdict))
# generate files

'''
