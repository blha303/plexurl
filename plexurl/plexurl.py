#!/usr/bin/env python
from __future__ import print_function
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexUser
from plexapi.exceptions import NotFound
from plexapi.video import Show

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

def get_terminal_size(width=80, height=25, fd=1):
    """ Gets current terminal size

    :param width: Default width to return if all other methods fail
    :param height: Default height to return if all other methods fail
    :param fd: File descriptor to open (1 = stdout)
    :returns: tuple(columns:int, rows:int)
    """
    try:
        import fcntl, termios, struct
        wh = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))[::-1]
    except:
        try:
            wh = (os.environ['COLUMNS'], os.environ['LINES'])
        except:
            wh = (25, 80)
    return wh

def print_multicolumn(alist):
    """Formats a list into columns to fit on screen. Similar to `ls`. From http://is.gd/6dwsuA (daniweb snippet, search for func name)

    :param alist: list of data to print into columns

    >>> print_multicolumn(["a", "aa", "aaa", "aaaa"])
      a   aa   aaa   aaaa
    """
    ncols = get_terminal_size(80, 20)[0] // max(len(a) for a in alist)
    try:
        nrows = - ((-len(alist)) // ncols)
        ncols = - ((-len(alist)) // nrows)
    except ZeroDivisionError:
        print("\n".join(alist))
        return
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

def truncate(text, chars=30, ending="..."):
    """ Truncates text longer than CHARS chars

    :param text: text to truncate
    :type text: str
    :param chars: maximum length of text
    :param ending: string to attach to the end after truncation
    :returns: truncated text with ending
    """

    return text if len(text) < 30 else text[:25] + "..."

def choose(options, q):
    """ Displays multi-column interface, with a prompt if terminal is interactive

    :param options: list of string options
    :param q: prompt message
    """

    if len(options) == 1:
        info("Selecting {}...".format(options[0]))
        return options[0]
    print_multicolumn(options)
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
    username = username if username else os.environ.get("PLEX_USERNAME", None) or prompt("Plex username: ")
    password = password if password else os.environ.get("PLEX_PASSWORD", None) or getpass("Plex password: ")
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

    try:
        return server.library.section("Movies").get(movie)
    except NotFound:
        results = server.library.section("Movies").search(movie)
        if results:
            return server.library.section("Movies").get(choose(results, "Select a movie: "))
        else:
            info("No results")
            return 50

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

    try:
        show = show if type(show) is Show else server.library.section("TV Shows").get(show)
    except NotFound:
        results = server.library.section("TV Shows").search(show)
        if results:
            show = server.library.section("TV Shows").get(choose(results, "Select a show: "))
        else:
            info("No results")
            return 50
    epcheck = re.match("S(\d+?)E(\d+)", episode)
    if epcheck:
        return show.seasons()[int(epcheck.group(1))].episodes()[int(epcheck.group(2))]
    try:
        return show.episode(episode)
    except NotFound:
        results = ["S{}E{} {}".format(ep.parentIndex.zfill(2), ep.index.zfill(2), truncate(ep.title)) for ep in show.episodes() if episode in ep.title]
        if results:
            return lookup_episode(server, show, choose(results, "Select an episode: "))
        else:
            info("No results")
            return 50

def main_movie(server, args):
    """ Convenience function for printing movie stream url

    :param server: Server object from get_server()
    :type server: plexapi.server.PlexServer
    :param args: argparse.ArgumentParser().parse_args object
    :returns: Return code
    """

    if args.name:
        print(lookup_movie(server, args.name).getStreamUrl())
    else:
        selection = choose(["{}".format(movie.title) for movie in server.library.section("Movies").all()], "Select a movie: ")
        if selection:
            print(lookup_movie(server, selection).getStreamUrl())

def main_show(server, args):
    """ Convenience function for printing show names

    :param server: Server object from get_server()
    :type server: plexapi.server.PlexServer
    :param args: argparse.ArgumentParser().parse_args object
    :returns: Return code
    """

    if args.name:
        main_episode(server, args.name, args.episode)
    else:
        selection = choose(["{}".format(show.title) for show in server.library.section("TV Shows").all()], "Select a show: ")
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
    :returns: Return code
    """

    if episode:
        print(lookup_episode(server, show, episode).getStreamUrl())
    else:
        selection = choose(["S{}E{} {}".format(ep.parentIndex.zfill(2), ep.index.zfill(2), truncate(ep.title)) for ep in server.library.section("TV Shows").get(show).episodes()], "Select an episode: ")
        if selection:
            print(lookup_episode(server, show, selection).getStreamUrl(videoResolution=args.resolution))

def main():
    parser = argparse.ArgumentParser(prog="plexurl")
    parser.add_argument("-m", "--movie", help="Specify movie.", action="store_true")
    parser.add_argument("-s", "--show", help="Specify show.", action="store_true")
    parser.add_argument("--name", help="Name of movie or show. Use with -m or -s respectively. Omit to produce listing")
    parser.add_argument("-e", "--episode", help="Specify episode. Get list of episodes by specifying show. Supports either full episode name (which may conflict) or SnnEnn (i.e S12E34)")
    parser.add_argument("-S", "--server", help="Specify server. Defaults to {} $PLEX_SERVER".format(DEFAULT_URI), default=os.environ.get("PLEX_SERVER", DEFAULT_URI))
    parser.add_argument("-u", "--username", help="Specify username. Used for Plex authentication. $PLEX_USERNAME", default=os.environ.get("PLEX_USERNAME", None))
    parser.add_argument("-p", "--password", help="Specify password. Provided for convenience only, preferred method is to omit this and enter password at the prompt. $PLEX_PASSWORD", default=os.environ.get("PLEX_PASSWORD", None))
    parser.add_argument("--servername", help="Specify server name. Used with -u above, for Plex authentication. $PLEX_SERVERNAME", default=os.environ.get("PLEX_SERVERNAME", None))
    parser.add_argument("-r", "--resolution", help="Specify resolution. Should be of format WIDTHxHEIGHT. Defaults to 1280x720, or Plex's default")
    args = parser.parse_args()
    try:
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
    except KeyboardInterrupt:
        info("\nAborting.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
