#!/usr/bin/env python3

"""
The original version of this script created by
Nick Johnson <arachnid@notdot.net> and may be found here:
https://gist.github.com/Arachnid/c51b450b0c80eb246394aab5c867d666

Updates by Tom Cameron https://github.com/tomc603
"""

"""
The original version of this script created by
Nick Johnson <arachnid@notdot.net> and may be found here:
https://gist.github.com/Arachnid/c51b450b0c80eb246394aab5c867d666
"""

import argparse
import requests
import xml.etree.ElementTree as ET

from io import StringIO
from PyPDF2 import PdfFileReader, PdfFileWriter


parser = argparse.ArgumentParser(description='Build a PDF from a set of matching RFCs')
parser.add_argument('rfc', metavar='RFC', nargs='*')
parser.add_argument('prefix', metavar='FILENAME')
parser.add_argument('--include-updates', dest='include_updates', action='store_true', default=False, help='Transitively include RFCs updated by a target RFC')
parser.add_argument('--include-obsoletes', dest='include_obsoletes', action='store_true', default=False, help='Transitively include RFCs obsoleted by a target RFC')
parser.add_argument('--include-see-also', dest='include_see_also', action='store_true', default=False, help='Transitively include RFCs references by a target RFC')
parser.add_argument('--keyword', nargs='*', default=[], help='Include all RFCs with the specified keyword(s)')
parser.add_argument('--maxpages', default=1000, type=int, help='Maximum pages per volume')
parser.add_argument('--all', default=False, action='store_true', help='Include *all* RFCs')

namespaces = {'rfc': 'http://www.rfc-editor.org/rfc-index'}

def fetch_rfc_index():
    print("Fetching RFC index...")
    response = requests.get("http://ietf.org/rfc/rfc-index.xml")
    response.raise_for_status()
    print("Parsing RFC index...")
    xml = ET.fromstring(response.content)
    #xml = ET.parse('rfc-index.xml')

    ret = {}
    for node in xml.findall('rfc:rfc-entry', namespaces):
        obsoletes = node.find('rfc:obsoletes', namespaces)
        updates = node.find('rfc:updates', namespaces)
        seealso = node.find('rfc:see-also', namespaces)
        keywords = node.find('rfc:keywords', namespaces)
        ret[node.find('rfc:doc-id', namespaces).text] = {
            'updates': set(doc.text for doc in updates.findall('rfc:doc-id', namespaces)) if updates is not None else set(),
            'obsoletes': set(doc.text for doc in obsoletes.findall('rfc:doc-id', namespaces)) if obsoletes is not None else set(),
            'see_also': set(doc.text for doc in seealso.findall('rfc:doc-id', namespaces)) if seealso is not None else set(),
            'keywords': set(kw.text for kw in keywords.findall('rfc:kw', namespaces)) if keywords is not None else set(),
        }
    return ret


def rfcs_by_keyword(rfc_index, keywords):
    ret = set()
    for docid, info in rfc_index.items():
        if 'keywords' in info and not info['keywords'].isdisjoint(keywords):
            ret.add(docid)
    return ret


def follow_references(rfc_index, rfcs, include_updates, include_obsoletes, include_see_also):
    ret = set()
    frontier = set(rfcs)
    while frontier:
        rfc = frontier.pop()
        ret.add(rfc)

        info = rfc_index[rfc]
        if include_updates:
            frontier.update(update for update in info['updates'] if update not in ret)
        if include_obsoletes:
            frontier.update(obsolete for obsolete in info['obsoletes'] if obsolete not in ret)
        if include_see_also:
            frontier.update(seealso for seealso in info['see_also'] if seealso not in ret)
    return ret


def get_doc(rfc):
    print("Adding %s..." % (rfc,))
    rfcnum = int(rfc[3:])
    response = requests.get("http://ietf.org/rfc/rfc%s.txt.pdf" % (rfcnum,))
    if response.status_code == 404:
        print("Could not add %s: No PDF version found." % (rfc,))
        return None
    response.raise_for_status()
    return PdfFileReader(StringIO(response.content))


def build_docs(rfcs, prefix, maxpages):
    writer = PdfFileWriter()
    pagenum = 0
    volume = 1
    for rfc in rfcs:
        reader = get_doc(rfc)
        if not reader: continue

        numpages = reader.getNumPages()
        if pagenum + numpages > maxpages:
            filename = '%s-%d.pdf' % (prefix, volume)
            print("Writing %s with %d pages" % (filename, pagenum))
            fh = open(filename, 'wb')
            writer.write(fh)
            fh.close()
            writer = PdfFileWriter()
            pagenum = 0
            volume += 1

        for n in range(numpages):
            writer.addPage(reader.getPage(n))
            pagenum += 1

    filename = '%s-%d.pdf' % (prefix, volume)
    print("Writing %s with %d pages" % (filename, pagenum))
    fh = open(filename, 'wb')
    writer.write(fh)
    fh.close()


def main(args):
    rfc_index = fetch_rfc_index()
    if args.all:
        rfcs = list(rfc_index.keys())
    else:
        rfcs = set('RFC'+ rfc for rfc in args.rfc)
        rfcs.update(rfcs_by_keyword(rfc_index, args.keyword))
        rfcs = follow_references(rfc_index, rfcs, args.include_updates, args.include_obsoletes, args.include_see_also)
    rfcs = sorted(rfcs)
    print("Found %d relevant RFCs." % (len(rfcs),))
    build_docs(rfcs, args.prefix, args.maxpages)


if __name__ == '__main__':
  main(parser.parse_args())
