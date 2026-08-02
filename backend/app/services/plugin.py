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
    """插件管理器（DB 持久化）。

    插件元数据存 `plugins` 表，重启后自动恢复，不再纯内存丢失。
    """

    def __init__(self):
        self._loaded = False
        self._ensure_loaded()

    # ---------- 内部：DB 读写 ----------

    def _ensure_loaded(self):
        if self._loaded:
            return
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            db.query(PluginItem).count()
            self._loaded = True
        except Exception:
            # 表尚未创建（main.py create_all 之前）——等 seed_default_plugins 兜底
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    def seed_default_plugins(self):
        """表为空时写入预置插件（幂等；需在 Base.metadata.create_all 之后调用）"""
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            db.query(PluginItem).count()
            for p in _DEFAULT_PLUGINS:
                if not db.query(PluginItem).filter(PluginItem.plugin_id == p.plugin_id).first():
                    db.add(
                        PluginItem(
                            plugin_id=p.plugin_id,
                            name=p.name,
                            version=p.version,
                            description=p.description,
                            author=p.author,
                            status=p.status.value,
                            config=p.config,
                        )
                    )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _row_to_plugin(self, row) -> Plugin:
        try:
            status = PluginStatus(row.status)
        except ValueError:
            status = PluginStatus.INSTALLED
        return Plugin(
            plugin_id=row.plugin_id,
            name=row.name,
            version=row.version,
            description=row.description,
            author=row.author,
            status=status,
            config=row.config or {},
        )

    # ---------- 对外接口（对齐原内存版签名） ----------

    def register_plugin(self, plugin: Plugin):
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            row = db.query(PluginItem).filter(PluginItem.plugin_id == plugin.plugin_id).first()
            if row:
                row.name = plugin.name
                row.version = plugin.version
                row.description = plugin.description
                row.author = plugin.author
                row.status = plugin.status.value
                row.config = plugin.config
            else:
                db.add(
                    PluginItem(
                        plugin_id=plugin.plugin_id,
                        name=plugin.name,
                        version=plugin.version,
                        description=plugin.description,
                        author=plugin.author,
                        status=plugin.status.value,
                        config=plugin.config,
                    )
                )
            db.commit()
        finally:
            db.close()

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            row = db.query(PluginItem).filter(PluginItem.plugin_id == plugin_id).first()
            return self._row_to_plugin(row) if row else None
        finally:
            db.close()

    def list_plugins(self) -> List[Dict[str, Any]]:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            rows = db.query(PluginItem).order_by(PluginItem.created_at.asc(), PluginItem.id.asc()).all()
            return [self._row_to_plugin(r).to_dict() for r in rows]
        finally:
            db.close()

    def _update_status(self, plugin_id: str, status: PluginStatus) -> bool:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            row = db.query(PluginItem).filter(PluginItem.plugin_id == plugin_id).first()
            if not row:
                return False
            row.status = status.value
            db.commit()
            return True
        finally:
            db.close()

    def activate_plugin(self, plugin_id: str) -> bool:
        return self._update_status(plugin_id, PluginStatus.ACTIVE)

    def deactivate_plugin(self, plugin_id: str) -> bool:
        return self._update_status(plugin_id, PluginStatus.INACTIVE)

    def delete_plugin(self, plugin_id: str) -> bool:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            row = db.query(PluginItem).filter(PluginItem.plugin_id == plugin_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()

    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            row = db.query(PluginItem).filter(PluginItem.plugin_id == plugin_id).first()
            if not row:
                return False
            merged = dict(row.config or {})
            merged.update(config)
            row.config = merged
            db.commit()
            return True
        finally:
            db.close()


_DEFAULT_PLUGINS = [
    Plugin(
        plugin_id="web_search",
        name="Web Search",
        version="1.0.0",
        description="搜索互联网获取信息",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    ),
    Plugin(
        plugin_id="code_execution",
        name="Code Execution",
        version="1.0.0",
        description="执行 Python 代码",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    ),
    Plugin(
        plugin_id="file_operations",
        name="File Operations",
        version="1.0.0",
        description="文件读写操作",
        author="MfkAgent",
        status=PluginStatus.ACTIVE,
    ),
]


plugin_manager = PluginManager()
