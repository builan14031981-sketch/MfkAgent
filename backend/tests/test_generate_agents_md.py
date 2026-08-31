"""scripts/generate_agents_md.py 生成 AGENTS.md 的验收测试（派工单 G①）。

对应派工单验收点：
1. 脚本在"干净环境"（仅标准库）可运行，能生成 AGENTS.md；
2. 生成的 AGENTS.md 覆盖 构建/测试命令、架构要点、非显性约束 三大块，且命令/路径与仓库一致；
3. 幂等：重跑输出 hash 一致；
4. 仓库根已提交的 AGENTS.md 与脚本生成结果完全一致（脚本是唯一事实来源）。

实现：以子进程方式调用脚本本体（`--output` 输出到临时目录），不触碰仓库根、无副作用。
"""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_agents_md.py"

# 正文必须出现的关键内容标记（覆盖派工单要求的三大块）
_MARKERS = [
    # 构建 / 测试 / 启动命令
    "pytest tests/ -q",
    "python main.py",
    "npm run build",
    "npm run dev",
    # 架构要点
    "core/tool_runtime",
    "backend/app",
    "agent_runtime",
    "frontend/src",
    # 非显性约束
    "backend/.venv",
    "chromadb",
    "worktree",
    "备份",
]


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )


def test_script_exists_and_pure_stdlib() -> None:
    """脚本存在且不依赖任何第三方库（干净环境可运行）。"""
    assert SCRIPT.exists(), f"脚本缺失: {SCRIPT}"
    src = SCRIPT.read_text(encoding="utf-8")
    for mod in ("fastapi", "pytest", "sqlalchemy", "requests", "uvicorn"):
        assert f"import {mod}" not in src, f"脚本不应依赖第三方库 {mod}"
        assert f"from {mod} " not in src, f"脚本不应依赖第三方库 {mod}"


def test_generate_to_temp_contains_required_sections(tmp_path: Path) -> None:
    """脚本可运行，生成的 AGENTS.md 覆盖三大块关键内容。"""
    out = tmp_path / "AGENTS.md"
    r = _run_script("--output", str(out))
    assert r.returncode == 0, f"脚本退出码 {r.returncode}: {r.stderr}"
    content = out.read_text(encoding="utf-8")
    for marker in _MARKERS:
        assert marker in content, f"生成的 AGENTS.md 缺少关键内容: {marker}"
    # 显式核对三大标题
    for section in ("构建 / 测试 / 启动命令", "架构要点", "非显性约束"):
        assert section in content, f"缺少章节: {section}"


def test_generate_is_idempotent(tmp_path: Path) -> None:
    """重跑输出完全一致（幂等，可重复生成）。"""
    out = tmp_path / "AGENTS.md"
    r1 = _run_script("--output", str(out))
    assert r1.returncode == 0, r1.stderr
    h1 = hashlib.sha256(out.read_bytes()).hexdigest()
    r2 = _run_script("--output", str(out))
    assert r2.returncode == 0, r2.stderr
    h2 = hashlib.sha256(out.read_bytes()).hexdigest()
    assert h1 == h2, "重跑生成结果不一致（应幂等）"


def test_repo_agents_md_matches_script(tmp_path: Path) -> None:
    """仓库根已提交的 AGENTS.md 与脚本生成结果完全一致（脚本是唯一事实来源）。"""
    committed = REPO_ROOT / "AGENTS.md"
    assert committed.exists(), "仓库根应存在已提交的 AGENTS.md"
    out = tmp_path / "AGENTS.md"
    r = _run_script("--output", str(out))
    assert r.returncode == 0, r.stderr
    assert committed.read_text(encoding="utf-8") == out.read_text(encoding="utf-8"), (
        "AGENTS.md 与脚本生成结果不一致——请用 scripts/generate_agents_md.py 重新生成后提交"
    )
