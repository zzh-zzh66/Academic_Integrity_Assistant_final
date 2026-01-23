"""
Runnable module - Runnable模块（已迁移到integrations/）

为了向后兼容，这里从integrations/重新导出。
"""

from ..integrations.wrapper import to_runnable

__all__ = ["to_runnable"]
