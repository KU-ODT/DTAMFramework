"""UAM Flight Simulator — Async streaming runtime.

Provides an asyncio-based layer that drives the DynamicsEngine tick-by-tick,
streaming FlightTrajectoryPoint records at a configurable rate (default 10 Hz).

Key classes:
    ClockSource      — ABC for pacing simulation ticks.
    WallClockSource  — Real-time pacing via asyncio.sleep.
    ExternalClockSource — Paced by an external time feed.
    FreeRunClockSource  — As-fast-as-possible (batch / testing).
    FlightSession    — Manages one active flight's lifecycle.
    FlightStreamService — Top-level service: submit plans, subscribe to streams.

Usage:
    service = FlightStreamService(config)
    flight_id = await service.submit_plan(plan)
    async for point in service.subscribe(flight_id):
        print(point)
    await service.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from typing import (
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

from ..core.types import (
    FlightPlan,
    FlightState,
    FlightStatus,
    FlightTrajectoryPoint,
    SimulationConfig,
)
from ..core.flight_dynamics import DynamicsEngine
from ..core.path_builder import build_segment_profiles
from ..core.flight_profile import build_kinematics
from ..core.wind_model import WindModel

logger = logging.getLogger(__name__)


# ── Clock sources ──────────────────────────────────────────────

class ClockSource(ABC):
    """Abstract base for pacing simulation ticks."""

    @abstractmethod
    async def wait_next_tick(self) -> float:
        """Block until the next tick should fire.

        Returns the current time in seconds (interpretation is
        source-dependent).
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset clock state for a new run."""


class WallClockSource(ClockSource):
    """Real-time pacing — one simulation tick per ``tick_interval`` wall seconds."""

    def __init__(self, tick_interval: float = 0.1) -> None:
        self._interval = tick_interval
        self._next_time: Optional[float] = None

    def reset(self) -> None:
        self._next_time = None

    async def wait_next_tick(self) -> float:
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._next_time is None:
            self._next_time = now + self._interval
        else:
            delay = self._next_time - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_time += self._interval
            # Prevent drift accumulation: if we fell behind, skip forward
            actual_now = loop.time()
            if self._next_time < actual_now:
                self._next_time = actual_now + self._interval
        return loop.time()


class ExternalClockSource(ClockSource):
    """Paced by an external time feed.

    Call ``update(time_s)`` from outside to push the current time.
    ``wait_next_tick`` blocks until a new time is received.
    """

    def __init__(self, tick_interval: float = 0.1) -> None:
        self._tick_interval = tick_interval
        self._current_time = 0.0
        self._last_consumed = -1.0
        self._event = asyncio.Event()

    def reset(self) -> None:
        self._current_time = 0.0
        self._last_consumed = -1.0
        self._event.clear()

    async def update(self, time_s: float) -> None:
        """Push a new time value from an external source."""
        self._current_time = time_s
        self._event.set()

    async def wait_next_tick(self) -> float:
        while True:
            await self._event.wait()
            if self._current_time - self._last_consumed >= self._tick_interval:
                self._last_consumed = self._current_time
                self._event.clear()
                return self._current_time
            self._event.clear()


class FreeRunClockSource(ClockSource):
    """No pacing — runs as fast as the CPU allows.

    Useful for batch-equivalent mode or testing.
    """

    def __init__(self) -> None:
        self._t = 0.0

    def reset(self) -> None:
        self._t = 0.0

    async def wait_next_tick(self) -> float:
        self._t += 0.1  # nominal
        await asyncio.sleep(0)  # yield to event loop
        return self._t


# ── Flight session ─────────────────────────────────────────────

class FlightSession:
    """Manages one flight's simulation lifecycle.

    Created internally by ``FlightStreamService``.
    """

    def __init__(
        self,
        flight_id: str,
        plan: FlightPlan,
        engine: DynamicsEngine,
        clock: ClockSource,
    ) -> None:
        self.flight_id = flight_id
        self.plan = plan
        self.engine = engine
        self.clock = clock

        self.state = FlightState.PENDING
        self.current_point: Optional[FlightTrajectoryPoint] = None
        self._subscribers: List[asyncio.Queue[Optional[FlightTrajectoryPoint]]] = []
        self._task: Optional[asyncio.Task] = None

    # ── Subscriber management ──────────────────────────────────

    def add_subscriber(self) -> asyncio.Queue[Optional[FlightTrajectoryPoint]]:
        q: asyncio.Queue[Optional[FlightTrajectoryPoint]] = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def _broadcast(self, point: Optional[FlightTrajectoryPoint]) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(point)
            except asyncio.QueueFull:
                # Drop oldest to prevent backpressure stall
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(point)
                except asyncio.QueueFull:
                    pass

    # ── Run loop ───────────────────────────────────────────────

    async def run(self) -> None:
        """Main coroutine — drives the engine tick-by-tick."""
        self.state = FlightState.ACTIVE
        logger.info("Flight %s started (aircraft=%s)", self.flight_id, self.plan.aircraft_id)

        try:
            while not self.engine.is_finished:
                await self.clock.wait_next_tick()
                point = self.engine.tick()
                if point is None:
                    break
                self.current_point = point
                await self._broadcast(point)
        except asyncio.CancelledError:
            self.state = FlightState.CANCELLED
            logger.info("Flight %s cancelled", self.flight_id)
            raise
        else:
            self.state = FlightState.COMPLETED
            logger.info("Flight %s completed", self.flight_id)
        finally:
            # Sentinel to signal end-of-stream to subscribers
            await self._broadcast(None)

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run(), name=f"flight-{self.flight_id}")
        return self._task

    async def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> FlightStatus:
        return FlightStatus(
            flight_id=self.flight_id,
            aircraft_id=self.plan.aircraft_id,
            flight_plan_number=self.plan.flight_plan_number,
            state=self.state,
            current_point=self.current_point,
            elapsed_s=self.engine.current_time,
            total_duration_s=self.engine.total_time_s,
        )


# ── Stream service ─────────────────────────────────────────────

# Broadcast item: (flight_id, point_or_None)
_BroadcastItem = Tuple[str, Optional[FlightTrajectoryPoint]]


class FlightStreamService:
    """Top-level async service for managing multiple concurrent flights.

    Usage::

        service = FlightStreamService(config)
        fid = await service.submit_plan(plan)

        async for point in service.subscribe(fid):
            process(point)

        await service.shutdown()
    """

    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        clock_source: Optional[ClockSource] = None,
        wind_preset: str = "good",
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.config = config or SimulationConfig()
        self.clock = clock_source or WallClockSource(self.config.tick_s)
        self.wind_preset = wind_preset
        self.wind_seed = wind_seed
        self.month = month

        self._sessions: Dict[str, FlightSession] = {}
        self._all_subscribers: List[asyncio.Queue[Optional[_BroadcastItem]]] = []

        # Callback hook: called with (flight_id, point) for every point
        self.on_point: Optional[Callable[[str, FlightTrajectoryPoint], None]] = None

    # ── Plan submission ────────────────────────────────────────

    def _create_engine(self, plan: FlightPlan) -> DynamicsEngine:
        seg_profiles, proj = build_segment_profiles(plan, self.config)
        kinematics = build_kinematics(seg_profiles, self.config)

        parts = plan.departure.etot.split(":")
        start_hour = int(parts[0]) + int(parts[1]) / 60.0

        wind: Optional[WindModel] = None
        if self.config.wind_enabled:
            wind = WindModel(
                seed=self.wind_seed,
                time_speed=self.config.wind_time_speed,
                preset=self.wind_preset,
                start_local_hour=start_hour,
            )

        return DynamicsEngine(
            segments=seg_profiles,
            kinematics=kinematics,
            proj=proj,
            config=self.config,
            wind_model=wind,
            start_clock=plan.departure.etot,
            month=self.month,
        )

    async def submit_plan(self, plan: FlightPlan, flight_id: Optional[str] = None) -> str:
        """Accept a mission plan and start simulating.

        Returns the ``flight_id`` assigned to this flight.
        """
        fid = flight_id or f"{plan.aircraft_id}_{uuid.uuid4().hex[:8]}"
        engine = self._create_engine(plan)
        session = FlightSession(fid, plan, engine, self.clock)

        # Wire up global broadcast
        global_q = session.add_subscriber()
        asyncio.create_task(self._relay_to_global(fid, global_q))

        self._sessions[fid] = session
        session.start()
        logger.info("Submitted plan → flight_id=%s", fid)
        return fid

    async def _relay_to_global(
        self, flight_id: str, q: asyncio.Queue[Optional[FlightTrajectoryPoint]]
    ) -> None:
        """Relay points from a session into the global (all-flights) broadcast."""
        while True:
            point = await q.get()
            if point is not None and self.on_point:
                self.on_point(flight_id, point)
            item: Optional[_BroadcastItem] = (flight_id, point) if point is not None else None
            for gq in self._all_subscribers:
                try:
                    gq.put_nowait(item)
                except asyncio.QueueFull:
                    try:
                        gq.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        gq.put_nowait(item)
                    except asyncio.QueueFull:
                        pass
            if point is None:
                break

    # ── Subscriptions ──────────────────────────────────────────

    async def subscribe(self, flight_id: str) -> AsyncIterator[FlightTrajectoryPoint]:
        """Async generator yielding points for one flight until it ends."""
        session = self._sessions.get(flight_id)
        if session is None:
            raise KeyError(f"Unknown flight_id: {flight_id}")
        q = session.add_subscriber()
        try:
            while True:
                point = await q.get()
                if point is None:
                    break
                yield point
        finally:
            session.remove_subscriber(q)

    async def subscribe_all(self) -> AsyncIterator[Tuple[str, FlightTrajectoryPoint]]:
        """Async generator yielding ``(flight_id, point)`` from all active flights."""
        q: asyncio.Queue[Optional[_BroadcastItem]] = asyncio.Queue(maxsize=500)
        self._all_subscribers.append(q)
        try:
            while True:
                item = await q.get()
                if item is None:
                    continue
                yield item
        finally:
            self._all_subscribers.remove(q)

    # ── Flight control ─────────────────────────────────────────

    async def cancel_flight(self, flight_id: str) -> None:
        session = self._sessions.get(flight_id)
        if session:
            await session.cancel()

    def get_status(self, flight_id: str) -> FlightStatus:
        session = self._sessions.get(flight_id)
        if session is None:
            raise KeyError(f"Unknown flight_id: {flight_id}")
        return session.status()

    def list_flights(self) -> List[FlightStatus]:
        return [s.status() for s in self._sessions.values()]

    def active_flights(self) -> List[str]:
        return [fid for fid, s in self._sessions.items() if s.state == FlightState.ACTIVE]

    # ── Lifecycle ──────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Cancel all active flights and clean up."""
        for session in self._sessions.values():
            await session.cancel()
        self._sessions.clear()
        logger.info("FlightStreamService shut down")
