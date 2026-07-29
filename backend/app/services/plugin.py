from typing import Dict, Any, List, Optional
from enum import Enum
import json
import os


class PluginStatus(str, Enum):
    INSTALLED = "installed"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Plugin:
    def __init__(
        self,
        plugin_id: str,
        name: str,
        version: str,
        description: str = "",
        author: str = "",
        status: PluginStatus = PluginStatus.INSTALLED,
        config: Dict[str, Any] = None,
    ):
        self.plugin_id = plugin_id
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.status = status
        self.config = config or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pluginId": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "status": self.status.value,
            "config": self.config,
        }


class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}

    def register_plugin(self, plugin: Plugin):
        self.plugins[plugin.plugin_id] = plugin

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        return self.plugins.get(plugin_id)

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.plugins.values()]

    def activate_plugin(self, plugin_id: str) -> bool:
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.ACTIVE
        return True

    def deactivate_plugin(self, plugin_id: str) -> bool:
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.INACTIVE
        return True

    def delete_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.plugins:
            del self.plugins[plugin_id]
            return True
        return False

    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False
        plugin.config.update(config)
        return True


plugin_manager = PluginManager()

plugin_manager.register_plugin(
    Plugin(
        plugin_id="web_search",
        name="Web Search",
        version="1.0.0",
        description="搜索互联网获取信息",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    )
)

plugin_manager.register_plugin(
    Plugin(
        plugin_id="code_execution",
        name="Code Execution",
        version="1.0.0",
        description="执行 Python 代码",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    )
)

plugin_manager.register_plugin(
    Plugin(
        plugin_id="file_operations",
        name="File Operations",
        version="1.0.0",
        description="文件读写操作",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    )
)
