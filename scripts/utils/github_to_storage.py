#!/usr/bin/env python3
"""
GitHub 仓库文件批量导入脚本

功能：
1. 通过 Git 克隆仓库（Git 自动处理认证）
2. 从本地克隆的仓库批量导入文件到 assets 目录
3. 支持批量导入和单个文件导入
4. 支持指定目标目录，保持原有目录结构
5. 可选择保留或清理克隆的仓库

使用示例：
    # 批量导入整个目录到 assets
    python scripts/github_to_storage.py \
        --repo https://github.com/username/repo.git \
        --source-path docs/knowledge \
        --target-dir assets/knowledge

    # 导入单个文件
    python scripts/github_to_storage.py \
        --repo https://github.com/username/repo.git \
        --source-path docs/knowledge/example.pdf \
        --target-dir assets/knowledge \
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


class FileCopier:
    """文件复制器"""

    def copy_from_local(self, local_path: str, target_path: str) -> bool:
        """
        从本地克隆目录复制文件到目标目录

        Args:
            local_path: 本地文件路径
            target_path: 目标文件路径（包含目录结构）

        Returns:
            是否成功
        """
        try:
            print(f"  📤 复制中: {target_path}")

            # 确保目标目录存在
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            # 复制文件
            shutil.copy2(local_path, target_path)
            print(f"  ✅ 复制成功: {target_path}")
            return True
        except Exception as e:
            print(f"  ❌ 复制失败: {e}")
            return False

    def check_file_exists(self, target_path: str) -> bool:
        """
        检查目标文件是否已存在

        Args:
            target_path: 目标文件路径

        Returns:
            是否存在
        """
        return os.path.exists(target_path)


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
    target_dir: str,
    skip_existing: bool = False
):
    """
    批量复制文件到目标目录

    Args:
        local_clone_dir: 本地克隆的仓库路径
        source_path: 源目录路径（相对于仓库根目录）
        target_dir: 目标目录路径
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始批量复制")
    print(f"   源路径: {source_path}")
    print(f"   目标目录: {target_dir}")
    print(f"   跳过已存在: {skip_existing}\n")

    copier = FileCopier()

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

    # 批量复制
    for relative_file in relative_files:
        local_file_path = os.path.join(full_source_path, relative_file)
        target_path = os.path.join(target_dir, relative_file)

        # 检查是否跳过
        if skip_existing and copier.check_file_exists(target_path):
            print(f"  ⏭️  跳过（已存在）: {relative_file}")
            skip_count += 1
            continue

        # 复制
        if copier.copy_from_local(local_file_path, target_path):
            success_count += 1
        else:
            fail_count += 1

    # 汇总
    print(f"\n📊 复制完成")
    print(f"   成功: {success_count}")
    print(f"   跳过: {skip_count}")
    print(f"   失败: {fail_count}")
    print(f"   总计: {len(relative_files)}")


def single_upload(
    local_clone_dir: str,
    source_path: str,
    target_dir: str,
    skip_existing: bool = False
):
    """
    复制单个文件

    Args:
        local_clone_dir: 本地克隆的仓库路径
        source_path: 源文件路径（相对于仓库根目录）
        target_dir: 目标目录路径
        skip_existing: 是否跳过已存在的文件
    """
    print(f"\n🚀 开始复制单个文件")
    print(f"   源文件: {source_path}")
    print(f"   目标目录: {target_dir}")
    print(f"   跳过已存在: {skip_existing}\n")

    copier = FileCopier()

    # 构建完整的源文件路径
    full_source_path = os.path.join(local_clone_dir, source_path)

    if not os.path.exists(full_source_path):
        print(f"❌ 文件不存在: {full_source_path}")
        return

    if not os.path.isfile(full_source_path):
        print(f"❌ 不是文件: {full_source_path}")
        return

    # 构建目标路径
    filename = os.path.basename(source_path)
    target_path = os.path.join(target_dir, filename)

    # 检查是否跳过
    if skip_existing and copier.check_file_exists(target_path):
        print(f"⏭️  文件已存在，跳过复制: {target_path}")
        return

    # 复制
    if copier.copy_from_local(full_source_path, target_path):
        print(f"\n✅ 复制成功: {target_path}")
    else:
        print(f"\n❌ 复制失败")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 仓库文件批量导入到 assets 目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 批量导入目录
  python scripts/github_to_storage.py \\
      --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \\
      --source-path 知识库资料001 \\
      --target-dir assets/knowledge

  # 导入单个文件
  python scripts/github_to_storage.py \\
      --repo https://github.com/zzh-zzh66/coze-agent-private-data.git \\
      --source-path 知识库资料001/example.pdf \\
      --target-dir assets/knowledge \\
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
        "--target-dir",
        required=True,
        help="目标目录路径，如: assets/knowledge"
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="GitHub 分支名，默认: main"
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="复制单个文件（默认为批量复制目录）"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="跳过已存在的文件"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时克隆的仓库（默认复制完成后删除）"
    )

    args = parser.parse_args()

    # 确保目标目录路径
    target_dir = args.target_dir.rstrip("/")
    source_path = args.source_path.strip("/")

    # 克隆仓库
    try:
        local_clone_dir = clone_repo(args.repo, args.branch)
    except Exception as e:
        print(f"❌ 克隆仓库失败: {e}")
        sys.exit(1)

    # 执行复制
    try:
        if args.single_file:
            single_upload(
                local_clone_dir=local_clone_dir,
                source_path=source_path,
                target_dir=target_dir,
                skip_existing=args.skip_existing
            )
        else:
            batch_upload(
                local_clone_dir=local_clone_dir,
                source_path=source_path,
                target_dir=target_dir,
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
