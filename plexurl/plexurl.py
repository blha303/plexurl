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
    """Formats a list into columns to fit on screen. Similar to `ls`. From http://is.gd/6dwsuA (daniweb snippet, search for func name)

    :param alist: list of data to print into columns

    >>> print_multicolumn(["a", "aa", "aaa", "aaaa"])
      a   aa   aaa   aaaa
    """
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

def choose(q):
    """ Displays prompt only if program is run from interactive terminal

    :param q: Prompt message
    :returns: user response
    :rtype: str
    """

    if os.isatty(sys.stdout.fileno()):
        return prompt(q)

def info(*objs):
    """ Print message to stderr to avoid interfering with pipeline

    :param objs: passed through to print()
    """

    print(*objs, file=sys.stderr)

def prompt(*objs):
    """ Print input() prompt to stderr to avoid interfering with pipeline

    :param objs: passed through to input()
    """

    old_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        return input(*objs)
    finally:
        sys.stdout = old_stdout

def get_server(uri=DEFAULT_URI, username=None, password=None, servername=None):
    """ Get Plex server object for further processing.

    :param uri: Server URI. Expects "http://IP-ADDRESS:PORT", where IP-ADDRESS can be a hostname, and PORT is usually 32400
    :param username: Plex username. Needed if uri fails. User is prompted if parameter is not provided. $PLEX_USERNAME
    :param password: Plex password. Recommended practice is to leave this as None and respond to the prompt. $PLEX_PASSWORD
    :param servername: Server name. User is prompted with a list of servers available to their username if parameter is not provided
    :returns: Server object
    :rtype: plexapi.server.PlexServer
    """

    try:
        return PlexServer(uri)
    except NotFound:
        pass
    if not username and not password:
        info("Could not get server object, maybe you need to be authenticated?")
    username = username if username else os.environ.get("PLEX_USERNAME", None) or prompt("Username: ")
    password = password if password else os.environ.get("PLEX_PASSWORD", None) or getpass()
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
    """ Retrieves movie object from specified server.

    :param server: Plex server object, probably returned by get_server()
    :type server: plexapi.server.PlexServer
    :param movie: Movie name
    :type movie: str
    :returns: Movie object
    :rtype: plexapi.video.Movie
    """

    return server.library.section("Movies").get(movie)

def lookup_episode(server, show, episode):
    """ Retrieves episode object from specified server.

    :param server: Plex server object, probably returned by get_server()
    :type server: plexapi.server.PlexServer
    :param show: TV show name
    :type show: str
    :param episode: Episode name, or SnnEnn designation
    :type episode: str
    :returns: Episode object
    :rtype: plexapi.video.Episode
    """

    show = server.library.section("TV Shows").get(show)
    epcheck = re.match("S(\d+?)E(\d+)", episode)
    if epcheck:
        return show.seasons()[int(epcheck.group(1))].episodes()[int(epcheck.group(2))]
    return show.episode(episode)

def main_movie(server, args):
    """ Convenience function for printing movie stream url

    :param server: Server object from get_server()
    :type server: plexapi.server.PlexServer
    :param args: argparse.ArgumentParser().parse_args object
    """

    if args.name:
        print(lookup_movie(server, args.name).getStreamUrl())
    else:
        print_multicolumn([u"{}".format(movie.title) for movie in server.library.section("Movies").all()])
        selection = choose("Select a movie: ")
        if selection:
            print(lookup_movie(server, selection).getStreamUrl())

def main_show(server, args):
    """ Convenience function for printing show names

    :param server: Server object from get_server()
    :type server: plexapi.server.PlexServer
    :param args: argparse.ArgumentParser().parse_args object
    """

    if args.name:
        main_episode(server, args.name, args.episode)
    else:
        print_multicolumn([u"{}".format(show.title) for show in server.library.section("TV Shows").all()])
        selection = choose("Select a show: ")
        if selection:
            main_episode(server, selection, None)

def main_episode(server, show, episode):
    """ Convenience function for printing movie stream url

    :param server: Server object from get_server()
    :type server: plexapi.server.PlexServer
    :param show: TV show name
    :type show: str
    :param episode: Episode name, or SnnEnn designation
    :type episode: str
    """

    if episode:
        print(lookup_episode(server, show, episode).getStreamUrl())
    else:
        print_multicolumn([u"S{}E{} {}".format(ep.parentIndex.zfill(2), ep.index.zfill(2), ep.title if len(ep.title) < 30 else ep.title[:25] + "...") for ep in server.library.section("TV Shows").get(show).episodes()])
        selection = choose("Select an episode: ")
        if selection:
            print(lookup_episode(server, show, selection).getStreamUrl())

def main():
    parser = argparse.ArgumentParser(prog="plexurl")
    parser.add_argument("-m", "--movie", help="Specify movie.", action="store_true")
    parser.add_argument("-s", "--show", help="Specify show.", action="store_true")
    parser.add_argument("--name", help="Name of movie or show. Use with -m or -s respectively. Omit to produce listing")
    parser.add_argument("-e", "--episode", help="Specify episode. Get list of episodes by specifying show. Supports either full episode name (which may conflict) or SnnEnn (i.e S12E34)")
    parser.add_argument("-S", "--server", help="Specify server. Defaults to {} $PLEX_SERVER".format(DEFAULT_URI), default=DEFAULT_URI)
    parser.add_argument("-u", "--username", help="Specify username. Used for Plex authentication. $PLEX_USERNAME")
    parser.add_argument("-p", "--password", help="Specify password. Provided for convenience only, preferred method is to omit this and enter password at the prompt. $PLEX_PASSWORD")
    parser.add_argument("--servername", help="Specify server name. Used with -u above, for Plex authentication. $PLEX_SERVERNAME")
    args = parser.parse_args()
    server = get_server(args.server, username=args.username, password=args.password, servername=args.servername)
    if type(server) is not PlexServer:
        info("Aborting.")
        return server
    if args.movie:
        main_movie(server, args)
    elif args.show:
        main_show(server, args)
    else:
        info("You need to specify either -m or -s for movies or TV shows, respectively.")
        return 5

if __name__ == "__main__":
    sys.exit(main())
