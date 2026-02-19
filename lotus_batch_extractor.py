#!/usr/bin/env python3 
"""
LOTUS batch compound extractor for plant database.
Queries Wikidata SPARQL for compounds, references, DOIs, and titles.
"""

import csv
import time
import requests
from pathlib import Path
from SPARQLWrapper import SPARQLWrapper, JSON


def get_reference_metadata(qid: str) -> dict:
	"""Fetch DOI, title, and publication date from Wikidata API"""
	url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
	headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
	}
	try:
		response = requests.get(url, headers=headers, timeout=5)
		if response.status_code == 200:
			data = response.json()
			entity = data.get('entities', {}).get(qid, {})
			claims = entity.get('claims', {})

			# Get P356 (DOI)
			doi = ''
			doi_claims = claims.get('P356', [])
			if doi_claims:
				doi = doi_claims[0].get('mainsnak', {}).get('datavalue', {}).get('value', '')

			# Get P1476 (Title)
			title = ''
			title_claims = claims.get('P1476', [])
			if title_claims:
				title_val = title_claims[0].get('mainsnak', {}).get('datavalue', {}).get('value', {})
				if isinstance(title_val, dict):
					title = title_val.get('text', '')
				else:
					title = str(title_val)

			# Get P577 (Publication date)
			pub_date = ''
			pub_date_claims = claims.get('P577', [])
			if pub_date_claims:
				pub_date = pub_date_claims[0].get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', '')

			return {
				'doi': doi,
				'title': title,
				'pub_date': pub_date
			}
		else:
			return {'doi': '', 'title': '', 'pub_date': ''}
	except Exception as e:
		return {'doi': '', 'title': '', 'pub_date': ''}


def query_lotus_for_plant(plant_name: str, sparql) -> list[dict]:
	"""
	Query LOTUS (Wikidata) for compounds of a specific plant.
	Returns list of compound entries with reference QIDs.
	"""
	query = f"""
	SELECT ?compound ?compoundLabel ?smiles ?inchikey ?reference WHERE {{
	  ?taxon wdt:P225 "{plant_name}" .
	  ?compound p:P703 ?statement .
	  ?statement ps:P703 ?taxon .
	  OPTIONAL {{ ?statement prov:wasDerivedFrom ?refnode .
	             ?refnode pr:P248 ?reference . }}
	  OPTIONAL {{ ?compound wdt:P233 ?smiles . }}
	  OPTIONAL {{ ?compound wdt:P235 ?inchikey . }}
	  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
	}}
	ORDER BY ?compoundLabel
	"""

	try:
		sparql.setQuery(query)
		sparql.setReturnFormat(JSON)
		results = sparql.query().convert()

		all_compounds = []
		for binding in results["results"]["bindings"]:
			row = {}
			for var in results["head"]["vars"]:
				row[var] = binding.get(var, {}).get('value', '')

			# If we have a reference QID, fetch its metadata
			if row.get('reference'):
				ref_qid = row['reference'].split('/')[-1]  # Extract QID from URL
				metadata = get_reference_metadata(ref_qid)
				row.update(metadata)

			all_compounds.append(row)

		return all_compounds
	except Exception as e:
		print(f"Error querying '{plant_name}': {e}")
		return []


def format_output(plant_num: str, plant_name: str, compounds: list[dict]) -> str:
	"""Format compound data into readable output."""
	output = []
	output.append(f"\n{'='*80}")
	output.append(f"PLANT #{plant_num}: {plant_name}")
	output.append(f"{'='*80}")

	if not compounds:
		output.append("No compounds found in LOTUS database.")
		return "\n".join(output)

	# Group compounds by title + DOI to deduplicate references
	seen = {}
	for compound in compounds:
		comp_name = compound.get('compoundLabel', 'Unknown')
		doi = compound.get('doi', '')
		title = compound.get('title', '')

		# Create a unique key based on compound + reference
		key = (comp_name, doi, title)
		if key not in seen:
			seen[key] = compound

	for idx, (key, compound) in enumerate(seen.items(), 1):
		comp_name = key[0]
		output.append(f"\nCompound {idx}: {comp_name}")

		# Add compound identifiers if available
		smiles = compound.get('smiles', '')
		inchikey = compound.get('inchikey', '')
		if smiles:
			output.append(f"  SMILES: {smiles}")
		if inchikey:
			output.append(f"  InChIKey: {inchikey}")

		# Add reference information
		doi = compound.get('doi', '')
		title = compound.get('title', '')
		pub_date = compound.get('pub_date', '')

		if doi or title:
			if title:
				output.append(f"  Title: {title}")
			if doi:
				output.append(f"  DOI: {doi}")
			if pub_date:
				# Clean up the Wikidata date format
				clean_date = pub_date.replace('+', '').split('T')[0]
				output.append(f"  Published: {clean_date}")

	return "\n".join(output)


def main():
	csv_path = Path("C:/Users/S4xon/Downloads/browser-use/plants.csv")
	output_path = Path("C:/Users/S4xon/Downloads/browser-use/lotus_compounds_output.txt")

	if not csv_path.exists():
		print(f"Error: {csv_path} not found!")
		return

	# Initialize SPARQL endpoint
	sparql = SPARQLWrapper("https://query.wikidata.org/sparql")

	# Read plants
	plants = []
	with open(csv_path, 'r', encoding='utf-8') as f:
		reader = csv.reader(f)
		for row in reader:
			if len(row) >= 2:
				plant_num = row[0].strip()
				plant_name = row[1].strip()
				plants.append((plant_num, plant_name))

	print(f"Loaded {len(plants)} plants from {csv_path}")
	print(f"Querying LOTUS database... (this may take a while)")
	print(f"Output will be written to {output_path}")
	print("-" * 80)

	total_compounds = 0

	# Check if file exists to resume or start fresh
	is_new_file = not output_path.exists()
	mode = 'w' if is_new_file else 'a'

	# Find which plants are already completed
	completed_plants = set()
	if not is_new_file:
		with open(output_path, 'r', encoding='utf-8') as f:
			for line in f:
				if line.startswith('PLANT #'):
					try:
						plant_num_str = line.split('#')[1].split(':')[0].strip()
						completed_plants.add(plant_num_str)
					except:
						pass
		if completed_plants:
			print(f"Found {len(completed_plants)} completed plants, resuming...")

	with open(output_path, mode, encoding='utf-8') as out_file:
		if is_new_file:
			out_file.write("LOTUS BATCH COMPOUND EXTRACTION RESULTS\n")
			out_file.write(f"Total Plants: {len(plants)}\n")
			out_file.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

		for idx, (plant_num, plant_name) in enumerate(plants, 1):
			if plant_num in completed_plants:
				continue

			print(f"[{idx}/{len(plants)}] Processing: {plant_name}")

			# Handle multiple synonyms (separated by "or")
			names_to_query = [n.strip() for n in plant_name.split(" or ")]

			all_compounds = []
			for name in names_to_query:
				compounds = query_lotus_for_plant(name, sparql)
				all_compounds.extend(compounds)
				time.sleep(0.3)  # Rate limiting for SPARQL queries

			# Format and write results
			formatted = format_output(plant_num, plant_name, all_compounds)
			out_file.write(formatted)
			out_file.write("\n")

			total_compounds += len(set(c.get('compoundLabel', '') for c in all_compounds))
			time.sleep(0.2)  # Small delay between plants

	print("-" * 80)
	print(f"[OK] Complete! Results written to {output_path}")
	print(f"Total unique compounds found: {total_compounds}")


if __name__ == "__main__":
	main()
