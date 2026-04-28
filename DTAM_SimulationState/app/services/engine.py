"""시뮬레이션 시간 관리 및 로직 제어 서비스."""
import logging
import threading
from typing import Optional

# dtam_client는 설치된 패키지이므로 이제 직접 import 가능
from dtam_client import DtamWsClient

logger = logging.getLogger("sim_state.engine")

class SimulationEngine:
    """시뮬레이션 시간 관리 및 0003 송신 엔진."""
    def __init__(self, hub):
        self.hub = hub
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    def start_clock(self):
        if self._running:
            return
        self._running = True
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._clock_loop, daemon=True)
        self._thread.start()
        logger.info("Simulation clock started (1Hz 0003 emitter)")

    def stop_clock(self):
        self._running = False
        self._stop_evt.set()
        if self._thread:
            self._thread.join()

    def _clock_loop(self):
        from datetime import datetime, timezone
        while not self._stop_evt.is_set():
            now = datetime.now(timezone.utc)
            iso_now = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
            payload = {
                "timestamp": iso_now,
                "simTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            # 서버 허브를 통해 전송 (0003의 대상은 MESSAGE_TABLE 또는 FORWARD_RULES 참조)
            # hub.push_to_role은 특정 역할에 보내는 것이므로, FORWARD_RULES를 참조하여 보냄
            from DTAM_CoreServer.app.model.message import FORWARD_RULES
            targets = FORWARD_RULES.get("0003", ["vehicle", "visual"])
            for t in targets:
                self.hub.push_to_role(t, "0003", payload)
                
            self._stop_evt.wait(1.0)
