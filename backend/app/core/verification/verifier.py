"""Verifier — 验证调度器：按工具名路由到策略，未知工具默认通过。

Runtime 接入点：工具执行完成后，对本轮成功执行的动作调用
verifier.verify_all(records, project_path)，得到 VerificationResult 列表；
Runtime 据此决定继续 / 注入重试反馈。
"""

from typing import List, Optional

from app.core.verification.models import VerificationResult
from app.core.verification.strategies import VERIFIERS, default_verify


class Verifier:
    """工具结果验证器。"""

    def verify(self, record: dict, project_path: Optional[str] = None) -> VerificationResult:
        """验证单个工具 record（executor 返回格式）。"""
        fn = VERIFIERS.get(record.get("tool"))
        if fn is None:
            fn = default_verify
        result = fn(record, project_path)
        result.tool = record.get("tool") or result.tool
        result.tool_call_id = record.get("tool_call_id") or result.tool_call_id
        return result

    def verify_all(
        self,
        records: List[dict],
        project_path: Optional[str] = None,
    ) -> List[VerificationResult]:
        """批量验证；只验证 status == "success"（动作真实发生）的 record。"""
        results = []
        for record in records:
            if record.get("status") != "success":
                continue
            results.append(self.verify(record, project_path))
        return results


# 全局单例（无状态，可共享）
verifier = Verifier()


def get_verifier() -> Verifier:
    return verifier
