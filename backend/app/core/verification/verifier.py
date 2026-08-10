"""Verifier — 验证调度器：按工具名路由到策略，未知工具默认通过。

Runtime 接入点：工具执行完成后，对本轮成功执行的动作调用
verifier.verify_all(records, project_path, chat_id)，得到 VerificationResult 列表；
Runtime 据此决定继续 / 注入重试反馈。

Verification Loop V1 集成：
  - verify_all 接受可选的 chat_id 参数
  - 自动跟踪重试次数，更新 VerificationResult.retry_count
  - 检测循环耗尽，设置 status 为 LOOP_EXHAUSTED
"""

from typing import List, Optional

from app.core.verification.models import VerificationResult, LOOP_EXHAUSTED
from app.core.verification.strategies import VERIFIERS, default_verify
from app.core.verification.loop import get_verification_loop


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
        chat_id: Optional[str] = None,
    ) -> List[VerificationResult]:
        """批量验证；只验证 status == "success"（动作真实发生）的 record。
        
        Verification Loop V1:
          - 如果提供 chat_id，自动跟踪重试次数
          - 更新每个结果的 retry_count
          - 检测循环耗尽，设置 status 为 LOOP_EXHAUSTED
        
        Args:
            records: 工具执行记录列表
            project_path: 项目路径（用于文件验证）
            chat_id: 会话 ID（用于循环跟踪）
            
        Returns:
            VerificationResult 列表
        """
        results = []
        loop = get_verification_loop(chat_id) if chat_id else None
        
        for record in records:
            if record.get("status") != "success":
                continue
            
            result = self.verify(record, project_path)
            
            # Verification Loop V1: 跟踪重试次数
            if loop and result.tool_call_id:
                # 如果验证失败（need_retry 或 failed），增加重试计数
                if not result.passed:
                    retry_count = loop.increment_retry(
                        result.tool_call_id,
                        tool=result.tool,
                        message=result.message
                    )
                    result.retry_count = retry_count
                    result.max_retries = loop.max_retries
                    
                    # 检测循环耗尽
                    if not loop.should_retry(result.tool_call_id):
                        result.status = LOOP_EXHAUSTED
                        result.message = f"[循环耗尽] {result.message} (已重试 {retry_count} 次)"
                else:
                    # 验证成功，重置该 tool_call_id 的重试计数
                    loop.reset(result.tool_call_id)
                    result.retry_count = 0
            
            results.append(result)
        
        return results


# 全局单例（无状态，可共享）
verifier = Verifier()


def get_verifier() -> Verifier:
    return verifier
