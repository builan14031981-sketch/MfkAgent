"""Phase 8: MfkAgent 后端独立打包脚本（PyInstaller）

将 main.py 编译为免 Python 环境的独立可执行程序。
输出：dist/backend.exe（Windows 单文件，无控制台弹窗）

用法：
    python build_backend.py          # 默认 --onefile --noconsole
    python build_backend.py --onedir # 目录模式（启动更快，调试用）

依赖：
    pip install pyinstaller
"""

import os
import sys
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DIST_DIR = BACKEND_DIR / "dist"
BUILD_DIR = BACKEND_DIR / "build"
SPEC_FILE = BACKEND_DIR / "backend.spec"

# ── 隐藏导入（FastAPI / SQLAlchemy / langchain 等动态加载的模块）──
HIDDEN_IMPORTS = [
    # FastAPI / Starlette / Uvicorn
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "starlette",
    # SQLAlchemy
    "sqlalchemy.sql.default_comparator",
    "sqlalchemy.dialects.sqlite",
    # Pydantic
    "pydantic.deprecated.decorator",
    "pydantic",
    # LangChain
    "langchain",
    "langchain_openai",
    "langchain_community",
    # ChromaDB
    "chromadb",
    "chromadb.config",
    # httpx engines
    "httpx",
    # 项目内部模块
    "app",
    "app.api",
    "app.api.chat",
    "app.api.models",
    "app.api.agents",
    "app.api.memory",
    "app.api.memories",
    "app.api.projects",
    "app.api.settings",
    "app.api.backup",
    "app.api.knowledge",
    "app.api.fonts",
    "app.api.tools",
    "app.api.mcp",
    "app.api.workflows",
    "app.api.autotasks",
    "app.api.plugins",
    "app.api.trash",
    "app.api.greetings",
    "app.api.devtools",
    "app.api.runs",
    "app.core",
    "app.core.config",
    "app.core.database",
    "app.core.tokens",
    "app.core.path_utils",
    "app.core.model_providers",
    "app.core.tool_runtime",
    "app.core.tool_runtime.executor",
    "app.core.tool_runtime.approval",
    "app.core.tool_runtime.risk_engine",
    "app.core.tool_runtime.events",
    "app.core.tool_runtime.normalizer",
    "app.core.agent_runtime",
    "app.core.agent_runtime.agent",
    "app.core.agent_runtime.context",
    "app.core.agent_runtime.context_builder",
    "app.core.agent_runtime.router",
    "app.core.agent_runtime.recorder",
    "app.core.agent_runtime.states",
    "app.core.agent_runtime.personas",
    "app.core.agent_runtime.task_graph_state",
    "app.core.agent_runtime.model_context_config",
    "app.core.command_tools",
    "app.core.git_tools",
    "app.core.search_tools",
    "app.core.tools",
    "app.core.sandbox",
    "app.core.verification",
    "app.core.pagination",
    "app.core.errors",
    "app.core.port_manager",
    "app.core.task_graph",
    "app.core.task_graph.models",
    "app.services",
    "app.services.model",
    "app.services.tools",
    "app.services.plugin",
    "app.services.memory_extractor",
    "app.models",
    "app.models.agent",
]

# ── 数据文件（与 exe 同级或嵌入）──
def _collect_data_files():
    """收集需要随 exe 分发的数据文件。"""
    datas = []
    # .env 文件（若存在）
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        datas.append((str(env_file), "."))
    # 备份目录（空目录占位，PyInstaller 不打包空目录，运行时创建）
    return datas


def _build_pyinstaller_cmd(onefile: bool = True) -> list[str]:
    """构建 PyInstaller 命令行参数。"""
    datas = _collect_data_files()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "backend",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BACKEND_DIR),
        "--clean",
        "--noconsole",          # 无控制台弹窗
        "--noconfirm",          # 覆盖已有输出
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 隐藏导入
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # 数据文件
    for src, dst in datas:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # 入口文件
    cmd.append(str(BACKEND_DIR / "main.py"))

    return cmd


def build(onefile: bool = True):
    """执行 PyInstaller 打包。"""
    print(f"[build] 模式: {'--onefile' if onefile else '--onedir'}")
    print(f"[build] 输出目录: {DIST_DIR}")
    print(f"[build] 构建目录: {BUILD_DIR}")

    # 清理旧产物
    import shutil
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    for f in BACKEND_DIR.glob("*.spec"):
        if f.name != "backend.spec":
            f.unlink(missing_ok=True)

    cmd = _build_pyinstaller_cmd(onefile=onefile)
    print(f"[build] 命令: {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode == 0:
        exe = DIST_DIR / "backend.exe"
        if exe.exists():
            size_mb = exe.stat().st_size / (1024 * 1024)
            print(f"[build] 成功! → {exe} ({size_mb:.1f} MB)")
        else:
            print(f"[build] 成功! 输出见 {DIST_DIR}")
    else:
        print(f"[build] 失败 (exit code: {result.returncode})")
        sys.exit(result.returncode)


if __name__ == "__main__":
    onefile = "--onedir" not in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    build(onefile=onefile)