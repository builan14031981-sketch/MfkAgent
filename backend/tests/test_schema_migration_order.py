# -*- coding: utf-8 -*-
"""启动序列迁移测试（2026-09-01 打包修复批 · 工单E）。

验证 main.py 的启动顺序修复：_ensure_schema（补全 plugins.source 列）必须先于
seed（含 source 不为空的 INSERT）执行，否则从旧库启动时会直接崩溃。
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# config.BACKEND_DIR (测试环境取绝对路径)
BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_schema_before_seed_migration(tmp_path, monkeypatch):
    """构造一个含有旧版 plugins 表（无 source 列）的残缺库，验证 main.py 能否顺利升级并启动。"""
    db_path = tmp_path / "mfkagent.db"
    
    # 构造残缺旧库：plugins 表缺失 source 列
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE plugins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plugin_id VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            version VARCHAR(50),
            description TEXT,
            author VARCHAR(200),
            status VARCHAR(20),
            config JSON,
            created_at DATETIME,
            updated_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()

    # 指向残缺库
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")

    # 以子进程模拟 main.py 启动（直接导入 main 会触发大量副作用和端口绑定）
    # 设置一个能快速退出的环境变量，比如 --help 或让它启动后立刻关闭？
    # 更好的方式是单独导入 _ensure_schema 和后续的 seed，这里我们验证 main 导入期不出错即可。
    
    # 在这个子进程里：我们只需导入 main 模块，它的模块级代码会执行启动序列
    # (create_all -> _ensure_schema -> seed_default_plugins)
    cmd = [
        sys.executable, "-c", 
        "import os; os.environ['DATABASE_URL'] = 'sqlite:///" + db_path.as_posix() + "'; "
        "import sys; sys.path.insert(0, str(r'" + str(BACKEND_DIR) + "')); "
        "from app.core.config import settings; "
        "import main"
    ]
    
    # 执行，若失败会抛出 subprocess.CalledProcessError
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    assert res.returncode == 0, f"main.py 导入失败（启动崩溃）：\n{res.stderr}\n{res.stdout}"
    
    # 验证库是否被升级并插入了内置插件
    conn = sqlite3.connect(db_path)
    # 检查 source 列
    cursor = conn.execute("PRAGMA table_info(plugins)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "source" in columns, "迁移未生效，source 列未创建"
    
        # 检查 seed 是否成功写入数据（内置插件）
    count = conn.execute("SELECT COUNT(*) FROM plugins").fetchone()[0]
    assert count > 0, f"Seed 未写入内置插件。stdout: {res.stdout}, stderr: {res.stderr}"
    conn.close()
