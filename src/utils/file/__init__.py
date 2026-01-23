"""
File module - 文件操作模块（已迁移到core/）

为了向后兼容，这里从core/重新导出。
"""

from ..core.file import File, FileOps, infer_file_category

__all__ = [
    "File",
    "FileOps",
    "infer_file_category",
]
