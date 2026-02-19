import json
import urllib.request
import urllib.parse
import time
import csv

def update_smiles_strict(input_json, output_json, max_compounds=50):
    """
    Updates SMILES to stereochemistry-aware versions from PubChem. 
    If not found in PubChem -> sets SMILES to empty string (flags for manual review).
    """
    
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    compounds = data['compounds'][:max_compounds]
    updated_count = 0
    emptied_count = 0
    
    for idx, entry in enumerate(compounds):
        name = entry.get('compound_name', '')
        inchikey = entry.get('inchikey', '')
        
        print(f"[{idx+1}/{len(compounds)}] {name[:40]}...")
        
        best_smiles = ''  # Start empty - must prove itself worthy
        
        # Try InChIKey first
        if inchikey:
            try:
                url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{inchikey}/property/IsomericSMILES/JSON"
                with urllib.request.urlopen(url, timeout=10) as response:
                    result = json.loads(response.read().decode())
                    smiles = result['PropertyTable']['Properties'][0]['SMILES']
                    
                    # Check if this has stereochemistry
                    if '@' in smiles or '/' in smiles or '\\' in smiles:
                        best_smiles = smiles
                        print(f"   ✅ Updated (with stereo)")
                    else:
                        # Flat from InChIKey, try name for stereo
                        if name:
                            try:
                                encoded_name = urllib.parse.quote(name)
                                url_name = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/property/IsomericSMILES/JSON"
                                with urllib.request.urlopen(url_name, timeout=10) as response2:
                                    result2 = json.loads(response2.read().decode())
                                    smiles2 = result2['PropertyTable']['Properties'][0]['SMILES']
                                    if '@' in smiles2 or '/' in smiles2 or '\\' in smiles2:
                                        best_smiles = smiles2
                                        print(f"   ✅ Updated (stereo via name)")
                                    else:
                                        best_smiles = smiles  # Flat but valid
                                        print(f"   ✅ Updated (flat)")
                            except:
                                best_smiles = smiles  # Flat but valid
                                print(f"   ✅ Updated (flat)")
                        else:
                            best_smiles = smiles  # Flat but valid
                            print(f"   ✅ Updated (flat)")
            except:
                # InChIKey failed, try name
                if name:
                    try:
                        encoded_name = urllib.parse.quote(name)
                        url_name = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/property/IsomericSMILES/JSON"
                        with urllib.request.urlopen(url_name, timeout=10) as response2:
                            result2 = json.loads(response2.read().decode())
                            smiles2 = result2['PropertyTable']['Properties'][0]['SMILES']
                            best_smiles = smiles2
                            print(f"   ✅ Updated (via name)")
                    except:
                        best_smiles = ''  # Failed both
                        print(f"   ❌ Not found - EMPTIED")
                        emptied_count += 1
                else:
                    best_smiles = ''
                    print(f"   ❌ Not found - EMPTIED")
                    emptied_count += 1
        else:
            # No InChIKey, try name only
            if name:
                try:
                    encoded_name = urllib.parse.quote(name)
                    url_name = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/property/IsomericSMILES/JSON"
                    with urllib.request.urlopen(url_name, timeout=10) as response2:
                        result2 = json.loads(response2.read().decode())
                        smiles2 = result2['PropertyTable']['Properties'][0]['SMILES']
                        best_smiles = smiles2
                        print(f"   ✅ Updated (via name)")
                except:
                    best_smiles = ''
                    print(f"   ❌ Not found - EMPTIED")
                    emptied_count += 1
            else:
                best_smiles = ''
                print(f"   ❌ Not found - EMPTIED")
                emptied_count += 1
        
        # Update smiles (empty string if not found)
        if best_smiles:
            entry['smiles'] = best_smiles
            updated_count += 1
        else:
            entry['smiles'] = ''  # Empty = needs manual attention
        
        time.sleep(0.2)
    
    # Save with exact same structure
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
	
	# ADD CSV EXPORT HERE (after the JSON save, before the final print)
    csv_file = output_json.replace('.json', '.csv')
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(['plant_number', 'plant_name', 'compound_name', 'molecular_weight', 
                        'logP', 'h_bond_donors', 'h_bond_acceptors', 'tpsa', 
                        'rotatable_bonds', 'rule_of_5_violations', 'drug_like_lipinski', 
                        'smiles', 'inchikey', 'doi'])
        # Data rows
        for entry in data['compounds'][:max_compounds]:
            p = entry.get('properties', {})
            writer.writerow([
                entry.get('plant_number', ''),
                entry.get('plant_name', ''),
                entry.get('compound_name', ''),
                p.get('molecular_weight', ''),
                p.get('logP', ''),
                p.get('h_bond_donors', ''),
                p.get('h_bond_acceptors', ''),
                p.get('tpsa', ''),
                p.get('rotatable_bonds', ''),
                p.get('rule_of_5_violations', ''),
                p.get('drug_like_lipinski', ''),
                entry.get('smiles', ''),
                entry.get('inchikey', ''),
                entry.get('doi', '')
            ])

    print(f"\n✅ Done.")
    print(f"   Updated with PubChem SMILES: {updated_count}")
    print(f"   Emptied (not found): {emptied_count}")
    print(f"   Total processed: {len(compounds)}")

if __name__ == "__main__":
    update_smiles_strict(
        'lotus_compounds_filtered.json',
        'lotus_compounds_final.json',
        max_compounds=2287
    )