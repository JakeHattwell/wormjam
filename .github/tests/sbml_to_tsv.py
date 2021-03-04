#!/usr/bin/env python

import csv
import datetime
import json
import os
from pathlib import Path
from string import Template
import sys

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
	
# try to find curators
curators = model.xpath(
	".//vCard:vcards/vCard:vcard",
	namespaces = nsmap
	)

# if curators were found
if len(curators):
	# check what information is included in the SBML

	headers = ["ID","!GivenName","!Surname","!Email","!OrganizationName"]
	SBtab_header = SBtabHeaderTemplate.substitute(TableID="curator",TableType="Curator",TableName="Curators")
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
else:
	print("SKIPPED: No curators found")

# <annotation>
#       <rdf:RDF>
#         <rdf:Description rdf:about="#24338838_de8b_4c0b_a8c6_fc2e8b6a3234">
#           <dc:creator>
#             <rdf:Bag>
#               <rdf:li rdf:about="lenov" rdf:parseType