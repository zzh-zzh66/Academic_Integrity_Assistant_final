"""
Messages module - 消息模块（已迁移到integrations/）

为了向后兼容，这里从integrations/重新导出。
"""

from ..integrations.client import *
from ..integrations.server import *

__all__ = [
    # Client
    "create_message_from_dict",
    "ClientMessage",
    # Server
    "create_response",
    "ServerResponse",
]
