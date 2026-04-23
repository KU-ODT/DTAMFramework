import math
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import sim_core as sc

points = []
labels = []
line = None
smooth_line = None
variant_lines = {}
SPEED_MPS = float(sc.DEFAULT_RULES.speed_mps)
TURN_RATE_DEG_S = float(sc.DEFAULT_RULES.turn_rate_deg_s)
DENSIFY_KM = float(sc.FLIGHT_PATH_DENSIFY_KM)
FILLET_ANGLE_DEG = float(sc.FLIGHT_PATH_FILLET_ANGLE_DEG)
OFFSET_KM = float(sc.FLIGHT_PATH_OFFSET_KM)
EXTRA_FILLET_KM = 0.4
BEVEL_KM = 0.2
BEVEL_ANGLE_DEG = 60.0
CLIP_BEVEL_KM = 1.8

POST_SMOOTH_RADIUS_KM = 0.25     # 오프셋 결과를 한 번 더 둥글게(너무 크면 형태가 많이 변함)
POST_SMOOTH_STEP_KM = 0.03

CLIP_BEVEL_ANGLE_DEG = 120
CLIP_SMOOTH_RADIUS_KM = 1.2
CLIP_SMOOTH_STEP_KM = 0.05

MIN_INNER_RADIUS_KM = 0.8

CLIP_SMOOTH_RADIUS_KM = max(CLIP_SMOOTH_RADIUS_KM, OFFSET_KM + MIN_INNER_RADIUS_KM)



fig, ax = plt.subplots()
ax.set_title("Click points, press Enter to draw line")
ax.set_aspect("equal", "box")
ax.set_xlim(0.0, 5.0)
ax.set_ylim(0.0, 5.0)
ax.grid(True, alpha=0.2)

scatter = ax.scatter([], [], s=30, c="black")


STRONG_SMOOTH_RADIUS_KM = 1.5   # 예각용 강한 라운딩 (0.6~1.5 사이로 튜닝)
STRONG_SMOOTH_STEP_KM = 0.03

def fix_offset_kinks(points_xy):
    if len(points_xy) < 2:
        return points_xy

    pts = sc._clean_polyline_xy(points_xy, min_dist_km=1e-9)

    # (여기 bevel은 "예각"에 잘 안 먹는 구조라서, 아래 강한 라운딩이 더 중요합니다)
    # pts = bevel_polyline(pts, CLIP_BEVEL_KM, CLIP_BEVEL_ANGLE_DEG)

    pts = remove_self_intersections(pts)
    pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    # 교차 잘리고 생긴 뾰족 코너를 한 번 크게 둥글게
    if len(pts) >= 3 and STRONG_SMOOTH_RADIUS_KM > 0:
        pts = sc._fillet_polyline_xy(
            pts,
            radius_km=STRONG_SMOOTH_RADIUS_KM,
            step_km=STRONG_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        pts = sc._densify_points_xy(pts, DENSIFY_KM)
        pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    # 마지막 마감(기존)
    if len(pts) >= 3 and POST_SMOOTH_RADIUS_KM > 0:
        pts = sc._fillet_polyline_xy(
            pts,
            radius_km=POST_SMOOTH_RADIUS_KM,
            step_km=POST_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        pts = sc._densify_points_xy(pts, DENSIFY_KM)
        pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    return pts

def update_points() -> None:
    if points:
        scatter.set_offsets(points)
    else:
        scatter.set_offsets(np.empty((0, 2)))
    fig.canvas.draw_idle()


def add_label(x: float, y: float, idx: int) -> None:
    labels.append(
        ax.text(
            x,
            y,
            str(idx),
            fontsize=8,
            color="black",
            ha="left",
            va="bottom",
        )
    )


def build_offset_from_center(center_xy, node_xy, offset_km):
    if len(center_xy) < 2:
        return []
    offset_xy = sc._offset_curve_by_normal_xy(center_xy, offset_km)
    return sc._clean_polyline_xy(offset_xy, min_dist_km=1e-9)


def build_simcore_paths(points_xy):
    center_xy = sc._clean_polyline_xy(points_xy, min_dist_km=1e-6)
    if len(center_xy) < 2:
        return [], [], []
    node_xy = center_xy
    center_xy = sc._simplify_polyline_xy(center_xy, angle_tol_deg=2.0, min_dist_km=1e-6)
    turn_radius_km = sc._turn_radius_km_for_path(
        speed_mps=SPEED_MPS,
        turn_rate_deg_s=TURN_RATE_DEG_S,
        offset_km=OFFSET_KM,
    )
    smoothed_center = sc._fillet_polyline_xy(
        center_xy,
        radius_km=turn_radius_km,
        step_km=DENSIFY_KM,
        angle_threshold_deg=FILLET_ANGLE_DEG,
    )
    densified_center = sc._densify_points_xy(smoothed_center, DENSIFY_KM)
    densified_center = sc._clean_polyline_xy(densified_center, min_dist_km=1e-9)
    if len(densified_center) < 2:
        return densified_center, [], []
    return densified_center, node_xy


def extra_round_center(center_xy):
    if len(center_xy) < 3:
        return list(center_xy)
    step_km = max(0.01, DENSIFY_KM / 2.0)
    rounded = sc._fillet_polyline_xy(
        center_xy,
        radius_km=EXTRA_FILLET_KM,
        step_km=step_km,
        angle_threshold_deg=0.0,
    )
    return sc._densify_points_xy(rounded, DENSIFY_KM)


def remove_self_intersections(points_xy):
    if len(points_xy) < 4:
        return points_xy

    def cross(ax, ay, bx, by):
        return ax * by - ay * bx

    def segment_intersection(p1, p2, q1, q2):
        px, py = p1
        rx, ry = (p2[0] - p1[0], p2[1] - p1[1])
        qx, qy = q1
        sx, sy = (q2[0] - q1[0], q2[1] - q1[1])
        denom = cross(rx, ry, sx, sy)
        if abs(denom) <= 1e-12:
            return False, (0.0, 0.0), 0.0
        qmpx = qx - px
        qmpy = qy - py
        t = cross(qmpx, qmpy, sx, sy) / denom
        u = cross(qmpx, qmpy, rx, ry) / denom
        if t <= 1e-6 or t >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        if u <= 1e-6 or u >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        return True, (px + t * rx, py + t * ry), t

    out = [points_xy[0]]
    for point in points_xy[1:]:
        start = out[-1]
        while len(out) >= 3:
            hit_idx = None
            hit_pt = None
            hit_t = None
            for idx in range(1, len(out) - 1):
                hit, pt, t = segment_intersection(start, point, out[idx - 1], out[idx])
                if not hit:
                    continue
                if hit_t is None or t < hit_t:
                    hit_t = t
                    hit_idx = idx
                    hit_pt = pt
            if hit_idx is None or hit_pt is None:
                break
            out = out[:hit_idx] + [hit_pt]
            start = hit_pt
        if point != out[-1]:
            out.append(point)
    return out


def clip_tail_intersections(points_xy):
    if len(points_xy) < 4:
        return points_xy

    def cross(ax, ay, bx, by):
        return ax * by - ay * bx

    def segment_intersection(p1, p2, q1, q2):
        px, py = p1
        rx, ry = (p2[0] - p1[0], p2[1] - p1[1])
        qx, qy = q1
        sx, sy = (q2[0] - q1[0], q2[1] - q1[1])
        denom = cross(rx, ry, sx, sy)
        if abs(denom) <= 1e-12:
            return False, (0.0, 0.0), 0.0
        qmpx = qx - px
        qmpy = qy - py
        t = cross(qmpx, qmpy, sx, sy) / denom
        u = cross(qmpx, qmpy, rx, ry) / denom
        if t <= 1e-6 or t >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        if u <= 1e-6 or u >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        return True, (px + t * rx, py + t * ry), t

    out = [points_xy[0]]
    for point in points_xy[1:]:
        start = out[-1]
        hit_pt = None
        hit_t = None
        for idx in range(1, len(out) - 1):
            hit, pt, t = segment_intersection(start, point, out[idx - 1], out[idx])
            if not hit:
                continue
            if hit_t is None or t < hit_t:
                hit_t = t
                hit_pt = pt
        if hit_pt is not None:
            point = hit_pt
        if point != out[-1]:
            out.append(point)
    return out


def bevel_polyline(points_xy, bevel_km, angle_thresh_deg):
    if len(points_xy) < 3 or bevel_km <= 0:
        return points_xy
    out = [points_xy[0]]
    thresh_rad = math.radians(angle_thresh_deg)
    eps = 1e-9
    for i in range(1, len(points_xy) - 1):
        axp, ayp = points_xy[i - 1]
        bx, by = points_xy[i]
        cx, cy = points_xy[i + 1]
        v1x, v1y = bx - axp, by - ayp
        v2x, v2y = cx - bx, cy - by
        l1 = math.hypot(v1x, v1y)
        l2 = math.hypot(v2x, v2y)
        if l1 <= eps or l2 <= eps:
            out.append((bx, by))
            continue
        d1x, d1y = v1x / l1, v1y / l1
        d2x, d2y = v2x / l2, v2y / l2
        dot = max(-1.0, min(1.0, d1x * d2x + d1y * d2y))
        theta = math.acos(dot)
        if theta >= thresh_rad:
            out.append((bx, by))
            continue
        cut = min(bevel_km, 0.45 * min(l1, l2))
        if cut <= eps:
            out.append((bx, by))
            continue
        p1 = (bx - d1x * cut, by - d1y * cut)
        p2 = (bx + d2x * cut, by + d2y * cut)
        if out[-1] != p1:
            out.append(p1)
        out.append(p2)
    out.append(points_xy[-1])
    return out


def plot_variant(key, points_xy, color, linestyle, label):
    if len(points_xy) < 2:
        return
    xs, ys = zip(*points_xy)
    line = variant_lines.get(key)
    if line is None:
        line, = ax.plot(xs, ys, color=color, linewidth=1.5, linestyle=linestyle, label=label)
        variant_lines[key] = line
    else:
        line.set_data(xs, ys)


def set_variant_visible(prefix, visible):
    for key, line in variant_lines.items():
        if key.startswith(prefix):
            line.set_visible(visible)


def on_click(event) -> None:
    if event.inaxes is not ax or event.xdata is None or event.ydata is None:
        return
    x = float(event.xdata)
    y = float(event.ydata)
    points.append((x, y))
    add_label(x + 0.02, y + 0.02, len(points))
    update_points()


def on_key(event) -> None:
    global line, smooth_line
    if event.key not in ("enter", "return"):
        if event.key in ("1", "2", "3"):
            set_variant_visible("round", event.key == "1")
            set_variant_visible("bevel", event.key == "2")
            set_variant_visible("clip", event.key == "3")
            ax.legend(loc="upper right")
            fig.canvas.draw_idle()
        return
    if len(points) < 2:
        return
    xs, ys = zip(*points)
    if line is None:
        line, = ax.plot(xs, ys, color="tab:blue", linewidth=2.0)
    else:
        line.set_data(xs, ys)
    smooth_points, node_xy = build_simcore_paths(points)
    if len(smooth_points) >= 2:
        sx, sy = zip(*smooth_points)
        if smooth_line is None:
            smooth_line, = ax.plot(
                sx,
                sy,
                color="tab:orange",
                linewidth=1.5,
                linestyle="--",
            )
        else:
            smooth_line.set_data(sx, sy)
        left_base = build_offset_from_center(smooth_points, node_xy, -OFFSET_KM)
        right_base = build_offset_from_center(smooth_points, node_xy, OFFSET_KM)

        round_center = extra_round_center(smooth_points)
        left_round = build_offset_from_center(round_center, node_xy, -OFFSET_KM)
        right_round = build_offset_from_center(round_center, node_xy, OFFSET_KM)

        left_bevel = bevel_polyline(left_base, BEVEL_KM, BEVEL_ANGLE_DEG)
        right_bevel = bevel_polyline(right_base, BEVEL_KM, BEVEL_ANGLE_DEG)

        # ====== (on_key 안에서 clip_* 만드는 부분만 교체) ======
        clip_center = sc._fillet_polyline_xy(
            smooth_points,
            radius_km=CLIP_SMOOTH_RADIUS_KM,
            step_km=CLIP_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        clip_center = sc._densify_points_xy(clip_center, DENSIFY_KM)
        clip_center = sc._clean_polyline_xy(clip_center, min_dist_km=1e-9)

        clip_left_base = build_offset_from_center(clip_center, node_xy, -OFFSET_KM)
        clip_right_base = build_offset_from_center(clip_center, node_xy, OFFSET_KM)

        left_clip = fix_offset_kinks(clip_left_base)
        right_clip = fix_offset_kinks(clip_right_base)

        plot_variant("round_left", left_round, "tab:green", "-", "round+ left")
        plot_variant("round_right", right_round, "tab:green", "--", "round+ right")
        plot_variant("bevel_left", left_bevel, "tab:purple", "-", "bevel left")
        plot_variant("bevel_right", right_bevel, "tab:purple", "--", "bevel right")
        plot_variant("clip_left", left_clip, "tab:red", "-", "clip+smooth left")
        plot_variant("clip_right", right_clip, "tab:red", "--", "clip+smooth right")
        set_variant_visible("round", True)
        set_variant_visible("bevel", False)
        set_variant_visible("clip", False)
        ax.legend(loc="upper right")
    fig.canvas.draw_idle()


fig.canvas.mpl_connect("button_press_event", on_click)
fig.canvas.mpl_connect("key_press_event", on_key)

update_points()
plt.show()
