from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from chronosmesh.events.event import Event


class WindowStrategy(ABC):
    """Abstract base class for windowing strategies."""

    def __init__(self):
        self.windows: Dict[str, List[Event]] = {}

    @abstractmethod
    def add_event(self, event: Event) -> List[str]:
        """Add event to appropriate windows. Returns list of window keys."""
        pass

    def get_window_events(self, key: str) -> List[Event]:
        """Get events for a specific window."""
        return self.windows.get(key, [])

    def get_all_windows(self) -> Dict[str, List[Event]]:
        """Get all active windows."""
        return self.windows

    @abstractmethod
    def expire_windows(self, current_time_ms: float) -> List[str]:
        """Expire old windows based on current time. Returns keys of expired windows."""
        pass


class TumblingWindow(WindowStrategy):
    """Fixed-size non-overlapping tumbling window."""

    def __init__(self, window_size_ms: float):
        super().__init__()
        self.window_size_ms = window_size_ms

    def add_event(self, event: Event) -> List[str]:
        window_idx = int(event.timestamp_ms // self.window_size_ms)
        key = f"tumb_{window_idx}"
        if key not in self.windows:
            self.windows[key] = []
        self.windows[key].append(event)
        return [key]

    def expire_windows(self, current_time_ms: float) -> List[str]:
        expired = []
        current_idx = int(current_time_ms // self.window_size_ms)
        for key in list(self.windows.keys()):
            idx = int(key.split("_")[1])
            if idx < current_idx:
                expired.append(key)
                del self.windows[key]
        return expired


class SlidingWindow(WindowStrategy):
    """Overlapping sliding window."""

    def __init__(self, window_size_ms: float, slide_ms: float):
        super().__init__()
        self.window_size_ms = window_size_ms
        self.slide_ms = slide_ms

    def add_event(self, event: Event) -> List[str]:
        keys = []
        ts = event.timestamp_ms
        first_window_idx = int((ts - self.window_size_ms) // self.slide_ms) + 1
        last_window_idx = int(ts // self.slide_ms)
        
        for idx in range(first_window_idx, last_window_idx + 1):
            window_start = idx * self.slide_ms
            window_end = window_start + self.window_size_ms
            if window_start <= ts < window_end:
                key = f"slide_{idx}"
                if key not in self.windows:
                    self.windows[key] = []
                self.windows[key].append(event)
                keys.append(key)
        return keys

    def expire_windows(self, current_time_ms: float) -> List[str]:
        expired = []
        for key in list(self.windows.keys()):
            idx = int(key.split("_")[1])
            window_end = (idx * self.slide_ms) + self.window_size_ms
            if window_end <= current_time_ms:
                expired.append(key)
                del self.windows[key]
        return expired


class SessionWindow(WindowStrategy):
    """Gap-based session window grouped by trace_id."""

    def __init__(self, gap_ms: float):
        super().__init__()
        self.gap_ms = gap_ms
        self.last_seen: Dict[str, float] = {}

    def add_event(self, event: Event) -> List[str]:
        trace_id = event.trace_id
        ts = event.timestamp_ms
        
        if trace_id in self.last_seen:
            if ts - self.last_seen[trace_id] > self.gap_ms:
                # new session
                self.windows[trace_id] = []
        else:
            if trace_id not in self.windows:
                self.windows[trace_id] = []
                
        self.windows[trace_id].append(event)
        self.last_seen[trace_id] = max(ts, self.last_seen.get(trace_id, 0))
        return [trace_id]

    def expire_windows(self, current_time_ms: float) -> List[str]:
        expired = []
        for trace_id, last_ts in list(self.last_seen.items()):
            if current_time_ms - last_ts > self.gap_ms:
                expired.append(trace_id)
                if trace_id in self.windows:
                    del self.windows[trace_id]
                del self.last_seen[trace_id]
        return expired
