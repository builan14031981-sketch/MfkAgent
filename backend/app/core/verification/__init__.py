"""Verification 模块 — Phase E4 基础验证框架。

Action → Observation → Verification → Decision → Finish / Retry
本阶段仅实现确定性程序验证（文件重读 / 命令退出码），不引入 LLM 判定。
"""

from app.core.verification.models import (
    VerificationResult,
    PASSED,
    FAILED,
    NEED_RETRY,
)
from app.core.verification.verifier import Verifier, verifier, get_verifier
from app.core.verification.strategies import VERIFIERS

__all__ = [
    "VerificationResult",
    "PASSED",
    "FAILED",
    "NEED_RETRY",
    "Verifier",
    "verifier",
    "get_verifier",
    "VERIFIERS",
]
