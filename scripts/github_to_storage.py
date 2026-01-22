#!/usr/bin/env python3
"""
GitHub 仓库文件批量导入对象存储脚本

功能：
1. 从公开 GitHub 仓库批量导入文件到对象存储
2. 支持批量导入和单个文件导入
3. 支持指定目标目录，保持原有目录结构

使用示例：
    # 批量导入整个目录
    python scripts/github_to_storage.py \
        --repo username/repo \
        --source-path docs/knowledge \
        --target-prefix coze_knowledge_origin/test

    # 导入单个文件
    python scripts/github_to_storage.py \
        --repo username/repo \
        --source-path docs/knowledge/example.pdf \
        --target-prefix coze_knowledge_origin/test \
        --single-file
"""

import argparse
import os
import sys
from typing import List, Dict, Optional
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from coze_coding_dev_sdk.s3 import S3SyncStorage


class GitHubRepoFetcher:
    """GitHub 仓库文件获取器"""

    GITHUB_API_BASE = "https://api.github.com"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(self, repo: str, branch: str = "main"):
        """
        初始化 GitHub 仓库获取器

        Args:
            repo: 仓库格式 username/repo_name
            branch: 分支名，默认 main
        """
        self.repo = repo
        self.branch = branch

    def get_directory_contents(self, path: str = "") -> List[Dict]:
        """
        获取目录内容（递归获取所有文件）

        Args:
            path: 目录路径，空字符串表示根目录

        Returns:
            文件列表，每个文件包含 name, path, size, download_url 等信息
        """
        url = f"{self.GITHUB_API_BASE}/repos/{self.repo}/contents/{path}"
        if path:
            url += f"?ref={self.branch}"
        else:
            url += f"?ref={self.branch}"

        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            contents = response.json()

            all_files = []
            for item in contents:
                if item["type"] == "file":
                    all_files.append(item)
                elif item["type"] == "dir":
                    # 递归获取子目录文件
                    sub_files = self.get_directory_contents(item["path"])
                    all_files.extend(sub_files)

            return all_files

        except Exception as e:
            print(f"❌ 获取目录内容失败: {e}")
            return []

    def get_file_info(self, path: str) -> Optional[Dict]:
        """
        获取单个文件信息

        Args:
            path: 文件路径

        Returns:
            文件信息字典
        """
        url = f"{self.GITHUB_API_BASE}/repos/{self.repo}/contents/{path}?ref={self.branch}"

        try:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取文件信息失败: {e}")
            return None

    def get_raw_url(self, path: str) -> str:
        """
        获取文件的原始下载 URL

        Args:
            path: 文件路径

        Returns:
            原始文件 URL
        """
        return f"{self.GITHUB_RAW_BASE}/{self.repo}/{self.branch}/{path}"


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

    def upload_from_github(self, raw_url: str, target_key: str) -> bool:
        """
        从 GitHub URL 上传文件到对象存储

        Args:
            raw_url: GitHub 原始文件 URL
            target_key: 目标对象键（包含目录结构）

        Returns:
            是否成功
        """
        try:
            print(f"  📤 上传中: {target_key}")
            key = self.storage.upload_from_url(url=raw_url, bucket=None)
            print(f"  ✅ 上传成功: {key}")
            return True
        except Exception as e:
            print(f"  ❌ 上传失败: {e}")
            return False

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


def batch_upload(
    repo: str,
    source_path: str,
    target_prefix: str,
    branch: str = "main",
    skip_existing: bool = False
):
    """
    批量上传目录

    Args:
        repo: 仓库格式 username/repo_name
        source_path: 源目录路径
        target_prefix: 目标前缀
        branch: 分支名
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始批量上传")
    print(f"   仓库: {repo}")
    print(f"   源路径: {source_path}")
    print(f"   目标前缀: {target_prefix}")
    print(f"   分支: {branch}")
    print(f"   跳过已存在: {skip_existing}\n")

    fetcher = GitHubRepoFetcher(repo, branch)
    uploader = StorageUploader()

    # 获取目录内容
    print("📂 正在获取目录内容...")
    files = fetcher.get_directory_contents(source_path)

    if not files:
        print("⚠️  未找到任何文件")
        return

    print(f"📋 找到 {len(files)} 个文件\n")

    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0

    # 批量上传
    for file_info in files:
        source_file_path = file_info["path"]
        # 保持相对路径
        relative_path = source_file_path.replace(source_path, "").lstrip("/")
        target_key = f"{target_prefix}/{relative_path}" if target_prefix else relative_path

        # 检查是否跳过
        if skip_existing and uploader.check_file_exists(target_key):
            print(f"  ⏭️  跳过（已存在）: {target_key}")
            skip_count += 1
            continue

        # 获取原始 URL
        raw_url = fetcher.get_raw_url(source_file_path)

        # 上传
        if uploader.upload_from_github(raw_url, target_key):
            success_count += 1
        else:
            fail_count += 1

    # 汇总
    print(f"\n📊 上传完成")
    print(f"   成功: {success_count}")
    print(f"   跳过: {skip_count}")
    print(f"   失败: {fail_count}")
    print(f"   总计: {len(files)}")


def single_upload(
    repo: str,
    source_path: str,
    target_prefix: str,
    branch: str = "main",
    skip_existing: bool = False
):
    """
    上传单个文件

    Args:
        repo: 仓库格式 username/repo_name
        source_path: 源文件路径
        target_prefix: 目标前缀
        branch: 分支名
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始上传单个文件")
    print(f"   仓库: {repo}")
    print(f"   源文件: {source_path}")
    print(f"   目标前缀: {target_prefix}")
    print(f"   分支: {branch}")
    print(f"   跳过已存在: {skip_existing}\n")

    fetcher = GitHubRepoFetcher(repo, branch)
    uploader = StorageUploader()

    # 获取文件信息
    print("📋 正在获取文件信息...")
    file_info = fetcher.get_file_info(source_path)

    if not file_info:
        print("❌ 未找到文件")
        return

    # 构建目标键
    filename = os.path.basename(source_path)
    target_key = f"{target_prefix}/{filename}" if target_prefix else filename

    # 检查是否跳过
    if skip_existing and uploader.check_file_exists(target_key):
        print(f"⏭️  文件已存在，跳过上传: {target_key}")
        return

    # 获取原始 URL
    raw_url = fetcher.get_raw_url(source_path)

    # 上传
    if uploader.upload_from_github(raw_url, target_key):
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
      --repo username/repo \\
      --source-path docs/knowledge \\
      --target-prefix coze_knowledge_origin/test

  # 导入单个文件
  python scripts/github_to_storage.py \\
      --repo username/repo \\
      --source-path docs/knowledge/example.pdf \\
      --target-prefix coze_knowledge_origin/test \\
      --single-file
        """
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub 仓库，格式: username/repo_name"
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

    args = parser.parse_args()

    # 确保目标前缀不以 / 开头或结尾
    target_prefix = args.target_prefix.strip("/")
    source_path = args.source_path.strip("/")

    # 执行上传
    if args.single_file:
        single_upload(
            repo=args.repo,
            source_path=source_path,
            target_prefix=target_prefix,
            branch=args.branch,
            skip_existing=args.skip_existing
        )
    else:
        batch_upload(
            repo=args.repo,
            source_path=source_path,
            target_prefix=target_prefix,
            branch=args.branch,
            skip_existing=args.skip_existing
        )


if __name__ == "__main__":
    main()
