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
clip_left_line = None
clip_right_line = None

SPEED_MPS = float(sc.DEFAULT_RULES.speed_mps)
TURN_RATE_DEG_S = float(sc.DEFAULT_RULES.turn_rate_deg_s)
DENSIFY_KM = float(sc.FLIGHT_PATH_DENSIFY_KM)
FILLET_ANGLE_DEG = float(sc.FLIGHT_PATH_FILLET_ANGLE_DEG)
OFFSET_KM = float(sc.FLIGHT_PATH_OFFSET_KM)

POST_SMOOTH_RADIUS_KM = 0.25
POST_SMOOTH_STEP_KM = 0.03

CLIP_SMOOTH_RADIUS_KM = 1.2
CLIP_SMOOTH_STEP_KM = 0.05
MIN_INNER_RADIUS_KM = 0.8
CLIP_SMOOTH_RADIUS_KM = max(CLIP_SMOOTH_RADIUS_KM, OFFSET_KM + MIN_INNER_RADIUS_KM)

STRONG_SMOOTH_RADIUS_KM = 2
STRONG_SMOOTH_STEP_KM = 0.03

fig, ax = plt.subplots()
ax.set_title("Click points, press Enter to draw line")
ax.set_aspect("equal", "box")
ax.set_xlim(0.0, 5.0)
ax.set_ylim(0.0, 5.0)
ax.grid(True, alpha=0.2)

scatter = ax.scatter([], [], s=30, c="black")


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


def build_offset_from_center(center_xy, offset_km):
    if len(center_xy) < 2:
        return []
    offset_xy = sc._offset_curve_by_normal_xy(center_xy, offset_km)
    return sc._clean_polyline_xy(offset_xy, min_dist_km=1e-9)


def build_simcore_paths(points_xy):
    center_xy = sc._clean_polyline_xy(points_xy, min_dist_km=1e-6)
    if len(center_xy) < 2:
        return []
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
    return densified_center


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


def fix_offset_kinks(points_xy):
    if len(points_xy) < 2:
        return points_xy

    pts = sc._clean_polyline_xy(points_xy, min_dist_km=1e-9)
    pts = clip_tail_intersections(pts)
    pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    if len(pts) >= 3 and STRONG_SMOOTH_RADIUS_KM > 0:
        pts = sc._fillet_polyline_xy(
            pts,
            radius_km=STRONG_SMOOTH_RADIUS_KM,
            step_km=STRONG_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        pts = sc._densify_points_xy(pts, DENSIFY_KM)
        pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    if len(pts) >= 3 and POST_SMOOTH_RADIUS_KM > 0:
        pts = sc._fillet_polyline_xy(
            pts,
            radius_km=POST_SMOOTH_RADIUS_KM,
            step_km=POST_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        pts = sc._densify_points_xy(pts, DENSIFY_KM)
        pts = sc._clean_polyline_xy(pts, min_dist_km=1e-9)

    pts = clip_tail_intersections(pts)
    return sc._clean_polyline_xy(pts, min_dist_km=1e-9)


def update_line(line_ref, points_xy, color, linestyle, label):
    if len(points_xy) < 2:
        return line_ref
    xs, ys = zip(*points_xy)
    if line_ref is None:
        line_ref, = ax.plot(xs, ys, color=color, linewidth=1.5, linestyle=linestyle, label=label)
    else:
        line_ref.set_data(xs, ys)
    return line_ref


def on_click(event) -> None:
    if event.inaxes is not ax or event.xdata is None or event.ydata is None:
        return
    x = float(event.xdata)
    y = float(event.ydata)
    points.append((x, y))
    add_label(x + 0.02, y + 0.02, len(points))
    update_points()


def on_key(event) -> None:
    global line, smooth_line, clip_left_line, clip_right_line
    if event.key not in ("enter", "return"):
        return
    if len(points) < 2:
        return

    xs, ys = zip(*points)
    if line is None:
        line, = ax.plot(xs, ys, color="tab:blue", linewidth=2.0, label="centerline")
    else:
        line.set_data(xs, ys)

    smooth_points = build_simcore_paths(points)
    if len(smooth_points) >= 2:
        smooth_line = update_line(
            smooth_line,
            smooth_points,
            "tab:orange",
            "--",
            "smoothed",
        )

        clip_center = sc._fillet_polyline_xy(
            smooth_points,
            radius_km=CLIP_SMOOTH_RADIUS_KM,
            step_km=CLIP_SMOOTH_STEP_KM,
            angle_threshold_deg=0.0,
        )
        clip_center = sc._densify_points_xy(clip_center, DENSIFY_KM)
        clip_center = sc._clean_polyline_xy(clip_center, min_dist_km=1e-9)

        clip_left = fix_offset_kinks(build_offset_from_center(clip_center, -OFFSET_KM))
        clip_right = fix_offset_kinks(build_offset_from_center(clip_center, OFFSET_KM))

        clip_left_line = update_line(
            clip_left_line,
            clip_left,
            "tab:red",
            "-",
            "clip left",
        )
        clip_right_line = update_line(
            clip_right_line,
            clip_right,
            "tab:red",
            "--",
            "clip right",
        )

        ax.legend(loc="upper right")

    fig.canvas.draw_idle()


fig.canvas.mpl_connect("button_press_event", on_click)
fig.canvas.mpl_connect("key_press_event", on_key)

update_points()
plt.show()
