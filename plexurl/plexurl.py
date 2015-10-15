#!/usr/bin/env python
from __future__ import print_function
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexUser
from plexapi.exceptions import NotFound

from prettytable import PrettyTable, NONE

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
from getpass import getpass
from socket import gethostbyname
from pydoc import pager

import sys
import os
import re
import shutil
import argparse

DEFAULT_URI = "http://127.0.0.1:32400"

input = raw_input if hasattr(__builtins__, 'raw_input') else input

def print_multicolumn(alist):
    ncols = shutil.get_terminal_size((80, 20)).columns // max(len(a) for a in alist)
    nrows = - ((-len(alist)) // ncols)
    ncols = - ((-len(alist)) // nrows)
    t = PrettyTable([str(x) for x in range(ncols)])
    t.header = False
    t.align = 'l'
    t.hrules = NONE
    t.vrules = NONE
    chunks = [alist[i:i+nrows] for i in range(0, len(alist), nrows)]
    chunks[-1].extend('' for i in range(nrows - len(chunks[-1])))
    chunks = zip(*chunks)
    for c in chunks:
        t.add_row(c)
    print(t)

def fmtcols(l):
    maxlen = max(len(i) for i in l)
    if len(l) % 2 != 0:
        l.append(" ")
    split = int(len(l)/2)
    l1 = l[0:split]
    l2 = l[split:]
    o = []
    for key, value in zip(l1,l2):
        o.append(u"{0:<{2}s} {1}".format(key, value, maxlen))
    return u"\n".join(o)

def choose(q):
    if os.isatty(sys.stdout.fileno()):
        return prompt(q)

def info(*objs):
    print(*objs, file=sys.stderr)

def prompt(*objs):
    old_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        return input(*objs)
    finally:
        sys.stdout = old_stdout

def get_server(uri=DEFAULT_URI, username=None, password=None, servername=None):
    try:
        return PlexServer(uri)
    except NotFound:
        pass
    if not username and not password:
        info("Could not get server object, maybe you need to be authenticated?")
    username = prompt("Username: ") if not username else username
    password = getpass() if not password else password
    user = MyPlexUser.signin(username, password)
    if not servername:
        info("Servers: " + ", ".join(a.name for a in user.resources()))
        servername = prompt("Please enter server name (or specify with --servername). If you don't know it, press enter and I'll (very slowly!) search for the correct server: ") or None
    if servername:
        return user.getResource(servername).connect()
    else:
        info("OK, beginning the search process.")
    # necessary to match correct server
    if uri.count(":") >= 2:
        ip = ":".join(urlparse(uri).netloc.split(":")[:-1])
    else:
        ip = urlparse(uri).netloc
    info("Getting IP for {}".format(ip))
    ip = gethostbyname(ip)
    info("Got IP from hostname: {}".format(ip) if ip not in uri else "Searching for {}".format(ip))
    for srv in user.resources():
        try:
            server = srv.connect()
            if ip in server.baseuri:
                info("Found server: {}".format(srv.name))
                return server
        except NotFound:
            info("Couldn't connect to {}".format(srv.name))
    info("Couldn't find server in your user's server list.")
    return 10

def lookup_movie(server, movie):
    return server.library.section("Movies").get(movie)

def lookup_episode(server, show, episode):
    show = server.library.section("TV Shows").get(show)
    epcheck = re.match("S(\d+?)E(\d+)", episode)
    if epcheck:
        return show.seasons()[int(epcheck.group(1))].episodes()[int(epcheck.group(2))]
    return show.episode(episode)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--movie", help="Specify movie.", action="store_true")
    parser.add_argument("-s", "--show", help="Specify show.", action="store_true")
    parser.add_argument("--name", help="Name of movie or show. Use with -m or -s respectively. Omit to produce listing")
    parser.add_argument("-e", "--episode", help="Specify episode. Get list of episodes by specifying show. Supports either full episode name (which may conflict) or SnnEnn (i.e S12E34)")
    parser.add_argument("-S", "--server", help="Specify server. Defaults to {}".format(DEFAULT_URI), default=DEFAULT_URI)
    parser.add_argument("-u", "--username", help="Specify username. Used for Plex authentication")
    parser.add_argument("-p", "--password", help="Specify password. Provided for convenience only, preferred method is to omit this and enter password at the prompt")
    parser.add_argument("--servername", help="Specify server name. Used with -u above, for Plex authentication.")
    args = parser.parse_args()
    server = get_server(args.server, username=args.username, password=args.password, servername=args.servername)
    if type(server) is not PlexServer:
        info("Aborting.")
        return server
    if args.movie:
        if args.name:
            print(lookup_movie(server, args.name).getStreamUrl())
        else:
            print_multicolumn([u"{}".format(movie.title) for movie in server.library.section("Movies").all()])
            selection = choose("Select a movie: ")
            if selection:
                print(lookup_movie(server, selection).getStreamUrl())
    elif args.show:
        def get_ep(show, ep):
            if ep:
                print(lookup_episode(server, show, ep).getStreamUrl())
            else:
                print_multicolumn([u"S{}E{} {}".format(ep.parentIndex.zfill(2), ep.index.zfill(2), ep.title) for ep in server.library.section("TV Shows").get(show).episodes()])
                selection = choose("Select an episode: ")
                if selection:
                    print(lookup_episode(server, show, selection).getStreamUrl())
        if args.name:
            get_ep(args.name, args.episode)
        else:
            print_multicolumn([u"{}".format(show.title) for show in server.library.section("TV Shows").all()])
            selection = choose("Select a show: ")
            if selection:
                get_ep(selection, None)
    else:
        info("You need to specify either -m or -s for movies or TV shows, respectively.")
        return 5

if __name__ == "__main__":
    sys.exit(main())
