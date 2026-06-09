import pytest

from VehicleModule.app.domain.transform.odt_pose_frame import (
    OdtPoseFrameState,
    POSE_FRAME_TYPE,
    SpawnPose,
)


def test_pose_frame_uses_odt_visual_axes_for_unreal_pose():
    state = OdtPoseFrameState(
        origin_lat=37.5665,
        origin_lon=126.9780,
        origin_alt_m=10.0,
        spawn_pose=SpawnPose(x_m=100.0, y_m=200.0, z_m=30.0, yaw_deg=0.0, vehicle_name="Drone1"),
    )

    projected = state.project(
        lat=37.5675,  # roughly 111 m north of the origin
        lon=126.9780,
        alt_m=20.0,
        heading_deg=0.0,
        time_s=0.0,
    )

    rel = projected["relative_position"]
    # DT World's visual AirSim frame is X=east, Y=south(-north).  A geographic
    # northward movement should therefore move mostly along pose Y, not pose X.
    assert abs(rel["north"]) < 1.0
    assert rel["east"] < -100.0
    assert rel["down"] == pytest.approx(-10.0, abs=0.05)

    geo = projected["offset"]["local_ned_m"]
    assert geo["north"] > 100.0
    assert abs(geo["east"]) < 1.0
    assert projected["pose_frame"]["type"] == POSE_FRAME_TYPE
    assert projected["pose_frame"]["type"] == "odt_mission_relative_custom_frame"


def test_pose_frame_yaw_maps_geographic_heading_to_odt_visual_frame():
    state = OdtPoseFrameState(
        origin_lat=37.5665,
        origin_lon=126.9780,
        origin_alt_m=10.0,
        spawn_pose=SpawnPose(yaw_deg=0.0, vehicle_name="Drone1"),
    )

    projected = state.project(
        lat=37.5665,
        lon=126.9790,
        alt_m=10.0,
        heading_deg=90.0,
        time_s=0.0,
    )

    assert projected["relative_position"]["north"] > 80.0
    assert abs(projected["relative_position"]["east"]) < 1.0
    assert projected["yaw_deg"] == pytest.approx(0.0)
    assert projected["target_frame_yaw_deg"] == pytest.approx(0.0)
