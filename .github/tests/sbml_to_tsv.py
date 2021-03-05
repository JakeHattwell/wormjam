#!/usr/bin/env python

import csv
import datetime
import json
import os
from pathlib import Path
from string import Template
import sys
import traceback
from lxml import etree

# debugging
from xml.etree import ElementTree

OUTPUT_LOCATION = Path("tmp")/"output"

def find_sbml_file(directory):
	"""Function to locate an SBML file.

	Args:
		directory (str): Directory containing the SBML file

	Returns:
		str: name of the SBML file. Note, this does not provide the path to the file
	"""	
	SBML_file = [f for f in os.listdir(directory) if f.endswith(".xml")]
	if len(SBML_file) > 1:
		print("WARNING: Multiple XML files found. Using largest file.")
		return sorted(SBML_file,key=lambda f: os.path.getsize(f),reverse=True)[0]
	elif len(SBML_file):
		return SBML_file[0]
	else:
		sys.exit("ERROR: No XML files found. Is this being run from the correct directory?")


def import_sbml_file(SBML_file):
	"""Imports an SBML xml file as a lxml etree Element

	Note that the essentially all information you'll want 
	is in the child attribute "model"

	Args:
		SBML_file (str): string path to the file

	Returns:
		lxml.etree.Element: an lxml etree element
	"""	
	tree = etree.parse(str(Path(os.getcwd())/SBML_file))
	sbml = tree.getroot()
	return sbml

def generate_headers(section):
	children = section.xpath("./*[not(self::sbml:notes)]",namespaces=nsmap)

	annotations = []
	notes = []
	for entity in children:
		entity_annotations = entity.xpath(".//sbml:annotation//dc:identifier",namespaces=nsmap)
		for resource in entity_annotations:
			if (resource:=resource.attrib["{%s}title"%nsmap["dc"]]) not in annotations:
				annotations.append(resource)
		entity_notes = entity.xpath(".//sbml:notes//xhtml:p",namespaces=nsmap)
		for note in entity_notes:
			if (note:=note.text.split(":")[0]) not in notes and note not in ['Comment', 'Curator']:
				notes.append(note)
	
	annotations = ["!Identifiers:"+a for a in annotations]
	notes = ["!Notes:"+n for n in notes]
	unused = section.xpath("./sbml:notes/xhtml:p",namespaces=nsmap)
	if len(unused):
		unused = unused[0].text.split("\n")[1:]
		annotations.extend(a for a in unused if a.startswith("!Identifiers"))
		notes.extend(a for a in unused if a.startswith("!Notes"))
	headers = sorted(annotations + notes)
	return headers

def pull_db_refs_from_sbml(dbs,entity):
	data = []
	notes = [e.text for e in entity.xpath("./sbml:notes//xhtml:p",namespaces=nsmap)]
	for i in dbs:
		search_term = i.split(":")[1]
		if "!Identifier" in i:
			ref = entity.xpath(".//dc:identifier[@dc:title='%s']"% search_term,namespaces=nsmap)
			if len(ref):
				ref = "|".join([i.attrib["{%s}subject" % nsmap["dc"]] for i in ref])
			else:
				ref = ""
		elif "!Notes" in i:
			ref = [note for note in notes if search_term == note.split(": ")[0]]
			if len(ref):
				ref = "|".join([i.split(": ")[1] for i in ref])
			else:
				ref = ""
		else:
			print("WARNING:",i,"is poorly labelled - missing !Identifier or !Notes")
			ref = ""
		data.append(ref)
	comments = [note for note in notes if "Comment" == note.split(": ")[0]]
	curator = [note for note in notes if "Curator" == note.split(": ")[0]]
	for i in [comments,curator]:
		if len(i):
			data.append(i[0].split(": ")[1])
		else:
			data.append("")
	return data

# load the file most likely to be the SBML model
# change os.getcwd() if file is not in the root directory of the github repo
sbml_file = find_sbml_file(os.getcwd())
sbml = import_sbml_file(sbml_file)

# see if an output directory already exists, otherwise make it

if not os.path.isdir(OUTPUT_LOCATION):
	os.makedirs(OUTPUT_LOCATION)

# build namespace map based on what is included in the SBML file
nsmap = {k:v for k,v in sbml.nsmap.items()} 
nsmap["sbml"]=nsmap.pop(None)

# access the model layer of the SBML file and set up SBtab variables
model = sbml.find("{%s}model" % nsmap["sbml"])

NAME = model.attrib["name"]
DATE = datetime.datetime.now().date().isoformat()
SBtabVersionString = "SBtabVersion='1.0'"
SBtabHeaderTemplate = Template("!!SBtab TableID='$TableID' Document='%s' TableType='$TableType' TableName='$TableName' %s Date='%s'" % (NAME,SBtabVersionString,DATE))
	
# CURATORS

# try to find curators
try:
	curators = model.xpath(
		".//vCard:vcards/vCard:vcard",
		namespaces = nsmap
		)

	# if curators were found
	if len(curators):
		# check what information is included in the SBML

		SBtab_header = SBtabHeaderTemplate.substitute(TableID="curator",TableType="Curator",TableName="Curators")
		headers = ["ID","!GivenName","!Surname","!Email","!OrganizationName"]
		with open(OUTPUT_LOCATION/"Curator-SBtab.tsv","w+",newline="") as f:
			curator_tsv = csv.writer(f,delimiter="\t")
			curator_tsv.writerow([SBtab_header])
			curator_tsv.writerow(headers)
			for vCard in curators:
				curator_tsv.writerow([
					vCard.attrib["{%s}about" % nsmap["rdf"]],
					vCard.xpath(".//vCard:given",namespaces=nsmap)[0].text,
					vCard.xpath(".//vCard:surname",namespaces=nsmap)[0].text,
					vCard.xpath(".//vCard:email",namespaces=nsmap)[0].text,
					vCard.xpath(".//vCard:org",namespaces=nsmap)[0].text
				])
		print("COMPLETE: Curators")
	else:
		print("SKIPPED: No curators found")
except Exception as e:
	sys.exit("ERROR: Processing Compartments\n"+str(e))

# GENES
try:
	genes = model.xpath(".//fbc:listOfGeneProducts",namespaces=nsmap)[0]
	if len(genes):
		SBtab_header = SBtabHeaderTemplate.substitute(TableID="compound",TableType="Gene",TableName="Genes")
		dbs = generate_headers(genes)
		headers = ["!ID","!Symbol","!LocusName","!Name"] + dbs + ["!Curator","!Comments"]
		with open(OUTPUT_LOCATION/"Gene-SBtab.tsv","w+",newline="") as f:
			gene_tsv = csv.writer(f,delimiter="\t")
			gene_tsv.writerow([SBtab_header])
			gene_tsv.writerow(headers)
			children = genes.xpath("./*[not(self::sbml:notes)]",namespaces=nsmap)
			for gene in children:
				data = [
					gene.attrib["metaid"],
					gene.attrib["{%s}name"%nsmap["fbc"]].split("@")[0],
					gene.attrib["{%s}name"%nsmap["fbc"]].split("@")[1].split("|")[0],
					gene.attrib["{%s}name"%nsmap["fbc"]].split("|")[1]
					]
				data.extend(pull_db_refs_from_sbml(dbs,gene))
				gene_tsv.writerow(data)
	print("COMPLETE: Genes")
except Exception as e:
	sys.exit("ERROR: Processing Genes\n"+str(e))


# COMPARTMENTS

try:
	compartments = model.xpath(".//sbml:listOfCompartments",namespaces=nsmap)[0]
	if len(compartments):
		SBtab_header = SBtabHeaderTemplate.substitute(TableID="compartment",TableType="Compartment",TableName="Compartments")
		dbs = generate_headers(compartments)
		headers = ["ID","!Name","!Size","!spatialDimensions"] + dbs + ["!Curator","!Comments"]
		with open(OUTPUT_LOCATION/"Compartment-SBtab.tsv","w+",newline="") as f:
			compartment_tsv = csv.writer(f,delimiter="\t")
			compartment_tsv.writerow([SBtab_header])
			compartment_tsv.writerow(headers)
			children = compartments.xpath("./*[not(self::sbml:notes)]",namespaces=nsmap)
			for compartment in children:
				data = [
					compartment.attrib["metaid"],
					compartment.attrib["name"],
					compartment.attrib["size"],
					compartment.attrib["spatialDimensions"]]
				data.extend(pull_db_refs_from_sbml(dbs,compartment))
				compartment_tsv.writerow(data)
	print("COMPLETE: Compartments")
except Exception as e:
	traceback.print_exc(e)
	sys.exit("ERROR: Processing Compartments\n"+str(e))

# COMPOUND
try:
	compounds = model.xpath(".//sbml:listOfSpecies",namespaces=nsmap)[0]
	if len(compounds):
		SBtab_header = SBtabHeaderTemplate.substitute(TableID="compound",TableType="Compound",TableName="Compounds")
		dbs = generate_headers(compounds)
		headers = ["!ID","!Name","!Location","!Charge","!Formula","!IsConstant","!SBOTerm","!InitialConcentration","!hasOnlySubstanceUnits"] + dbs + ["!Curator","!Comments"]
		with open(OUTPUT_LOCATION/"Compound-SBtab.tsv","w+",newline="") as f:
			compound_tsv = csv.writer(f,delimiter="\t")
			compound_tsv.writerow([SBtab_header])
			compound_tsv.writerow(headers)
			children = compounds.xpath("./*[not(self::sbml:notes)]",namespaces=nsmap)
			for species in children:
				data = [
					species.attrib["metaid"],
					species.attrib["name"],
					species.attrib["compartment"],
					species.attrib["{%s}charge"%nsmap["fbc"]],
					species.attrib["{%s}chemicalFormula"%nsmap["fbc"]],
					species.attrib["constant"],
					species.attrib["sboTerm"],
					species.attrib["initialConcentration"],
					species.attrib["hasOnlySubstanceUnits"]
					]
				data.extend(pull_db_refs_from_sbml(dbs,species))
				compound_tsv.writerow(data)
	print("COMPLETE: Compounds")
except Exception as e:
	sys.exit("ERROR: Processing Compounds\n"+str(e))


# compound = model.xpath(".//sbml:listOfSpecies",namespaces=nsmap)
# a = generate_headers(compound[0])
# b = "!ID	!Name	!Location	!Charge	!Formula	!Identifiers:chebi	!Identifiers:pubmed.compound	!Identifiers:doi	!Identifiers:eco	!Comment	!Curator	!Notes:Old_ID	!Identifiers:inchi	!Identifiers:inchikey	!Notes:SMILES	!Notes:Name_neutral	!Notes:Formula_Neutral	!Notes:InChI_neutral	!Notes:InChIKey_neutral	!Notes:SMILES_neutral	!Notes:ChEBI_neutral	!Identifiers:kegg.compound	!Identifiers:biocyc	!Identifiers:hmbd	!Notes:LipidMaps_neutral	!Notes:SwissLipids_neutral	!Notes:Wikidata_neutral	!Notes:Pubchem_neutral	!Notes:Metabolights_neutral	!Notes:Chemspider_neutral	!Identifiers:bigg.metabolite	!Identifiers:metanetx.compound	!Identifiers:reactome	!Identifiers:seed.compound".split("\t")
# print(b)
# print()
# print(a)
# print()
# print([i for i in b if i not in a])
# print()
# print([i for i in a if i not in b])
# print()