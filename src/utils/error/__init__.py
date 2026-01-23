"""
Error module - 错误处理模块（已迁移到core/）

为了向后兼容，这里从core/重新导出。
"""

from ..core.exceptions import *
from ..core.codes import *
from ..core.error_classifier import ErrorClassifier, ErrorInfo, ErrorStats
from ..core.error_patterns import *

__all__ = [
    "VibeCodingError",
    "ErrorCode",
    "get_error_description",
    "classify_error",
    "ErrorClassifier",
    "ErrorInfo",
    "ErrorStats",
]
