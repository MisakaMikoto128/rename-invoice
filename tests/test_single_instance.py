import socket
from unittest.mock import MagicMock, patch
import pytest

from accounting import single_instance


def _mock_socket_class(behaviors: list):
    """behaviors: list of dicts per call to socket.socket().
    Each dict can have 'bind_error' (OSError) and/or 'connect_error' (OSError).
    """
    calls = iter(behaviors)
    instances = []

    def factory(*args, **kwargs):
        m = MagicMock()
        b = next(calls, {})
        if b.get("bind_error"):
            m.bind.side_effect = b["bind_error"]
        if b.get("connect_error"):
            m.connect.side_effect = b["connect_error"]
        instances.append(m)
        return m

    return factory, instances


def test_acquire_when_port_free_returns_listening_sock():
    factory, instances = _mock_socket_class([{}])  # bind succeeds
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    assert sock is not None
    assert sock is instances[0]
    instances[0].bind.assert_called_once_with(("127.0.0.1", single_instance.PORT))


def test_acquire_when_port_held_by_peer_sends_show_and_returns_none():
    factory, instances = _mock_socket_class([
        {"bind_error": OSError(10048, "in use")},  # first socket: bind fails
        {},                                         # second socket: connect succeeds
    ])
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    assert sock is None
    instances[1].connect.assert_called_once_with(("127.0.0.1", single_instance.PORT))
    instances[1].sendall.assert_called_once_with(b"SHOW\n")


def test_acquire_when_port_blocked_by_other_process_degrades():
    factory, instances = _mock_socket_class([
        {"bind_error": OSError(10048, "in use")},  # first: bind 47821 fails
        {"connect_error": OSError("refused")},      # second: connect fails
        {},                                         # third: bind port 0 succeeds
    ])
    with patch.object(socket, "socket", side_effect=factory):
        sock = single_instance.acquire_or_signal_existing()
    # Single-instance protection degrades, but returns a usable sock
    assert sock is instances[2]
    instances[2].bind.assert_called_once_with(("127.0.0.1", 0))


def test_serve_show_requests_calls_on_show_on_recv():
    on_show = MagicMock()
    sock = MagicMock()
    conn = MagicMock()
    conn.recv.return_value = b"SHOW\n"
    # accept() returns conn once, then raises OSError so listener exits
    sock.accept.side_effect = [(conn, ("127.0.0.1", 12345)), OSError("stopped")]

    single_instance._listener_loop(sock, on_show)  # synchronous, no thread

    on_show.assert_called_once()
    conn.close.assert_called_once()


def test_serve_show_requests_ignores_non_show_payload():
    on_show = MagicMock()
    sock = MagicMock()
    conn = MagicMock()
    conn.recv.return_value = b"PING\n"
    sock.accept.side_effect = [(conn, ("127.0.0.1", 12345)), OSError("stopped")]

    single_instance._listener_loop(sock, on_show)

    on_show.assert_not_called()
