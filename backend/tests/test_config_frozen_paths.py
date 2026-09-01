# -*- coding: utf-8 -*-
"""config.py 路径选择单测（2026-09-01 打包修复批 · 工单B）。

验证两种模式下路径出口的锚定：
- 开发模式：BACKEND_DIR / DATA_DIR / DATABASE_PATH / PORT_FILE / uploads 锚定仓库 backend/
- 打包模式（monkeypatch sys.frozen）：全部锚定 %APPDATA%/MfkAgent（可持久化目录），
  sqlite 数据目录在模块导入期即被创建；.env 读取位置（Settings.Config.env_file）随迁。

实现说明：config 在导入期计算路径常量，测试用 importlib.reload 重建模块；
fixture 收尾再 reload 一次，恢复开发模式全局状态，保证测试顺序无关。
engine（app.core.database）不参与 reload，其绑定的测试库由 conftest 的
DATABASE_URL 环境变量决定，不受本文件影响。
"""
import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def config_module():
    """提供 app.core.config 模块，用例结束后恢复开发模式。"""
    import app.core.config as cfg
    yield cfg
    importlib.reload(cfg)


def test_dev_mode_paths_anchored_to_backend_dir(config_module):
    cfg = config_module
    expected_backend = Path(cfg.__file__).resolve().parent.parent.parent
    assert cfg.BACKEND_DIR == expected_backend
    assert cfg.DATA_DIR == expected_backend
    assert cfg.DATABASE_PATH == expected_backend / "mfkagent.db"
    assert cfg.PORT_FILE == expected_backend / ".mfkagent_port"
    assert cfg.settings.UPLOAD_DIR == str(expected_backend / "uploads")
    assert cfg.settings.CHROMA_PERSIST_DIR == str(expected_backend / "chroma_db")
    # .env 读取位置与 BACKEND_DIR 同源（feishu.py 等写入方共用此出口）
    assert str(cfg.Settings.Config.env_file) == str(expected_backend / ".env")


def test_frozen_mode_paths_use_appdata(config_module, monkeypatch, tmp_path):
    cfg = config_module
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    importlib.reload(cfg)

    data_root = fake_appdata / "MfkAgent"
    assert cfg.BACKEND_DIR == data_root
    assert cfg.DATA_DIR == data_root
    assert cfg.DATABASE_PATH == data_root / "mfkagent.db"
    assert cfg.PORT_FILE == data_root / ".mfkagent_port"
    assert cfg.settings.UPLOAD_DIR == str(data_root / "uploads")
    assert cfg.settings.CHROMA_PERSIST_DIR == str(data_root / "chroma_db")
    assert str(cfg.Settings.Config.env_file) == str(data_root / ".env")
    # 数据根目录已被创建（sqlite 引擎在 database.py 导入期即连库，目录必须先存在）
    assert data_root.is_dir()


def test_frozen_mode_without_appdata_falls_back_to_home(config_module, monkeypatch, tmp_path):
    """非 Windows 打包（APPDATA 未设）时落用户目录，不落 temp。"""
    cfg = config_module
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(cfg.sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    importlib.reload(cfg)

    expected = Path.home() / ".local" / "share" / "MfkAgent"
    assert cfg.BACKEND_DIR == expected
    assert cfg.DATABASE_PATH == expected / "mfkagent.db"
