"""Airspace route planner — ported from trafficS/app/pathplanner.py.

Builds a Dijkstra graph from vertiport.csv and waypoint.csv (the same data
already on disk under backend/data/) and provides:

  * `find_route(start, end)` — shortest waypoint-only path between two
    vertiports, distance in km and a (lon, lat) polyline geometry.
  * Optional turn arcs at departure/arrival vertiports (uses INR/OTR radii
    and bearings from the vertiport CSV).
  * Edge closure / spare-edge support for routing fallbacks.

Pure stdlib — no external deps. Used by `/api/route` endpoint.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import csv
import heapq
import math


@dataclass(frozen=True)
class Port:
    name: str
    lat: float
    lon: float
    inr_km: float
    otr_km: float
    inr_deg: Optional[float]
    otr_deg: Optional[float]
    turn_dir: str
    links: Tuple[str, ...]
    kind: str = "port"


@dataclass(frozen=True)
class Waypoint:
    name: str
    lat: float
    lon: float
    alt_ft: Optional[float]
    links: Tuple[str, ...]
    spare_links: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RouteResult:
    path: List[str]
    distance_km: float
    points: List[Tuple[float, float]]  # (lon, lat)


class LocalProjection:
    def __init__(self, lon0: float, lat0: float) -> None:
        self.lon0 = lon0
        self.lat0 = lat0
        self._km_per_deg_lat = 111.32
        self._km_per_deg_lon = 111.32 * math.cos(math.radians(lat0))

    def to_xy_km(self, lon: float, lat: float) -> Tuple[float, float]:
        dx = (lon - self.lon0) * self._km_per_deg_lon
        dy = (lat - self.lat0) * self._km_per_deg_lat
        return dx, dy

    def to_lonlat(self, x_km: float, y_km: float) -> Tuple[float, float]:
        lon = self.lon0 + (x_km / self._km_per_deg_lon)
        lat = self.lat0 + (y_km / self._km_per_deg_lat)
        return lon, lat


class RoutePlanner:
    def __init__(self, ports: Dict[str, Port], waypoints: Dict[str, Waypoint]) -> None:
        if not ports or not waypoints:
            raise ValueError("RoutePlanner requires ports and waypoints.")
        self.ports = ports
        self.waypoints = waypoints

        all_lons = [p.lon for p in ports.values()] + [w.lon for w in waypoints.values()]
        all_lats = [p.lat for p in ports.values()] + [w.lat for w in waypoints.values()]
        lon0 = sum(all_lons) / len(all_lons)
        lat0 = sum(all_lats) / len(all_lats)
        self.projection = LocalProjection(lon0, lat0)

        self.node_xy: Dict[str, Tuple[float, float]] = {}
        for port in ports.values():
            self.node_xy[port.name] = self.projection.to_xy_km(port.lon, port.lat)
        for wp in waypoints.values():
            self.node_xy[wp.name] = self.projection.to_xy_km(wp.lon, wp.lat)

        self.wp_graph: Dict[str, List[Tuple[str, float]]] = {n: [] for n in waypoints}
        self._build_waypoint_graph()
        self.port_links = {p.name: self._filter_links(p.links) for p in ports.values()}
        self.waypoint_to_ports = self._build_waypoint_to_ports()
        self.graph: Dict[str, List[Tuple[str, float]]] = {n: [] for n in self.node_xy}
        self._build_full_graph()
        self.closed_edges: set[tuple[str, str]] = set()
        self.spare_edges: set[tuple[str, str]] = set()
        self._graph_revision = 0
        self._route_cache_limit = 4096
        self._route_cache: "OrderedDict[tuple[str, str, bool, int, int], RouteResult]" = OrderedDict()
        self._build_spare_edges()

    @classmethod
    def from_csv(
        cls,
        vertiport_csv: Path | str,
        waypoint_csv: Path | str,
        *,
        encoding: Optional[str] = None,
    ) -> "RoutePlanner":
        ports = _load_ports(Path(vertiport_csv), encoding=encoding)
        waypoints = _load_waypoints(Path(waypoint_csv), encoding=encoding)
        return cls(ports, waypoints)

    def list_ports(self) -> List[str]:
        return sorted(self.ports.keys())

    def list_waypoints(self) -> List[str]:
        return sorted(self.waypoints.keys())

    def find_route(
        self,
        start_port: str,
        end_port: str,
    ) -> RouteResult:
        cache_key = (start_port, end_port, self._graph_revision)
        cached = self._route_cache.get(cache_key)
        if cached is not None:
            self._route_cache.move_to_end(cache_key)
            return RouteResult(
                path=list(cached.path),
                distance_km=float(cached.distance_km),
                points=list(cached.points),
            )
        path, distance_km = self._shortest_path(start_port, end_port)
        points = self._build_geometry(path)
        result = RouteResult(path=path, distance_km=distance_km, points=points)
        self._route_cache[cache_key] = RouteResult(
            path=list(path),
            distance_km=float(distance_km),
            points=list(points),
        )
        self._route_cache.move_to_end(cache_key)
        while len(self._route_cache) > self._route_cache_limit:
            self._route_cache.popitem(last=False)
        return result

    def _invalidate_route_cache(self) -> None:
        self._graph_revision += 1
        self._route_cache.clear()

    def _build_waypoint_graph(self) -> None:
        for wp in self.waypoints.values():
            for link in wp.links:
                if link in self.waypoints:
                    self._add_edge(wp.name, link)

    def _add_edge(self, a: str, b: str) -> None:
        if a == b:
            return
        dist = self._distance_km(a, b)
        self.wp_graph[a].append((b, dist))
        self.wp_graph[b].append((a, dist))

    def _filter_links(self, links: Iterable[str]) -> List[str]:
        return [name for name in links if name in self.waypoints]

    def _build_waypoint_to_ports(self) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {n: [] for n in self.waypoints}
        for port in self.ports.values():
            for link in self.port_links.get(port.name, []):
                mapping[link].append(port.name)
        return mapping

    def _build_full_graph(self) -> None:
        for wp, neighbors in self.wp_graph.items():
            for nb, _dist in neighbors:
                self._add_graph_edge(wp, nb)
        for port, links in self.port_links.items():
            for wp in links:
                self._add_graph_edge(port, wp)

    def _build_spare_edges(self) -> None:
        for wp in self.waypoints.values():
            if not wp.spare_links:
                continue
            for link in wp.spare_links:
                if link not in self.waypoints:
                    continue
                if any(n == link for n, _ in self.wp_graph.get(wp.name, [])):
                    continue
                key = self._edge_key(wp.name, link)
                if key in self.spare_edges:
                    continue
                self.spare_edges.add(key)
                self._add_graph_edge(wp.name, link)
                self.closed_edges.add(key)

    def _add_graph_edge(self, a: str, b: str) -> None:
        if a == b:
            return
        dist = self._distance_km(a, b)
        if not any(n == b for n, _ in self.graph[a]):
            self.graph[a].append((b, dist))
        if not any(n == a for n, _ in self.graph[b]):
            self.graph[b].append((a, dist))

    def _edge_key(self, a: str, b: str) -> tuple[str, str]:
        return tuple(sorted((a, b)))

    def set_edge_closed(self, a: str, b: str, closed: bool) -> bool:
        key = self._edge_key(a, b)
        if closed:
            if key in self.closed_edges:
                return False
            self.closed_edges.add(key)
            self._invalidate_route_cache()
            return True
        if key not in self.closed_edges:
            return False
        self.closed_edges.remove(key)
        self._invalidate_route_cache()
        return True

    def is_edge_closed(self, a: str, b: str) -> bool:
        return self._edge_key(a, b) in self.closed_edges

    def _distance_km(self, a: str, b: str) -> float:
        ax, ay = self.node_xy[a]
        bx, by = self.node_xy[b]
        return math.hypot(bx - ax, by - ay)

    def _shortest_path(self, start_port: str, end_port: str) -> Tuple[List[str], float]:
        if start_port not in self.graph:
            raise ValueError(f"Unknown start node: {start_port}")
        if end_port not in self.graph:
            raise ValueError(f"Unknown end node: {end_port}")
        if start_port == end_port:
            return [start_port], 0.0

        dist: Dict[str, float] = {start_port: 0.0}
        prev: Dict[str, Optional[str]] = {start_port: None}
        queue: List[Tuple[float, str]] = [(0.0, start_port)]

        while queue:
            cost, node = heapq.heappop(queue)
            if node == end_port:
                break
            if cost != dist.get(node, math.inf):
                continue
            for nxt, weight in self.graph.get(node, []):
                if self.is_edge_closed(node, nxt):
                    continue
                if nxt in self.ports and nxt != end_port:
                    continue
                ncost = cost + weight
                if ncost < dist.get(nxt, math.inf):
                    dist[nxt] = ncost
                    prev[nxt] = node
                    heapq.heappush(queue, (ncost, nxt))

        if end_port not in dist:
            raise RuntimeError(f"No route found between {start_port} and {end_port}.")

        path: List[str] = []
        cur: Optional[str] = end_port
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        path.reverse()
        return path, dist[end_port]

    def _build_geometry(self, path: List[str]) -> List[Tuple[float, float]]:
        return [self._node_lonlat(name) for name in path]

    def _node_lonlat(self, name: str) -> Tuple[float, float]:
        if name in self.ports:
            port = self.ports[name]
            return port.lon, port.lat
        wp = self.waypoints[name]
        return wp.lon, wp.lat


# ---------- CSV loaders (auto-detect column names) ----------

def _load_ports(path: Path, encoding: Optional[str] = None) -> Dict[str, Port]:
    rows, fieldnames = _read_csv(path, encoding=encoding)
    name_col = _find_column(fieldnames, lambda k: "vertiport" in k) or fieldnames[0]
    link_col = _find_column(fieldnames, lambda k: "link" in k)

    lat_col = _find_column(fieldnames, lambda k: "lat" in k)
    lon_col = _find_column(fieldnames, lambda k: "lon" in k)
    if not lat_col or not lon_col:
        lat_col, lon_col = _infer_lat_lon_columns(fieldnames, rows)

    inr_deg_col = _find_column(fieldnames, lambda k: "inr" in k and "deg" in k)
    otr_deg_col = _find_column(fieldnames, lambda k: "otr" in k and "deg" in k)
    inr_col = _find_column(fieldnames, lambda k: "inr" in k and "deg" not in k)
    otr_col = _find_column(fieldnames, lambda k: "otr" in k and "deg" not in k)
    turn_col = _find_column(fieldnames, lambda k: "turn" in k or "circle" in k)
    class_col = _find_column(fieldnames, lambda k: "class" in k or "type" in k)

    ports: Dict[str, Port] = {}
    for row in rows:
        name = _clean_text(row.get(name_col))
        if not name:
            continue
        lat = _parse_float(row.get(lat_col))
        lon = _parse_float(row.get(lon_col))
        if lat is None or lon is None:
            continue
        inr_km = _parse_float(row.get(inr_col)) or 0.0
        otr_km = _parse_float(row.get(otr_col)) or 0.0
        inr_deg = _parse_float(row.get(inr_deg_col)) if inr_deg_col else None
        otr_deg = _parse_float(row.get(otr_deg_col)) if otr_deg_col else None
        turn_dir = _parse_turn_dir(row.get(turn_col))
        kind = _clean_text(row.get(class_col)).lower() if class_col else ""
        if not kind:
            kind = "port"
        links = tuple(_split_links(row.get(link_col)))
        ports[name] = Port(
            name=name,
            lat=lat,
            lon=lon,
            inr_km=inr_km,
            otr_km=otr_km,
            inr_deg=inr_deg,
            otr_deg=otr_deg,
            turn_dir=turn_dir,
            links=links,
            kind=kind,
        )
    if not ports:
        raise RuntimeError(f"No vertiports parsed from {path}.")
    return ports


def _load_waypoints(path: Path, encoding: Optional[str] = None) -> Dict[str, Waypoint]:
    rows, fieldnames = _read_csv(path, encoding=encoding)
    name_col = _find_column(fieldnames, lambda k: "waypoint" in k) or fieldnames[0]
    link_col = _find_column(fieldnames, lambda k: "link" in k and "spare" not in k)
    spare_col = _find_column(fieldnames, lambda k: "spare" in k)

    lat_col = _find_column(fieldnames, lambda k: "lat" in k)
    lon_col = _find_column(fieldnames, lambda k: "lon" in k)
    if not lat_col or not lon_col:
        lat_col, lon_col = _infer_lat_lon_columns(fieldnames, rows)

    alt_col = _find_column(fieldnames, lambda k: "alt" in k or k.endswith("ft"))

    waypoints: Dict[str, Waypoint] = {}
    for row in rows:
        name = _clean_text(row.get(name_col))
        if not name:
            continue
        lat = _parse_float(row.get(lat_col))
        lon = _parse_float(row.get(lon_col))
        if lat is None or lon is None:
            continue
        alt_ft = _parse_float(row.get(alt_col)) if alt_col else None
        links = tuple(_split_links(row.get(link_col)))
        spare_links = tuple(_split_links(row.get(spare_col))) if spare_col else ()
        waypoints[name] = Waypoint(
            name=name,
            lat=lat,
            lon=lon,
            alt_ft=alt_ft,
            links=links,
            spare_links=spare_links,
        )
    if not waypoints:
        raise RuntimeError(f"No waypoints parsed from {path}.")
    return waypoints


def _read_csv(path: Path, encoding: Optional[str] = None) -> Tuple[List[Dict[str, str]], List[str]]:
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            if not reader.fieldnames:
                raise RuntimeError("Missing CSV headers.")
            return rows, list(reader.fieldnames)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Failed to read CSV: {path}") from last_error


def _find_column(fieldnames: Iterable[str], predicate) -> Optional[str]:
    for name in fieldnames:
        key = _normalize_key(name)
        if predicate(key):
            return name
    return None


def _normalize_key(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _infer_lat_lon_columns(
    fieldnames: List[str],
    rows: List[Dict[str, str]],
) -> Tuple[str, str]:
    stats = _column_stats(fieldnames, rows)
    lat_candidates = []
    lon_candidates = []
    for col, (minv, maxv, meanv) in stats.items():
        if minv >= -90 and maxv <= 90 and 5 <= abs(meanv) <= 60:
            lat_candidates.append((abs(meanv), col))
        if minv >= -180 and maxv <= 180 and abs(meanv) >= 60:
            lon_candidates.append((abs(meanv), col))
    lat_col = max(lat_candidates)[1] if lat_candidates else None
    lon_col = max(lon_candidates)[1] if lon_candidates else None
    if not lat_col or not lon_col:
        raise RuntimeError("Failed to infer lat/lon columns.")
    return lat_col, lon_col


def _column_stats(
    fieldnames: Iterable[str],
    rows: List[Dict[str, str]],
    sample_size: int = 50,
) -> Dict[str, Tuple[float, float, float]]:
    stats: Dict[str, Tuple[float, float, float]] = {}
    for col in fieldnames:
        values: List[float] = []
        for row in rows[:sample_size]:
            value = _parse_float(row.get(col))
            if value is not None:
                values.append(value)
        if len(values) < 3:
            continue
        stats[col] = (min(values), max(values), sum(values) / len(values))
    return stats


def _split_links(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _clean_text(value: Optional[str]) -> str:
    return str(value).strip() if value is not None else ""


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_turn_dir(value: Optional[str]) -> str:
    text = _clean_text(value).lower()
    if text.startswith("l"):
        return "L"
    if text.startswith("r"):
        return "R"
    return "R"


# ---------- Singleton helper used by the API ----------

_planner_singleton: Optional[RoutePlanner] = None


def get_planner() -> RoutePlanner:
    """Lazy-instantiate the project-wide route planner from our backend data."""
    global _planner_singleton
    if _planner_singleton is None:
        from ..config import VERTIPORT_CSV, WAYPOINT_CSV
        _planner_singleton = RoutePlanner.from_csv(VERTIPORT_CSV, WAYPOINT_CSV)
    return _planner_singleton


def reload_planner() -> RoutePlanner:
    """Force-reload the planner (e.g. after CSV edits)."""
    global _planner_singleton
    _planner_singleton = None
    return get_planner()
