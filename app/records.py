from flask import Blueprint, render_template, redirect, url_for, request, flash
from . import db
from .models import Taxonomy, TaxonomyRank, Authority, DataSource, ConservationStatus, TaxonomyConservationStatus, ConservationList, ConservationEntry
import csv
import requests
from datetime import datetime
from sqlalchemy.exc import IntegrityError

GBIF_get = "https://api.gbif.org/v2/species/match" #api

checklistKey = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

#helper functions

#--------------------------------------------------------------------------------------------------------Database---------------------------------------------------------------------------------
#check if taxa rank is in db, if not add it
def validate_rank(rank):
    if not rank:
        return None
    
    cleaned_rank = rank.strip().lower()
    
    with db.session.no_autoflush:
        db_rank_name = TaxonomyRank.query.filter_by(taxonomy_rank_name=cleaned_rank).first()

        if db_rank_name:
            return db_rank_name

        db_rank_name = TaxonomyRank(taxonomy_rank_name=cleaned_rank)
        db.session.add(db_rank_name)

        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return TaxonomyRank.query.filter_by(taxonomy_rank_name= cleaned_rank).first()

    return db_rank_name
    
#add authority if doesnt exist already
def add_authority(authority):
    if not authority:
        return None
    
    cleaned_authority = authority.strip()
    
    db_authority_name = Authority.query.filter_by(authority_name = cleaned_authority).first()
    
    if db_authority_name is None:
        db_authority_name = Authority(authority_name = cleaned_authority)
        db.session.add(db_authority_name)
        db.session.flush()
        
    return db_authority_name

#add data source if doesnt exist already
def add_data_source(data_source):
    if not data_source:
        return None
    
    cleaned_data_source = data_source.strip()
    
    db_data_source = DataSource.query.filter_by(data_source_name = cleaned_data_source).first()
    
    if db_data_source is None:
        db_data_source = DataSource(data_source_name = cleaned_data_source)
        db.session.add(db_data_source)
        db.session.flush()
        
    return db_data_source    

    
#run the gbif match v2 api, kingdom is optional but used to narrow down names if there is uncertainty, https://requests.readthedocs.io/en/latest/user/quickstart/#json-response-content
def gbif_match_v2(scientific_name, kingdom = None):
    payload = {"scientificName": scientific_name, "checklistKey": checklistKey}

    if kingdom:
        payload["kingdom"] = kingdom

    r = requests.get(GBIF_get, params = payload)
    
    r.status_code
    r.raise_for_status()
    return r.json()


def get_taxonomy(gbif_key):
    return Taxonomy.query.filter_by(gbif_taxonomy_id = str(gbif_key)).first()


#upset (update/insert) a taxonomy 
def upsert_taxon(scientific_name, gbif_key, taxonomy_rank_name = None, parent_id = None):

    rank = validate_rank(taxonomy_rank_name)
    
    rank_id = rank.taxonomy_rank_id if rank else None

    taxon = get_taxonomy(gbif_key)

    if taxon is None:
        taxon = Taxonomy(
            scientific_name = scientific_name,
            gbif_taxonomy_id = str(gbif_key),
            gbif_taxonomy_url = f"https://www.gbif.org/species/{gbif_key}",
            taxonomy_rank_id = rank_id,
            parent_id = parent_id
        )
        db.session.add(taxon)

        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()

            # fetch the existing one instead
            taxon = get_taxonomy(gbif_key)
    else:
        taxon.scientific_name = scientific_name
        taxon.gbif_taxonomy_id = str(gbif_key)
        taxon.gbif_taxonomy_url = f"https://www.gbif.org/species/{gbif_key}"
        taxon.taxonomy_rank_id = rank_id
        taxon.parent_id = parent_id
        db.session.flush()

    return taxon


#add authority, data_source and vernacular name if they exist to a data entry
def add_extra_data_to_node(taxon, vernacular_name = None, authority_name = None, data_source_name = None):
    #add vernacular name if exists
    if vernacular_name:
        taxon.vernacular_name = vernacular_name.strip()

    authority = add_authority(authority_name) if authority_name else None
    data_source = add_data_source(data_source_name) if data_source_name else None

    #add rank id if auth exists
    if authority:
        taxon.authority_id = authority.authority_id
    else:
        None
        
    #add data source id if exists
    if data_source:
        taxon.data_source_id = data_source.data_source_id
    else:
        None

    return taxon

#https://techdocs.gbif.org/en/openapi/v1/species#/Searching%20names/matchNames API with json return
#build the taxonomy database
def build_taxonomy(api_response, vernacular_name = None, authority_name = None, data_source_name = None):
    #get usage from api
    usage = api_response.get("usage")

    if not usage:
        return None

    #local variable for the parent
    local_parent = None

    for node in api_response.get("classification", []): #upsert each node from the classification given by the api into the database and remember the parent
        current_classification = upsert_taxon(
            scientific_name = node["name"],
            gbif_key = str(node["key"]),
            taxonomy_rank_name = node.get("rank"),
            parent_id = local_parent.taxonomy_id if local_parent else None
        )
        
        local_parent = current_classification

    #upsert the searched taxon, i.e. the last node in the chain of heirarchies and the searched scientific name
    final_node = upsert_taxon(
        scientific_name = usage.get("canonicalName") or usage.get("name"), #get name
        gbif_key = str(usage["key"]),
        taxonomy_rank_name = usage.get("rank"),
        parent_id = local_parent.taxonomy_id if local_parent else None
    )

    final_node = add_extra_data_to_node(final_node, vernacular_name = vernacular_name, authority_name = authority_name, data_source_name = data_source_name) #upsert extra data into the node

    return final_node


def import_csv(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        unmatched_gbif = [] #entry not found on backbone
        reader = csv.DictReader(f) #read the csv

        for row in reader:
            scientific_name = (row.get("scientific_name") or "").strip()
            vernacular_name = (row.get("Vernacular name") or "").strip() or None #if none then None
            authority_name = (row.get("Authority") or "").strip() or None #if none then None
            data_source_name = (row.get("Data source") or "").strip() or None #if none then None
            kingdom = (row.get("Kingdom") or "").strip() or None #if none then None
            
            #skip if no scientific name
            if not scientific_name:
                continue

            try:
                api_response = gbif_match_v2(scientific_name, kingdom = kingdom)
                diagnostics = api_response.get("diagnostics", {})
                
                match_type = diagnostics.get("matchType") #get the type of match done

                if match_type == "NONE": #failed to find
                    #print(f"No match: {scientific_name}")
                    #add to unmatched_gbif list
                    unmatched_gbif.append({
                        "scientific_name": scientific_name,
                        "vernacular_name": vernacular_name,
                        "authority_name": authority_name,
                        "data_source_name": data_source_name,
                        "kingdom": kingdom,
                        "match_type": match_type
                    })
                    continue
                    
                #validation
                """
                if match_type == "HIGHERRANK": #higher rank than species
                    print(f"Imported higher rank {scientific_name} -> "
                          f"{node.scientific_name} "
                          f"(GBIF {node.gbif_taxonomy_id})"
                          )
                """    
                    
                node = build_taxonomy(api_response, vernacular_name = vernacular_name, authority_name = authority_name, data_source_name = data_source_name)

                
                if node:
                    update_taxon_conservation(node)
                #validation
                """
                    print(
                        f"Imported {scientific_name} -> "
                        f"{node.scientific_name} "
                        f"(GBIF {node.gbif_taxonomy_id})"
                    )
                """
                
                db.session.commit()
                
            #errors, api fail
            except requests.HTTPError as e:
                db.session.rollback()
                print(f"HTTP error for {scientific_name}: {e}")

            except Exception as e:
                db.session.rollback()
                print(f"Error processing {scientific_name}: {e}")
                
            
        
        if unmatched_gbif != []:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") #timestamp for failed records csv in year month day hour min sec
            
            
            filename = f"unmatched_records_{timestamp}.csv"

            #create a csv with all unmatched records for review
            with open(filename, "w", newline="", encoding="utf-8") as f:    
                writer = csv.DictWriter(f, fieldnames = [
                    "scientific_name",
                    "vernacular_name",
                    "authority_name",
                    "data_source_name",
                    "kingdom",
                    "match_type"])
                writer.writeheader()
                writer.writerows(unmatched_gbif)

    db.session.commit()
    
    
    
#--------------------------------------------------------------Conservation List-----------------------------------------------------------------------------------------------

#check if there is a link to the conservation list
#add to import from csv
def refresh_taxonomy_protection(taxonomy):
    sensitive = db.session.query(TaxonomyConservationStatus).join(ConservationStatus).filter(TaxonomyConservationStatus.taxonomy_id == taxonomy.taxonomy_id, ConservationStatus.is_sensitive == True).first() is not None

    taxonomy.is_protected = sensitive

    
    
def add_conservation_status(conservation_list, status_name, is_sensitive = False):
    status = ConservationStatus.query.filter_by(conservation_list_id = conservation_list.conservation_list_id, conservation_status= status_name).first()

    if status is None:
        status = ConservationStatus(
            conservation_status = status_name,
            conservation_list_id = conservation_list.conservation_list_id,
            is_sensitive = is_sensitive
        )
        db.session.add(status)
        db.session.flush()
        
    else:
        status.is_sensitive = is_sensitive

    return status
    
    
def add_taxon_to_conservation_status(taxonomy, conservation_status):
    db.session.add(
        TaxonomyConservationStatus(
            taxonomy_id=taxonomy.taxonomy_id,
            conservation_status_id=conservation_status.conservation_status_id
        )
    )

    
def add_conservation_list(list_name):
    conservation_list = ConservationList.query.filter_by(conservation_list_name = list_name.strip()).first()

    if conservation_list is None:
        conservation_list = ConservationList(
            conservation_list_name=list_name.strip()
        )
        db.session.add(conservation_list)
        db.session.flush()

    return conservation_list
    
#to get the taxonomy from the conservation list
def get_taxonomy_by_scientific_name(scientific_name):
    if not scientific_name:
        return None

    cleaned_name = scientific_name.strip()
    return Taxonomy.query.filter(db.func.lower(Taxonomy.scientific_name) == cleaned_name.lower()).first() #make all lower case for matching
    
#default status rules for SBL is_sensitive
SBL_Status_Rules = {
    "Conservation action needed": True,
    "Avoid negative impacts": True,
    "Watching brief only": False,
    "Legally protected species": True,
    "S1 - on UKBAP list": True,
    "S2 - Internatnl. Obligation": True,
    "S3 - Rare in the UK (<16 10km sqs)": True,
    "S4 - <6 Scottish 10km sqs": True,
    "S5 - >25% Scottish Decline": True,
    "S6a - Endemic to Scotland": True,
    "S6b - endemic sub-species/ race": True,
}

#same threat values as jncc, normalises to uppercase
def normalise_threatened_value(value):
    if not value:
        return None

    cleaned = value.strip().upper()

    allowed = {"EX", "EW", "RE", "CR", "CR(PE)", "EN", "VU", "NT", "LC", "DD", "NE", "NA"}
    if cleaned in allowed:
        return cleaned

    return None
 

#import sbl from given dataset 
def import_sbl_csv(csv_path, list_name ="SBL"):
    conservation_list = add_conservation_list(list_name)
    gbif_cache = {} #cache to save time storing the taxon and gbif_key 

    with open(csv_path, newline ="", encoding = "utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            scientific_name = (row.get("Scientific Name") or "").strip()

            #dont allow useless checks
            if not scientific_name:
                continue

            if scientific_name in gbif_cache:
                taxon, gbif_key = gbif_cache[scientific_name]
            else:
                taxon, gbif_key = gbif_conservation_helper(scientific_name)
                gbif_cache[scientific_name] = (taxon, gbif_key)

            #flags, yes is any input, no is blank
            for status_name, is_sensitive in SBL_Status_Rules.items():
                input = (row.get(status_name) or "").strip()

                if input:
                    status = add_conservation_status(
                        conservation_list,
                        status_name,
                        is_sensitive = is_sensitive
                    )

                    #add to list of conservation entries
                    add_conservation_entry(
                        scientific_name = scientific_name,
                        conservation_list = conservation_list,
                        conservation_status = status,
                        taxonomy = taxon,
                        gbif_taxonomy_id = gbif_key
                    )

                    if taxon is not None:
                        add_taxon_to_conservation_status(taxon, status)

            #threatened species value
            threatened_value = normalise_threatened_value(row.get("Threatened species"))

            if threatened_value:
                threatened_status = add_conservation_status(
                    conservation_list,
                    f"Threatened species - {threatened_value}", #signify that its sbl and not jncc
                    is_sensitive = threatened_value in {"CR", "EN", "VU", "EX"}
                )
                
                add_conservation_entry(
                        scientific_name = scientific_name,
                        conservation_list = conservation_list,
                        conservation_status = threatened_status,
                        taxonomy = taxon,
                        gbif_taxonomy_id = gbif_key
                    )
                    
                    
                if taxon is not None:
                    add_taxon_to_conservation_status(taxon, threatened_status)
              
              #change -  refresh outside of loop
            if taxon is not None:
                refresh_taxonomy_protection(taxon)

    db.session.commit()
    
 
#store the raw conservation list entries 
def add_conservation_entry(scientific_name, conservation_list, conservation_status, taxonomy = None, gbif_taxonomy_id = None):
    entry = ConservationEntry(
        scientific_name = scientific_name.strip(),
        gbif_taxonomy_id =str(gbif_taxonomy_id).strip() if gbif_taxonomy_id else None,
        conservation_list_id = conservation_list.conservation_list_id,
        conservation_status_id = conservation_status.conservation_status_id,
        taxonomy_id = taxonomy.taxonomy_id if taxonomy else None
    )
    
    db.session.add(entry)
    
    
    return entry
    
    
#used when importing taxonomy data from csv
def update_taxon_conservation(taxon):
    pending_entries = ConservationEntry.query.filter(ConservationEntry.taxonomy_id.is_(None), ConservationEntry.gbif_taxonomy_id == taxon.gbif_taxonomy_id).all()

    for entry in pending_entries:
        entry.taxonomy_id = taxon.taxonomy_id

        link = TaxonomyConservationStatus.query.filter_by(taxonomy_id =taxon.taxonomy_id, conservation_status_id = entry.conservation_status_id).first()

        if link is None:
            db.session.add(
                TaxonomyConservationStatus(
                    taxonomy_id = taxon.taxonomy_id,
                    conservation_status_id =entry.conservation_status_id
                )
            )

    refresh_taxonomy_protection(taxon)
    


# broader red-list categories for GB + Global lists with default status rules, does not include birds
JNCC_Status_Rules = {
    "EX": True,
    "EW": True,
    "RE": True,
    "CR": True,
    "CR(PE)": True,
    "EN": True,
    "VU": True,
    "NT": False,
    "LC": False,
    "DD": False,
    "NE": False,
    "NA": False,
    "INSU": False,
    "R": True,
    "INDE": False,
}

def normalise_jncc_values(value):
    #some are values in the jncc list are actually 2 values seperated by a coma
    if value is None:
        return []

    cleaned = str(value).strip().upper()

    if not cleaned:
        return []

    parts = [p.strip() for p in cleaned.split(",")]

    allowed = {"EX", "EW", "RE", "CR", "CR(PE)", "EN", "VU", "NT", "LC", "DD", "NE", "NA", "INSU", "R", "INDE"}

    return [p for p in parts if p in allowed]
    
    

def import_jncc_csv(csv_path):
    #columns to check, aren't doing birds currently
    gb_list = add_conservation_list("JNCC GB Red List")
    global_list = add_conservation_list("JNCC Global Red List")
    #caches
    gbif_cache = {} #cache to save time storing the taxon and gbif_key 
    status_cache = {}
    link_cache = set()
    #cache the updated is_sensitive (in theory should be able to change in admin dashboard
    sensitive_status_cache = { 
        (status.conservation_list_id, status.conservation_status): status.is_sensitive
        for status in ConservationStatus.query.filter(
            ConservationStatus.conservation_list_id.in_([gb_list.conservation_list_id, global_list.conservation_list_id])).all()
    }
    
    with open(csv_path, newline = "", encoding = "utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            scientific_name = (row.get("Recommended taxon name") or "").strip()
            #check - slow upload speed
            print(f"Uploading: {scientific_name}")

            
            #dont allow useless checks
            if not scientific_name:
                continue
    
            if scientific_name in gbif_cache:
                taxon, gbif_key = gbif_cache[scientific_name]
            else:
                taxon, gbif_key = gbif_conservation_helper(scientific_name)
                gbif_cache[scientific_name] = (taxon, gbif_key)
                
            row_is_sensitive = False    

            #UK redlist
            gb_statuses = normalise_jncc_values(row.get("GB Red list"))
            for status_name in set(gb_statuses):
                key = (gb_list.conservation_list_id, status_name)

                if key in status_cache:
                    status = status_cache[key]
                else:
                    is_sensitive = sensitive_status_cache.get(key, JNCC_Status_Rules.get(status_name, False))
                    
                    status = add_conservation_status(
                        conservation_list = gb_list,
                        status_name = status_name,
                        is_sensitive = is_sensitive
                    )
                    
                    status_cache[key] = status
                    sensitive_status_cache[key] = status.is_sensitive


                add_conservation_entry(
                    scientific_name = scientific_name,
                    conservation_list = gb_list,
                    conservation_status = status,
                    taxonomy = taxon,
                    gbif_taxonomy_id = gbif_key
                )
                
                if sensitive_status_cache.get(key, False):
                    row_is_sensitive = True
                    
                if taxon is not None:
                    pair = (taxon.taxonomy_id, status.conservation_status_id)
                    if pair not in link_cache:
                        add_taxon_to_conservation_status(taxon, status)
                        link_cache.add(pair)

            #Global red list
            global_statuses = normalise_jncc_values(row.get("Global Red list status"))
            for status_name in set(global_statuses):
                key = (global_list.conservation_list_id, status_name)

                if key in status_cache:
                    status = status_cache[key]
                else:
                    is_sensitive = sensitive_status_cache.get(key, JNCC_Status_Rules.get(status_name, False))
                    
                    status = add_conservation_status(
                        conservation_list = global_list,
                        status_name = status_name,
                        is_sensitive = is_sensitive
                    )
                    
                    status_cache[key] = status
                    sensitive_status_cache[key] = status.is_sensitive

                add_conservation_entry(
                    scientific_name = scientific_name,
                    conservation_list = global_list,
                    conservation_status = status,
                    taxonomy = taxon,
                    gbif_taxonomy_id = gbif_key
                )
                
                if sensitive_status_cache.get(key, False):
                    row_is_sensitive = True

                if taxon is not None:
                    pair = (taxon.taxonomy_id, status.conservation_status_id)
                    if pair not in link_cache:
                        add_taxon_to_conservation_status(taxon, status)
                        link_cache.add(pair)
            
            #change -  refresh outside of loop
            if taxon is not None:
                taxon.is_protected = row_is_sensitive

    db.session.commit()

    
    
#use the gbif for the conservation lists, avoids issue where names are different
def gbif_conservation_helper(scientific_name, kingdom = None):
    api_response = gbif_match_v2(scientific_name, kingdom = kingdom)
    usage = api_response.get("usage")
    diagnostics = api_response.get("diagnostics", {})
    match_type = diagnostics.get("matchType")

    if not usage or match_type in {"NONE", "HIGHERRANK"}:
        return None, None

    gbif_key = str(usage["key"])
    taxon = Taxonomy.query.filter_by(gbif_taxonomy_id = gbif_key).first()
    
    return taxon, gbif_key