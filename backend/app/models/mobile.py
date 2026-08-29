"""移动端（安卓）配对设备模型 — MfkAgent 安卓端 M1/M2。

设计原则：
  - 独立新表，不修改任何已有核心表（与 SandboxAuditLog 同一套约定）
  - token 只存 sha256 哈希，明文仅在配对确认响应中出现一次
  - 桌面版（本机回环访问）不经过设备鉴权，本表存在与否不影响桌面行为
"""
from sqlalchemy import Column, Integer, String, DateTime

from app.core.database import Base


class PairedDevice(Base):
    """已配对的移动设备（一台手机一条记录，token 长期有效直至吊销）。"""

    __tablename__ = "paired_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(100), default="", nullable=False)
    # sha256(token) hex — 查询主键用，明文 token 不落库
    token_hash = Column(String(64), index=True, unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    # 0=正常 1=已吊销（吊销后 token 立即失效）
    revoked = Column(Integer, default=0, nullable=False)
