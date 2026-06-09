"""API routes for launching external DTAM plug-ins."""

from fastapi import APIRouter

from app.services.plugin_process_service import launch_plugin, plugin_status, stop_plugin

router = APIRouter()


@router.post("/{plugin_id}/launch")
async def launch_dtam_plugin(plugin_id: str) -> dict:
    return launch_plugin(plugin_id)


@router.get("/{plugin_id}/status")
async def get_dtam_plugin_status(plugin_id: str) -> dict:
    return plugin_status(plugin_id)


@router.post("/{plugin_id}/stop")
async def stop_dtam_plugin(plugin_id: str) -> dict:
    return stop_plugin(plugin_id)
