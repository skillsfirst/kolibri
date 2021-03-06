import atexit
import logging
import multiprocessing
import os
import platform

import cherrypy
import requests
from django.conf import settings
from django.core.management import call_command
from kolibri.content.utils import paths

from .system import kill_pid, pid_exists

logger = logging.getLogger(__name__)

# Status codes for kolibri
STATUS_RUNNING = 0
STATUS_STOPPED = 1
STATUS_STARTING_UP = 4
STATUS_NOT_RESPONDING = 5
STATUS_FAILED_TO_START = 6
STATUS_UNCLEAN_SHUTDOWN = 7
STATUS_UNKNOWN_INSTANCE = 8
STATUS_SERVER_CONFIGURATION_ERROR = 9
STATUS_PID_FILE_READ_ERROR = 99
STATUS_PID_FILE_INVALID = 100
STATUS_UNKNOWN = 101

# Used to store PID and port number (both in foreground and daemon mode)
PID_FILE = os.path.join(
    os.environ['KOLIBRI_HOME'],
    "server.pid"
)

# Used to PID, port during certain exclusive startup process, before we fork
# to daemon mode
STARTUP_LOCK = os.path.join(
    os.environ['KOLIBRI_HOME'],
    "server.lock"
)

# This is a special file with daemon activity. It logs ALL stderr output, some
# might not have made it to the log file!
DAEMON_LOG = os.path.join(
    os.environ['KOLIBRI_HOME'],
    "server.log"
)

# Currently non-configurable until we know how to properly handle this
LISTEN_ADDRESS = "0.0.0.0"


class NotRunning(Exception):
    """
    Raised when server was expected to run, but didn't. Contains a status
    code explaining why.
    """

    def __init__(self, status_code):
        self.status_code = status_code
        super(NotRunning, self).__init__()


def start_background_workers():
    p = multiprocessing.Process(target=call_command, args=("qcluster", ))

    # note: atexit normally only runs when python exits normally, aka doesn't
    # exit through a signal. However, this function gets run because cherrypy
    # catches all the various signals, and runs the atexit callbacks.
    atexit.register(p.terminate)

    p.start()


def start(port=8080):
    """
    Starts the server.

    :param: port: Port number (default: 8080)
    """

    # start the qcluster process
    # don't run on windows; we don't run a full cluster there.
    if platform.system() != "Windows":
        start_background_workers()

    # Write the new PID
    with open(PID_FILE, 'w') as f:
        f.write("%d\n%d" % (os.getpid(), port))

    def rm_pid_file():
        os.unlink(PID_FILE)

    atexit.register(rm_pid_file)

    run_server(port=port)


def stop(pid=None, force=False):
    """
    Stops the kalite server, either from PID or through a management command

    :param args: List of options to parse to the django management command
    :raises: NotRunning
    """

    if not force:
        # Kill the KA lite server
        kill_pid(pid)
    else:
        try:
            pid, __ = _read_pid_file(PID_FILE)
            kill_pid(pid)
        except ValueError:
            logger.error("Could not find PID in .pid file\n")
        except OSError:
            logger.error("Could not read .pid file\n")

    # TODO: Check that server has in fact been killed, otherwise we should
    # raise an error...

    # Finally, remove the PID file
    os.unlink(PID_FILE)


def run_server(port):

    # Mount the application
    from kolibri.deployment.default.wsgi import application
    cherrypy.tree.graft(application, "/")

    serve_static_dir(settings.STATIC_ROOT, settings.STATIC_URL)
    serve_static_dir(
        settings.CONTENT_DATABASE_DIR, paths.get_content_database_url("/")
    )
    serve_static_dir(
        settings.CONTENT_STORAGE_DIR, paths.get_content_storage_url("/")
    )

    # Unsubscribe the default server
    cherrypy.server.unsubscribe()

    # Instantiate a new server object
    server = cherrypy._cpserver.Server()

    # Configure the server
    server.socket_host = LISTEN_ADDRESS
    server.socket_port = port
    server.thread_pool = 30

    # Subscribe this server
    server.subscribe()

    # Start the server engine (Option 1 *and* 2)
    cherrypy.engine.start()
    cherrypy.engine.block()


def serve_static_dir(root, url):

    static_handler = cherrypy.tools.staticdir.handler(
        section="/",
        dir=os.path.split(root)[1],
        root=os.path.abspath(os.path.split(root)[0])
    )
    cherrypy.tree.mount(static_handler, url)


def _read_pid_file(filename):
    """
    Reads a pid file and returns the contents. PID files have 1 or 2 lines;
     - first line is always the pid
     - optional second line is the port the server is listening on.

    :param filename: Path of PID to read
    :return: (pid, port): with the PID in the file and the port number
                          if it exists. If the port number doesn't exist, then
                          port is None.
    """
    try:
        pid, port = open(filename, "r").readlines()
        pid, port = int(pid), int(port)
    except ValueError:
        # The file only had one line
        try:
            pid, port = int(open(filename, "r").read()), None
        except ValueError:
            pid, port = None, None
    return pid, port


def _write_pid_file(filename, port):
    """
    Writes a PID file in the format Kolibri parses

    :param: filename: Path of file to write
    :param: port: Listening port number which the server is assigned
    """

    with open(filename, 'w') as f:
        f.write("%d\n%d" % (os.getpid(), port))


def get_status():  # noqa: max-complexity=16
    """
    Tries to get the PID of a running server.

    The behavior is also quite redundant given that `kalite start` should
    always create a PID file, and if its been started directly with the
    runserver command, then its up to the developer to know what's happening.
    :returns: (PID, address, port), where address is not currently detected in
              a valid way because it's not configurable, and we might be
              listening on several IPs.
    :raises: NotRunning
    """

    # There is no PID file (created by server daemon)
    if not os.path.isfile(PID_FILE):
        # Is there a startup lock?
        if os.path.isfile(STARTUP_LOCK):
            try:
                pid, port = _read_pid_file(STARTUP_LOCK)
                # Does the PID in there still exist?
                if pid_exists(pid):
                    raise NotRunning(STATUS_STARTING_UP)
                # It's dead so assuming the startup went badly
                else:
                    raise NotRunning(STATUS_FAILED_TO_START)
            # Couldn't parse to int
            except TypeError:
                raise NotRunning(STATUS_STOPPED)
        raise NotRunning(STATUS_STOPPED)  # Stopped

    # PID file exists, check if it is running
    try:
        pid, port = _read_pid_file(PID_FILE)
    except (ValueError, OSError):
        raise NotRunning(STATUS_PID_FILE_INVALID)  # Invalid PID file

    # PID file exists, but process is dead
    if not pid_exists(pid):
        if os.path.isfile(STARTUP_LOCK):
            raise NotRunning(STATUS_FAILED_TO_START)  # Failed to start
        raise NotRunning(STATUS_UNCLEAN_SHUTDOWN)  # Unclean shutdown

    listen_port = port

    try:
        # Timeout is 3 seconds, we don't want the status command to be slow
        # TODO: Using 127.0.0.1 is a hardcode default from KA Lite, it could
        # be configurable
        # TODO: HTTP might not be the protocol if server has SSL
        response = requests.get(
            "http://{}:{}".format("127.0.0.1", listen_port),
            timeout=3
        )
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        raise NotRunning(STATUS_NOT_RESPONDING)
    except (requests.exceptions.RequestException):
        if os.path.isfile(STARTUP_LOCK):
            raise NotRunning(STATUS_STARTING_UP)  # Starting up
        raise NotRunning(STATUS_UNCLEAN_SHUTDOWN)

    if response.status_code == 404:
        raise NotRunning(STATUS_UNKNOWN_INSTANCE)  # Unknown HTTP server

    if response.status_code != 200:
        # Probably a mis-configured kolibri
        raise NotRunning(STATUS_SERVER_CONFIGURATION_ERROR)

    return pid, LISTEN_ADDRESS, listen_port  # Correct PID !

    # We don't detect this at present:
    # Could be detected because we fetch the PID directly via HTTP, but this
    # is dumb because kolibri could be running in a worker pool with different
    # PID from the PID file..
    # raise NotRunning(STATUS_UNKNOWN_INSTANCE)
    # This would be the fallback when we know it's not running, but we can't
    # give a proper reason...
    # raise NotRunning(STATUS_UNKNOW)


def get_urls():
    """
    This is a stub, see: https://github.com/learningequality/kolibri/issues/1595
    """
    try:
        __, __, port = get_status()
        urls = []
        for addr in [LISTEN_ADDRESS]:
            urls.append("http://{}:{}/".format(addr, port))
        return STATUS_RUNNING, urls
    except NotRunning as e:
        return e.status_code, []
