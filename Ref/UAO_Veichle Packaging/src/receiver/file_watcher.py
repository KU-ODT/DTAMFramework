"""
Mission Dispatch System — File Watcher

inbox/ 디렉토리를 감시하여 새로운 .json 파일이 생성되면
Dispatcher로 전달한다.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Thread
from typing import Optional, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, DirCreatedEvent

from src.dispatcher.dispatcher import Dispatcher
from src.dispatcher.models import DispatchResult
from src.validator.errors import ValidationReport

logger = logging.getLogger(__name__)


class MissionFileHandler(FileSystemEventHandler):
    """
    inbox/ 폴더에 .json 파일이 생기면 Dispatcher로 전달하는 핸들러.
    """

    def __init__(self, dispatcher: Dispatcher):
        super().__init__()
        self._dispatcher = dispatcher

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent):
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix.lower() != ".json":
            return

        logger.info("New mission file detected: %s", path.name)

        try:
            # 파일 쓰기 완료 대기 (짧은 딜레이)
            time.sleep(0.5)

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 단건/배치 처리
            if isinstance(data, dict):
                result = self._dispatcher.process_single(data)
                self._log_result(path.name, [result])
            elif isinstance(data, list):
                results = self._dispatcher.process_batch(data)
                self._log_result(path.name, results)
            else:
                logger.error("File %s: payload is not a JSON object or array.", path.name)

            # 처리 완료된 파일을 processed 폴더로 이동
            processed_dir = path.parent / "processed"
            processed_dir.mkdir(exist_ok=True)
            dest = processed_dir / path.name
            path.rename(dest)
            logger.info("Moved %s → processed/", path.name)

        except json.JSONDecodeError as e:
            logger.error("File %s: invalid JSON — %s", path.name, e)
        except Exception as e:
            logger.error("File %s: processing error — %s", path.name, e)

    @staticmethod
    def _log_result(filename: str, results: list):
        for r in results:
            if isinstance(r, DispatchResult):
                logger.info(
                    "  [%s] FP%d → %s (QUEUED)",
                    filename, r.flight_plan_number, r.aircraft_id,
                )
            elif isinstance(r, ValidationReport):
                logger.warning(
                    "  [%s] FP%s — REJECTED (%d errors)",
                    filename,
                    r.flight_plan_number or "?",
                    r.error_count,
                )


class FileWatcher:
    """
    inbox/ 디렉토리를 감시하는 워처.

    start()로 백그라운드 스레드에서 감시를 시작하고,
    stop()으로 중지한다.
    """

    def __init__(self, inbox_path: str | Path, dispatcher: Dispatcher):
        self._inbox = Path(inbox_path)
        self._inbox.mkdir(parents=True, exist_ok=True)
        self._handler = MissionFileHandler(dispatcher)
        self._observer: Optional[Any] = None

    def start(self) -> None:
        """비동기 감시 시작 (백그라운드 스레드)"""
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._inbox), recursive=False)
        self._observer.start()
        logger.info("File watcher started: monitoring %s", self._inbox)

    def stop(self) -> None:
        """감시 중지"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("File watcher stopped")

    @property
    def inbox_path(self) -> Path:
        return self._inbox
