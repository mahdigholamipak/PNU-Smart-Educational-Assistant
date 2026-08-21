"""Thread-safe LRU cache and single-flight coalescing primitives.

Used to avoid redundant Gemini API calls:

- :class:`LRUCache` — bounded in-memory cache for expensive results
  (embedding vectors, OCR text) keyed by a deterministic string hash.
- :class:`Singleflight` — coalesces concurrent calls with the *same* key into
  one shared execution so a burst of identical requests debounce to a single
  upstream API call (the followers simply wait on the leader's result).

Both are thread-safe and safe to share across all request threads.
"""

import threading
from collections import OrderedDict
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

# Sentinel for "missing" cache entries (avoids storing None ambiguously).
_MISSING = object()


class LRUCache(Generic[T]):
    """Bounded, thread-safe LRU cache.

    On access, entries are moved to the most-recently-used position; when the
    cache exceeds ``max_size``, the least-recently-used entry is evicted.
    """

    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max(1, int(max_size))
        self._data: OrderedDict[str, T] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        """Return the cached value for ``key``, or ``None`` if absent."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            return None

    def put(self, key: str, value: T) -> None:
        """Store ``value`` under ``key``, evicting the LRU entry if over budget."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        """Empty the cache (e.g. after admin updates models/keys)."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


class _Call:
    """Shared state for an in-flight single-flight call."""

    __slots__ = ("done", "result", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: object = _MISSING
        self.error: BaseException | None = None


class Singleflight:
    """Coalesce concurrent calls with the same key into one shared computation.

    First caller becomes the "leader" and runs ``fn``; any concurrent caller
    with the same key blocks on the shared :class:`_Call` event and receives
    the leader's result (or re-raises the leader's error). Duplicates never
    hit the upstream API.
    """

    def __init__(self) -> None:
        self._inflight: dict[str, _Call] = {}
        self._lock = threading.Lock()

    def execute(self, key: str, fn: Callable[[], T]) -> T:
        """Run ``fn`` once for ``key``; concurrent callers wait for the result."""
        with self._lock:
            call = self._inflight.get(key)
            if call is None:
                call = _Call()
                self._inflight[key] = call
                is_leader = True
            else:
                is_leader = False

        if not is_leader:
            # Follower: wait for the leader to finish, then share the outcome.
            call.done.wait()
            if call.error is not None:
                raise call.error
            return call.result  # type: ignore[return-value]

        try:
            call.result = fn()
        except BaseException as exc:
            call.error = exc
            raise
        finally:
            call.done.set()
            with self._lock:
                # Best-effort cleanup (the key cannot be re-added while the
                # leader is still running, so this pop is always the leader).
                self._inflight.pop(key, None)
        return call.result  # type: ignore[return-value]