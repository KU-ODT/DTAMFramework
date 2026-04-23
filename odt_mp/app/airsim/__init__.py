from app.airsim.coord_transform import (
    wgs84_to_airsim_ned,
    wgs84_to_local_ned,
    wgs84_to_ue_ch_cm,
    load_resources_vp,
    lookup_vp_label_alt_m,
)
from app.airsim.mission_runner import AirsimMissionRunner

__all__ = [
    "AirsimMissionRunner",
    "wgs84_to_airsim_ned",
    "wgs84_to_local_ned",
    "wgs84_to_ue_ch_cm",
    "load_resources_vp",
    "lookup_vp_label_alt_m",
]

from .client import *
from .utils import *
from .types import *

__version__ = "3.3.0"

if 'quaternion_to_euler_angles' in globals() and 'to_eularian_angles' not in globals():
    def to_eularian_angles(q):
        roll, pitch, yaw = quaternion_to_euler_angles(q)
        return pitch, roll, yaw

if 'euler_to_quaternion' in globals() and 'to_quaternion' not in globals():
    def to_quaternion(pitch, roll, yaw):
        return euler_to_quaternion(roll, pitch, yaw)
