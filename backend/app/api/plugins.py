from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.services.plugin import plugin_manager, Plugin, PluginStatus

router = APIRouter()


class PluginCreate(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    config: Dict[str, Any] = {}


class PluginConfig(BaseModel):
    config: Dict[str, Any] = {}


@router.get("")
async def list_plugins():
    return {"plugins": plugin_manager.list_plugins()}


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    plugin = plugin_manager.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin.to_dict()


@router.post("")
async def create_plugin(request: PluginCreate):
    plugin_id = request.name.lower().replace(" ", "_")
    plugin = Plugin(
        plugin_id=plugin_id,
        name=request.name,
        version=request.version,
        description=request.description,
        author=request.author,
        config=request.config,
    )
    plugin_manager.register_plugin(plugin)
    return plugin.to_dict()


@router.post("/{plugin_id}/activate")
async def activate_plugin(plugin_id: str):
    success = plugin_manager.activate_plugin(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "activated"}


@router.post("/{plugin_id}/deactivate")
async def deactivate_plugin(plugin_id: str):
    success = plugin_manager.deactivate_plugin(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "deactivated"}


@router.put("/{plugin_id}/config")
async def update_config(plugin_id: str, request: PluginConfig):
    success = plugin_manager.update_config(plugin_id, request.config)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "updated"}


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_id: str):
    success = plugin_manager.delete_plugin(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "deleted"}
