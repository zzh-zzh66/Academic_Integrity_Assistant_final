#!/usr/bin/env python3
"""
GitHub 仓库文件批量导入对象存储脚本

功能：
1. 通过 Git 克隆仓库（Git 自动处理认证）
2. 从本地克隆的仓库批量导入文件到对象存储
3. 支持批量导入和单个文件导入
4. 支持指定目标目录，保持原有目录结构
5. 支持清理临时克隆的仓库

使用示例：
    # 批量导入整个目录
    python scripts/github_to_storage.py \
        --repo https://github.com/username/repo.git \
        --source-path docs/knowledge \
        --target-prefix coze_knowledge_origin/test

    # 导入单个文件
    python scripts/github_to_storage.py \
        --repo https://github.com/username/repo.git \
        --source-path docs/knowledge/example.pdf \
        --target-prefix coze_knowledge_origin/test \
        --single-file
"""

import argparse
import os
import sys
import shutil
import tempfile
from typing import List, Dict, Optional
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from coze_coding_dev_sdk.s3 import S3SyncStorage


class StorageUploader:
    """对象存储上传器"""

    def __init__(self):
        """初始化对象存储客户端"""
        self.storage = S3SyncStorage(
            endpoint_url=os.getenv("COZE_BUCKET_ENDPOINT_URL"),
            access_key="",
            secret_key="",
            bucket_name=os.getenv("COZE_BUCKET_NAME"),
            region="cn-beijing",
        )

    def upload_from_local(self, local_path: str, target_key: str) -> bool:
        """
        从本地文件上传到对象存储

        Args:
            local_path: 本地文件路径
            target_key: 目标对象键（包含目录结构）

        Returns:
            是否成功
        """
        try:
            print(f"  📤 上传中: {target_key}")
            key = self.storage.stream_upload_file(
                fileobj=open(local_path, 'rb'),
                file_name=os.path.basename(local_path),
                content_type=self._get_content_type(local_path),
                bucket=None,
            )
            print(f"  ✅ 上传成功: {key}")
            return True
        except Exception as e:
            print(f"  ❌ 上传失败: {e}")
            return False

    def _get_content_type(self, file_path: str) -> str:
        """根据文件扩展名获取 Content-Type"""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.html': 'text/html',
            '.json': 'application/json',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
        }
        return content_types.get(ext, 'application/octet-stream')

    def check_file_exists(self, key: str) -> bool:
        """
        检查文件是否已存在

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        try:
            return self.storage.file_exists(file_key=key, bucket=None)
        except Exception:
            return False


def clone_repo(repo_url: str, branch: str = "main") -> str:
    """
    克隆 GitHub 仓库到临时目录

    Args:
        repo_url: 仓库 URL
        branch: 分支名

    Returns:
        本地克隆路径
    """
    temp_dir = tempfile.mkdtemp(prefix="github_clone_")
    print(f"📥 正在克隆仓库到临时目录: {temp_dir}")

    try:
        import subprocess
        result = subprocess.run(
            ["git", "clone", "-b", branch, "--depth", "1", repo_url, temp_dir],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            print(f"❌ 克隆失败: {result.stderr}")
            shutil.rmtree(temp_dir)
            raise Exception(f"Git clone failed: {result.stderr}")
        
        print(f"✅ 克隆成功")
        return temp_dir
    except Exception as e:
        shutil.rmtree(temp_dir)
        raise e


def get_all_files(directory: str) -> List[str]:
    """
    递归获取目录下所有文件

    Args:
        directory: 目录路径

    Returns:
        文件路径列表（相对路径）
    """
    files = []
    base_path = Path(directory)
    for item in base_path.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(base_path)
            files.append(str(relative_path))
    return files


def batch_upload(
    local_clone_dir: str,
    source_path: str,
    target_prefix: str,
    skip_existing: bool = False
):
    """
    批量上传目录

    Args:
        local_clone_dir: 本地克隆的仓库路径
        source_path: 源目录路径（相对于仓库根目录）
        target_prefix: 目标前缀
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始批量上传")
    print(f"   源路径: {source_path}")
    print(f"   目标前缀: {target_prefix}")
    print(f"   跳过已存在: {skip_existing}\n")

    uploader = StorageUploader()

    # 构建完整的源目录路径
    full_source_path = os.path.join(local_clone_dir, source_path)

    if not os.path.exists(full_source_path):
        print(f"❌ 目录不存在: {full_source_path}")
        return

    if not os.path.isdir(full_source_path):
        print(f"❌ 不是目录: {full_source_path}")
        return

    # 获取所有文件
    print("📂 正在获取目录内容...")
    relative_files = get_all_files(full_source_path)

    if not relative_files:
        print("⚠️  未找到任何文件")
        return

    print(f"📋 找到 {len(relative_files)} 个文件\n")

    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0

    # 批量上传
    for relative_file in relative_files:
        local_file_path = os.path.join(full_source_path, relative_file)
        target_key = f"{target_prefix}/{relative_file}" if target_prefix else relative_file

        # 检查是否跳过
        if skip_existing and uploader.check_file_exists(target_key):
            print(f"  ⏭️  跳过（已存在）: {target_key}")
            skip_count += 1
            continue

        # 上传
        if uploader.upload_from_local(local_file_path, target_key):
            success_count += 1
        else:
            fail_count += 1

    # 汇总
    print(f"\n📊 上传完成")
    print(f"   成功: {success_count}")
    print(f"   跳过: {skip_count}")
    print(f"   失败: {fail_count}")
    print(f"   总计: {len(relative_files)}")


def single_upload(
    local_clone_dir: str,
    source_path: str,
    target_prefix: str,
    skip_existing: bool = False
):
    """
    上传单个文件

    Args:
        local_clone_dir: 本地克隆的仓库路径
        source_path: 源文件路径（相对于仓库根目录）
        target_prefix: 目标前缀
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始上传单个文件")
    print(f"   源文件: {source_path}")
    print(f"   目标前缀: {target_prefix}")
    print(f"   跳过已存在: {skip_existing}\n")

    uploader = StorageUploader()

    # 构建完整的源文件路径
    full_source_path = os.path.join(local_clone_dir, source_path)

    if not os.path.exists(full_source_path):
        print(f"❌ 文件不存在: {full_source_path}")
        return

    if not os.path.isfile(full_source_path):
        print(f"❌ 不是文件: {full_source_path}")
        return

    # 构建目标键
    filename = os.path.basename(source_path)
    target_key = f"{target_prefix}/{filename}" if target_prefix else filename

    # 检查是否跳过
    if skip_existing and uploader.check_file_exists(target_key):
        print(f"⏭️  文件已存在，跳过上传: {target_key}")
        return

    # 上传
    if uploader.upload_from_local(full_source_path, target_key):
        print(f"\n✅ 上传成功: {target_key}")
    else:
        print(f"\n❌ 上传失败")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 仓库文件批量导入对象存储",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 批量导入目录
  python scripts/github_to_storage.py \\
      --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \\
      --source-path 知识库资料001 \\
      --target-prefix coze_knowledge_origin/test

  # 导入单个文件
  python scripts/github_to_storage.py \\
      --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \\
      --source-path 知识库资料001/example.pdf \\
      --target-prefix coze_knowledge_origin/test \\
      --single-file
        """
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub 仓库 URL，格式: https://github.com/username/repo.git"
    )
    parser.add_argument(
        "--source-path",
        required=True,
        help="源文件或目录路径（相对于仓库根目录）"
    )
    parser.add_argument(
        "--target-prefix",
        required=True,
        help="对象存储目标前缀（目录），如: coze_knowledge_origin/test"
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="GitHub 分支名，默认: main"
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="上传单个文件（默认为批量上传目录）"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="跳过已存在的文件"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时克隆的仓库（默认上传完成后删除）"
    )

    args = parser.parse_args()

    # 确保目标前缀不以 / 开头或结尾
    target_prefix = args.target_prefix.strip("/")
    source_path = args.source_path.strip("/")

    # 克隆仓库
    try:
        local_clone_dir = clone_repo(args.repo, args.branch)
    except Exception as e:
        print(f"❌ 克隆仓库失败: {e}")
        sys.exit(1)

    # 执行上传
    try:
        if args.single_file:
            single_upload(
                local_clone_dir=local_clone_dir,
                source_path=source_path,
                target_prefix=target_prefix,
                skip_existing=args.skip_existing
            )
        else:
            batch_upload(
                local_clone_dir=local_clone_dir,
                source_path=source_path,
                target_prefix=target_prefix,
                skip_existing=args.skip_existing
            )
    finally:
        # 清理临时目录
        if not args.keep_temp:
            print(f"\n🧹 清理临时目录...")
            shutil.rmtree(local_clone_dir)
            print("✅ 清理完成")
        else:
            print(f"\n💡 临时目录保留在: {local_clone_dir}")


if __name__ == "__main__":
    main()
