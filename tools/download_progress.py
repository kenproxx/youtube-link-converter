"""Verified-build download transport with visible progress and bounded waits."""
import http.client
import ssl
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class _Reporter:
    def __init__(self, stream):
        self.stream = stream
        self.interactive = bool(getattr(stream, 'isatty', lambda: False)())
        self.width = 0

    def show(self, text, final=False):
        if self.interactive:
            self.stream.write('\r' + text.ljust(self.width) + ('\n' if final else ''))
            self.stream.flush()
            self.width = 0 if final else len(text)
        else:
            print(text, file=self.stream, flush=True)


def _retryable(exc):
    if isinstance(exc, HTTPError):
        return exc.code in (408, 429) or exc.code >= 500
    if isinstance(exc, ssl.SSLCertVerificationError):
        return False
    if isinstance(exc, URLError) and isinstance(exc.reason, ssl.SSLCertVerificationError):
        return False
    return isinstance(exc, (OSError, URLError, http.client.IncompleteRead))


def fetch_bytes(url, label, *, stream=None, interval=1.0, socket_timeout=15,
                idle_timeout=30, deadline=600, attempts=2):
    """Read in chunks; main-thread heartbeat also runs during DNS/connect/read waits.

    No filesystem writes or TLS overrides. Caller must validate downloaded artifacts.
    Daemon workers stop at the next chunk when cancelled; they never log or install.
    """
    if interval <= 0 or attempts < 1 or min(socket_timeout, idle_timeout, deadline) <= 0:
        raise ValueError('Download intervals, timeouts and attempts must be positive')
    reporter = _Reporter(sys.stdout if stream is None else stream)
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        state = {'received': 0, 'total': None, 'last': started, 'connected': False,
                 'error': None, 'chunks': []}
        lock, done, cancel = threading.Lock(), threading.Event(), threading.Event()

        def worker(state=state, lock=lock, done=done, cancel=cancel):
            try:
                with urlopen(url, timeout=socket_timeout) as response:
                    length = response.headers.get('Content-Length')
                    total = int(length) if length and length.isdigit() else None
                    with lock:
                        state.update(total=total if total and total > 0 else None,
                                     connected=True, last=time.monotonic())
                    read = getattr(response, 'read1', response.read)
                    while not cancel.is_set():
                        chunk = read(64 * 1024)
                        if not chunk:
                            break
                        with lock:
                            state['chunks'].append(chunk)
                            state['received'] += len(chunk)
                            state['last'] = time.monotonic()
                    if not cancel.is_set() and state['total'] is not None and state['received'] != state['total']:
                        raise OSError(f'Incomplete download: {state["received"]}/{state["total"]} bytes')
            except Exception as exc:
                state['error'] = exc
            finally:
                done.set()

        reporter.show(f'[{label}] Connecting / awaiting response... attempt {attempt}/{attempts} | elapsed 0s')
        threading.Thread(target=worker, daemon=True).start()
        try:
            while not done.wait(min(interval, idle_timeout, max(.001, deadline - (time.monotonic() - started)))):
                now = time.monotonic()
                with lock:
                    received, total, last, connected = (state[k] for k in ('received', 'total', 'last', 'connected'))
                elapsed, stalled = now - started, now - last
                if elapsed >= deadline:
                    raise TimeoutError(f'Download deadline reached after {elapsed:.0f}s')
                if stalled >= idle_timeout:
                    raise TimeoutError(f'No response/data for {stalled:.0f}s')
                if not connected:
                    status = 'Connecting / awaiting response...'
                else:
                    status = _metrics(received, total, elapsed)
                    if stalled >= 3:
                        status += f' | waiting for data {stalled:.0f}s'
                reporter.show(f'[{label}] {status} | elapsed {elapsed:.0f}s')
            if state['error'] is not None:
                raise state['error']
            elapsed = max(time.monotonic() - started, .001)
            if elapsed >= deadline:
                raise TimeoutError(f'Download deadline reached after {elapsed:.0f}s')
            reporter.show(f'[{label}] {_metrics(state["received"], state["total"], elapsed)} | download complete in {elapsed:.1f}s', final=True)
            return b''.join(state['chunks'])
        except Exception as exc:
            reporter.show(f'[{label}] Failed: {exc}', final=True)
            if attempt == attempts or not _retryable(exc):
                raise
            reporter.show(f'[{label}] Retrying with a new connection ({attempt + 1}/{attempts})...', final=True)
        finally:
            cancel.set()


def _metrics(received, total, elapsed):
    mib = 1024 * 1024
    speed = received / max(elapsed, .001)
    if total:
        remaining = max(0, total - received) / speed if speed else None
        eta = f'{remaining:.0f}s' if remaining is not None else 'waiting'
        return f'{received / total * 100:5.1f}% | {received / mib:.2f}/{total / mib:.2f} MiB | {speed / mib:.2f} MiB/s avg | ETA {eta}'
    return f'{received / mib:.2f} MiB | total size unknown | {speed / mib:.2f} MiB/s avg | ETA unknown'
