import urllib, urllib2
import re
from indra.databases import uniprot_client

nextprot_url = 'http://www.nextprot.org/db/term/'

def get_family_members(nextprot_id):
    url = nextprot_url + 'FA-' + nextprot_id
    res = urllib2.urlopen(url)
    html = res.read()
    match = re.match(r'(.*)http://www.uniprot.org/uniprot/\?query=family:([^"]*)"',\
             html, re.DOTALL|re.MULTILINE)
    family_name = match.groups()[1]
    gene_names = uniprot_client.get_family_members(family_name)
    return gene_names
