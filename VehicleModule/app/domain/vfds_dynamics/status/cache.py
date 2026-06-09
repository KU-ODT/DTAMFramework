import threading
from typing import Dict, Optional
from .models import AircraftStatus

class StatusCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._aircrafts: Dict[str, AircraftStatus] = {}

    def update_status(self, aircraft_id: str, status: AircraftStatus):
        with self._lock:
            self._aircrafts[aircraft_id] = status

    def get_status(self, aircraft_id: str) -> Optional[AircraftStatus]:
        with self._lock:
            return self._aircrafts.get(aircraft_id)

    def get_all(self) -> Dict[str, AircraftStatus]:
        with self._lock:
            return dict(self._aircrafts)

# 전역 싱글톤 캐시
status_cache = StatusCache()
