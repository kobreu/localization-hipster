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
import cStringIO
import xlsxwriter
from pprint import pprint

langcolumnoffset = 1
keysrowoffset = 1

sys.dont_write_bytecode = True

HOOK_EXPORT_ALTER_TERMS = 'export_alter_terms'
HOOK_IMPORT = 'import_terms'
HOOK_EXPORT_TERMS = 'export_terms'
CONFIG_FILE = os.path.expanduser('~/.l10n-hipster-config')

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

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

def get_notes(sheet):
	keys = get_keys(sheet)
	langs = get_languages(sheet)
	values = sheet.col_values(len(langs)+langcolumnoffset+1)[keysrowoffset:]
	# bring value to the same length as keys to have "None" for the rest
	values = values + [None]*(len(keys)-len(values))
	notes = dict(zip(keys, values))
	return notes
		
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

def load_project_with_key(key, user, password):
	gc = gspread.login(user, password)
	wks = gc.open_by_key(key).sheet1
	return wks

def load_project(config):
	project_config = open('.l10n', 'r')
	data = json.load(project_config)
	return load_project_with_key(data['Key'], config['user'], config['password'])

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
def get_csv_strings(file, delimiter=';'):
	langs = []
	terms = tree()
	with codecs.open(file,'r', 'utf-8') as file:
		reader=unicode_csv_reader(file, delimiter=delimiter, strict=True) # todo: make delimiter choosable
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
	
def get_property_terms(file):
	return dict(line.strip().split('=') for line in codecs.open(file, 'r', 'utf-8') if line.strip() != "")
	

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
		if(".properties" in args.file):
			terms = get_property_terms(args.file)
			import_terms(wks, args.l, terms)
		else:
			terms = get_json(args.file)
			import_terms(wks, args.l, terms)	
			
			
def init(args):
	wks = load_project(args.config)
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
	print "Initialized empty translation project at " + wks.title + "";
		
def link(args):
	config = open('.l10n', 'w+')
	json.dump({'Key' : args.key},config)
	config.close()
	print "Linked with spreadsheet at " + args.key +".";
		
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
		if hasattr(hooks_funcs, HOOK_EXPORT_TERMS):
			has_hooks.append(HOOK_EXPORT_TERMS)
		return (has_hooks, hooks_funcs)
	else:
		return ([], {})
		

	
def lint(sheet):
	range = sheet.col_values(1)
	error = False
	for index, key in enumerate(range):
		if not key:
			print "Error: Empty key at row " + str(index) + ". Give this row a key by editing the column A, row " + str(index) + " in the spreadsheet."
			error = True
	
	terms = get_terms(sheet)
	missingTranslationError = False
	for lang in terms:
		flattenedterms = flatten(terms[lang], [])
		for term in flattenedterms:
			for key in term.iterkeys():
				if not term[key]:
					print "Error: Empty translation for key " + key + " and language " + lang + "."
					missingTranslationError = True
					
	if missingTranslationError:
		print "There are missing translations. Use --force to export empty translations or specify a fallback language with --fallback."
		return ['missingTranslationError']
	elif error:
		return ['error']
	else:
		return []
	
def merge_empty(fallback, potentiallyempty):
	for key in potentiallyempty:
		if isinstance(potentiallyempty[key], dict):
			merge_empty(fallback[key], potentiallyempty[key])
		elif not potentiallyempty[key]:
			potentiallyempty[key] = fallback[key]
			
def escapeproperties(term):
	ret = term.replace("\n", "\\n")
	ret = ret.replace("=", "\\=")
	ret = ret.replace(":", "\\:")
	return ret
	
class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
    	print row
    	print [s.encode("utf-8") for s in row]
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        print data
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
	

def export_to_csv(terms):
	with open("terms.csv", 'w') as file:
		writer = UnicodeWriter(file, delimiter=',')
		writer.writerow(['Key'] + terms.keys())
		for idx, term in enumerate(terms[terms.keys()[0]]):
			key = term.keys()[0]
			row = [unicode(terms[lang][idx][key]) for lang in terms.keys()]
			writer.writerow([key] + row)
		

def split(x):
	if (isinstance(x,unicode) or isinstance(x, str)):
		return x.split("\n")
	else:
		return x
		
def foreach(tree, fn):
	for key in tree:
		if isinstance(tree[key],dict):
			foreach(tree[key],fn)
		else:
			tree[key] = fn(tree[key])
		
def export(args):
	wks = load_project(args.config)
	lint_result = lint(wks)
	terms = get_terms(wks)
	if 'error' in lint_result:
		sys.exit(1)
	elif 'missingTranslationError' in lint_result:
		if not args.fallback:
			sys.exit(1)
		else: # TODO: don't print errors if fallback language was chosen
			print "Using fallback language: " + args.fallback
			#TODO: what if fallback language has missing translations?
			for lang in terms.keys():
				merge_empty(terms[args.fallback],terms[lang])
	(hooks, hooks_funcs) = load_hooks()
	if has_hook(hooks, HOOK_EXPORT_ALTER_TERMS):
		# todo make this changeable
		terms = hooks_funcs.export_alter_terms(args.exporter, terms)
	if has_hook(hooks, HOOK_EXPORT_TERMS):
		hooks_funcs.export_terms(terms)
	elif args.exporter == 'json':
		for lang in terms:
			langfile = codecs.open(args.prefix + lang + '.json', 'w+', 'utf-8')
			if(args.split):
				foreach(terms[lang][args.split_prefix], split) 	
			json.dump(terms[lang], langfile, indent=4, ensure_ascii=False)
	elif args.exporter == 'ios':
		for lang in terms:
			langfile = codecs.open("Localizable-" + lang + ".strings", 'w', 'utf-8')
			flattenedterms = flatten(terms[lang], [])
			for term in flattenedterms:
				for key in term:
					langfile.write("\"" + key + "\" = \"" + term[key].replace("\"", "\\\"") + "\";\n");
			langfile.close()
	elif args.exporter == 'android':
		for lang in terms:
			# TODO: adapt placeholders
			langfile = codecs.open("strings-"+lang+".xml", 'w', 'utf-8')
			langfile.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
			langfile.write("<resources>\n")
			flattenedterms = flatten(terms[lang], [])
			for term in flattenedterms:
				for key in term:
					value = replace_placeholders(term[key])
					langfile.write("<string name=\""+key+"\">\""+value+"\"</string>\n")
			langfile.write("</resources>")
			langfile.close()
	elif args.exporter == 'properties':
		for lang in terms:
			langfile = codecs.open(lang+".properties", 'w', 'utf-8')
			flattenedterms = flatten(terms[lang], [])
			for term in flattenedterms:
				for key in term:
					langfile.write(key + " = " + escapeproperties(term[key]) + "\n")
			langfile.close()
	elif args.exporter == 'csv':
		flattenedterms = {lang : flatten(terms[lang], []) for lang in terms.keys()}
		export_to_csv(flattenedterms)

			

def compare(args):
	wks = load_project(args.config)
	local_terms = map(lambda x: x.keys()[0], flatten(get_local_terms(args.file), []))
	sync_keys(wks, local_terms)
	
def combined_import_compare(args):
	terms = get_csv_strings(args.file, ",")
	# separate by file
	allterms = tree()
	for lang in terms:
		for k,v in terms[lang].items():
			split = k.split("/")
			allterms[split[0]][lang]['/'.join(split[1:])]=v
	for sheetid,sheetterms in allterms.items():
		wks = load_project_with_key(sheetid, args.config['user'], args.config['password'])
		onlineterms = get_terms(wks)
		onlinetermsflattened = {lang : flatten(onlineterms[lang], []) for lang in onlineterms.keys()}
		onlinetermsflattenedtransformed = tree()
		for lang in onlinetermsflattened.keys():
			transformed = tree()
			for termdict in onlinetermsflattened[lang]:
				for k,v in termdict.items():
					transformed[k] = v
			onlinetermsflattenedtransformed[lang] = transformed
		for lang, langterms in sheetterms.items():
			if lang == "":
				continue
			# for now, compare only
			for key, value in langterms.items():
				#print value != onlinetermsflattenedtransformed[lang][key]
				#print value + " " + onlinetermsflattenedtransformed[lang][key]
				if value != onlinetermsflattenedtransformed[lang][key]:
					print "diff!!! at " + lang + " " + key
					
			#import_terms(wks, lang, langterms)


def import_term(sheet, language, key, value):
	# find the row
	langcell = sheet.find(language)
	keyrow = sheet.find(key)
	
	keyrange = sheetrange(sheet, keyrow.row, langcell.col, keyrow.row, langcell.col)
	keyrange[0].value=value
	sheet.update_cells(keyrange)

def combined_import(args):
	terms = get_csv_strings(args.file, ",")
	# separate by file
	allterms = tree()
	for lang in terms:
		for k,v in terms[lang].items():
			split = k.split("/")
			allterms[split[0]][lang]['/'.join(split[1:])]=v
	for sheetid,sheetterms in allterms.items():
		wks = load_project_with_key(sheetid, args.config['user'], args.config['password'])
		onlineterms = get_terms(wks)
		onlinetermsflattened = {lang : flatten(onlineterms[lang], []) for lang in onlineterms.keys()}
		onlinetermsflattenedtransformed = tree()
		for lang in onlinetermsflattened.keys():
			transformed = tree()
			for termdict in onlinetermsflattened[lang]:
				for k,v in termdict.items():
					transformed[k] = v
			onlinetermsflattenedtransformed[lang] = transformed
		for lang, langterms in sheetterms.items():
			if lang == "" or lang == "Notes" or lang == "Kommentare":
				continue
			# for now, compare only
			for key, value in langterms.items():
				#print value != onlinetermsflattenedtransformed[lang][key]
				#print value + " " + onlinetermsflattenedtransformed[lang][key]
				if value != onlinetermsflattenedtransformed[lang][key]:
					if not onlinetermsflattenedtransformed[lang][key]:
						print "Inserting text \n" + value.encode('ascii', 'backslashreplace') + "\nfor "  + key + " and language " + lang + ""
						import_term(wks, lang, key, value)

					else:
						answer = query_yes_no("Should I replace text \n" + onlinetermsflattenedtransformed[lang][key].encode('ascii', 'backslashreplace') + "\n with \n" + value.encode('ascii', 'backslashreplace') + "\nkey "+ key + " for language " + lang + "?", "no")
						if answer:
							import_term(wks, lang, key, value)
			#import_terms(wks, lang, langterms)			
	
def combined_export(args):
	projects = args.files.split(",")
	allterms = defaultdict(list)
	allnotes = {}
	print projects
	for project in projects:
		print project
		wks = load_project_with_key(project, args.config['user'], args.config['password'])
		terms = get_terms(wks)
		flattenedterms = {lang : flatten(terms[lang], [project]) for lang in terms.keys()}
		for lang in flattenedterms:
			allterms[lang]  = allterms[lang] + flattenedterms[lang]
		notes = get_notes(wks)
		notes = allnotes.update({ project + "/" + k: v for k, v in notes.items() })
	print allterms
	workbook = xlsxwriter.Workbook('terms.xlsx')
	worksheet = workbook.add_worksheet()
	format = workbook.add_format()
	format.set_text_wrap()
	headformat = workbook.add_format()
	headformat.set_font_size(20)
	worksheet.write(0,0, "Key", headformat)
	i = 1
	for key in allterms.keys():
		worksheet.write(0,i, key, headformat)
		i = i+1
	worksheet.write(0,i, "Notes", headformat)
	i = 1
	for idx, term in enumerate(allterms[allterms.keys()[0]]):
		j = 1
		key = term.keys()[0]
		worksheet.write(i,0,key)
		for lang in terms.keys():
			worksheet.write(i,j, allterms[lang][idx][key], format)
			j = j+1
		worksheet.write(i,j, allnotes[key], format)
		i = i + 1
	formatCond = workbook.add_format()
	formatCond.set_bg_color('yellow')
	worksheet.freeze_panes(1,0)
	worksheet.conditional_format(1,1,len(allterms[allterms.keys()[0]]), len(allterms), { 'type' : 'blanks', 'format': formatCond })
	workbook.close()
	
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

parser_link = subparsers.add_parser('link', help='link to a spreadsheet')
parser_link.add_argument('key', help='the google spreadsheet key')
# TODO:
# parser_link.add_argument('sheet', help='the sheet of the project')
parser_link.set_defaults(func=link)
parser_init = subparsers.add_parser('init', help='init a project')
#parser_init.add_argument('key', help='the google spreadsheet key')
parser_init.set_defaults(func=init)
parser_flush = subparsers.add_parser('flush', help='flush the translations')
parser_import = subparsers.add_parser('import', help='import')
parser_import.add_argument('file', default ='', type=str)
parser_import.add_argument('-l', default='en_US', type=str)
parser_import.set_defaults(func=importt)
parser_export = subparsers.add_parser('export', help='export')
parser_export.add_argument('--exporter', default='json', type=str)
parser_export.add_argument('--fallback', type=str)
parser_export.add_argument('--prefix', type=str)
parser_export.add_argument('--split', nargs='?', const=True, default=False)
parser_export.add_argument('--split_prefix', type=str)
parser_export.set_defaults(func=export)
parser_compare = subparsers.add_parser('compare', help='compare')
parser_compare.add_argument('file', help='file', type=str)
parser_compare.set_defaults(func=compare)
parser_compare = subparsers.add_parser('config', help='config')
parser_compare.add_argument('--user', type=str)
parser_compare.set_defaults(func=config)
parser_combined_export = subparsers.add_parser('combined-export', help='combined export')
parser_combined_export.add_argument('files', type=str)
parser_combined_export.set_defaults(func=combined_export)
parser_combined_import = subparsers.add_parser('combined-import-compare', help='combined import compare')
parser_combined_import.add_argument('file', type=str)
parser_combined_import.set_defaults(func=combined_import_compare)
parser_combined_import = subparsers.add_parser('combined-import', help='combined import')
parser_combined_import.add_argument('file', type=str)
parser_combined_import.set_defaults(func=combined_import)


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
