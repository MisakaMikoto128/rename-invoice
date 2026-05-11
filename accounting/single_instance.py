"""Single-instance enforcement via a 127.0.0.1 socket on a fixed port.

The port serves two purposes: it is the mutex (only one process can bind),
and it is the IPC channel (second-launch sends "SHOW" to make the first
process bring its window forward). No new dependencies, no lock files.
"""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

PORT = 47821  # local loopback fixed port


def acquire_or_signal_existing() -> Optional[socket.socket]:
    """Try to bind 127.0.0.1:PORT.

    Returns:
        - bind succeeds → bound socket (caller will listen + serve_show_requests)
        - bind fails but connect succeeds → sends b"SHOW\\n", returns None (caller sys.exit)
        - bind fails and connect also fails → logs warning, binds random port, returns it
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORT))
        return sock
    except OSError:
        try:
            sock.close()
        except OSError:
            pass

        peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            peer.connect(("127.0.0.1", PORT))
            peer.sendall(b"SHOW\n")
            peer.close()
            return None
        except OSError as e:
            log.warning("single-instance: port %d held by non-peer (%s); "
                        "degrading to random port", PORT, e)
            try:
                peer.close()
            except OSError:
                pass
            degraded = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            degraded.bind(("127.0.0.1", 0))
            return degraded


def serve_show_requests(sock: socket.socket, on_show: Callable[[], None]) -> None:
    """Listen on `sock` in a daemon thread. Calls on_show() per "SHOW" line received."""
    sock.listen(5)
    t = threading.Thread(target=_listener_loop, args=(sock, on_show),
                         daemon=True, name="single-instance-listener")
    t.start()


def _listener_loop(sock: socket.socket, on_show: Callable[[], None]) -> None:
    """Internal: accept loop. Exits on socket close / OSError from accept()."""
    while True:
        try:
            conn, _addr = sock.accept()
        except OSError:
            return  # socket closed
        try:
            data = conn.recv(1024)
            if data and b"SHOW" in data:
                on_show()
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
