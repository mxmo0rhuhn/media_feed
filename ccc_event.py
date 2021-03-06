#!/usr/bin/python3

import argparse
import base64
import os
import shutil
import sys
from xml.dom.minidom import parse

import urllib3

urllib3.disable_warnings()

DOWNLOADS_DIR = '/tmp'


def get_file(url):
    # name = url.rsplit('/', 1)[-1]
    # Easy and works
    name = str(base64.b64encode(bytes(url, "utf-8")), "utf-8")

    # Combine the name and the downloads directory to get the local filename
    filename = os.path.join(DOWNLOADS_DIR, name)

    # Download the file if it does not exist
    if not os.path.isfile(filename):
        if not quiet:
            sys.stderr.write("Downloading %s \n" % (url))
        with http.request('GET', url, preload_content=False) as r, open(filename, 'wb') as out_file:
            shutil.copyfileobj(r, out_file)

    return filename


# def find_talk(fahrplan, talk_name, media_url, response):
def find_talk(fahrplan, media, query):
    fahrplan_xml = parse(fahrplan)
    media_xml = parse(media)

    for fahrplan_node in fahrplan_xml.getElementsByTagName("title"):
        if str.upper(query) in str.upper(fahrplan_node.childNodes[0].data):
            sys.stderr.write("Found: %s \n" % str.upper(fahrplan_node.childNodes[0].data))
            title = fahrplan_node.childNodes[0].data

            #  Event
            par = fahrplan_node.parentNode
            event_id = par.getAttribute('id')

            try:
                sub = par.getElementsByTagName("subtitle")[0].childNodes[0].data
            except:
                sub = ""
                if not quiet:
                    sys.stderr.write("Element has no subtitle \n")

            try:
                speakers = ", ".join([speaker.childNodes[0].data for speaker in
                                      par.getElementsByTagName("persons")[0].getElementsByTagName("person")])

            except:
                speakers = ""
                if not quiet:
                    sys.stderr.write("Element has no speakers \n")

            try:
                desc = par.getElementsByTagName("description")[0].childNodes[0].data
            except:
                desc = None
                if not quiet:
                    sys.stderr.write("Element has no description \n")

            for media_node in media_xml.getElementsByTagName("title"):
                if str.upper(title) in str.upper(media_node.childNodes[0].data):

                    # media item
                    item = media_node.parentNode

                    try:
                        media_desc = item.getElementsByTagName("description")[0].childNodes[0].data
                    except:
                        media_desc = ""
                        if not quiet:
                            sys.stderr.write("Element has no media description \n")

                    try:
                        pubDate = item.getElementsByTagName("pubDate")[0].childNodes[0].data
                    except:
                        pubDate = ""
                        if not quiet:
                            sys.stderr.write("Element has no publication date \n")

                    try:
                        enclosure = item.getElementsByTagName("enclosure")[0]
                        media_url = enclosure.getAttribute("url")
                        media_type = enclosure.getAttribute("length")
                        media_length = enclosure.getAttribute("type")
                    except:
                        sys.stderr.write("Could not get media information \n")
                        exit()

                    print('')
                    print("  - title: \"%s\"" % (title))
                    print("    published: %s" % (pubDate))
                    print("    speakers: %s" % (speakers))
                    print("    subtitle: \"%s\"" % (sub))
                    print("    media_url: %s" % (media_url))
                    print("    media_type: %s" % (media_type))
                    print("    media_length: %s" % (media_length))
                    print("    web_url: %s%s%s " % (event_pattern_head, event_id, event_pattern_tail))
                    if long_desc and desc:
                        print_desc("{} {} ".format(desc, custom_comment))
                    else:
                        print_desc(media_desc + custom_comment)
                    return True
            sys.stderr.write("No media found for talk '%s' - aborting \n" % title)
            return False

    return False


def print_desc(desc):
    if desc:
        print("    description: >-")
        print("      %s " % (str.replace(desc, "\n", "\n       ")))
    else:
        print("    description: ")


################################################################################

args = sys.argv
http = urllib3.PoolManager()

parser = argparse.ArgumentParser(description='Search for talks in CCC events and generate media yml syntax for it.')

parser.add_argument('query', metavar='<query string>', type=str, help='The search string')
parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='Disable optional output')
parser.add_argument('-l', '--long', dest='long_desc', action='store_true',
                    help='Print long description from Fahrplan instead of short descriptions from CCC media feed.')
parser.add_argument('-y', '--year', metavar='year', dest='year', type=str, default="2019",
                    help='Year to search (currently 2019, 2014, 2015 and 2016 are supported). Defaults to 2019.')
parser.add_argument('-c', '--comment', metavar='text', dest='custom_comment', type=str, default="",
                    help='Custom comment to add to the description.')

args = parser.parse_args()

query = args.query
quiet = args.quiet
long_desc = args.long_desc
year = args.year
custom_comment = args.custom_comment

# 36c3 specific:
podcat_feed = "https://media.ccc.de/podcast-hq.xml"
fahrplan_location = "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/schedule.xml"
event_pattern_head = "https://fahrplan.events.ccc.de/congress/2019/Fahrplan/events/"
event_pattern_tail = ".html"

if year == "2015":
    # 32c3 specific:
    podcat_feed = "https://media.ccc.de/c/32c3/podcast/mp4.xml"
    fahrplan_location = "https://events.ccc.de/congress/2015/Fahrplan/schedule.xml"
    event_pattern_head = "https://events.ccc.de/congress/2015/Fahrplan/events/"

elif year == "2014":
    # 31c3 specific:
    podcat_feed = "https://media.ccc.de/c/31c3/podcast/mp4.xml"
    fahrplan_location = "https://events.ccc.de/congress/2014/Fahrplan/schedule.xml"
    event_pattern_head = "https://events.ccc.de/congress/2014/Fahrplan/events/"

fahrplan = get_file(fahrplan_location)
media = get_file(podcat_feed)

if not find_talk(fahrplan, media, query):
    sys.stderr.write("no talk or media found for '%s'\n" % (query))
