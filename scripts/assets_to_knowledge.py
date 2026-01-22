#!/usr/bin/env python3
"""
本地目录文件批量导入知识库脚本

功能：
1. 扫描本地 assets 目录下的所有文件
2. 读取文件内容并导入到知识库（向量数据库）
3. 保持目录结构，在知识库中创建对应的数据集
4. 避免重复导入（通过记录已导入文件）
5. 支持增量更新
6. 支持多种文件格式：.txt, .md, .pdf, .doc, .docx

使用示例：
    # 导入 assets 目录下的文件到知识库
    python scripts/assets_to_knowledge.py \
        --assets-dir assets/knowledge
"""

import argparse
import os
import sys
import json
from typing import List, Dict, Set
from pathlib import Path

# 添加项目根目录和 src 目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from coze_coding_dev_sdk import KnowledgeClient, Config
from coze_coding_dev_sdk.knowledge import KnowledgeDocument, DataSourceType

# 文件读取工具
from utils.file.file import FileOps, File


class AssetsToKnowledgeImporter:
    """本地目录到知识库的导入器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        '.txt', '.md', '.markdown',  # 文本文件
        '.pdf',  # PDF 文件
        '.doc', '.docx',  # Word 文档
    }

    def __init__(self):
        """初始化导入器"""
        self.knowledge_client = KnowledgeClient(config=Config())

        # 记录已导入文件的数据库路径
        self.import_record_file = "scripts/knowledge_import_record.json"
        self.imported_files: Dict[str, Set[str]] = self._load_import_record()

    def _load_import_record(self) -> Dict[str, Set[str]]:
        """加载已导入文件记录"""
        try:
            if os.path.exists(self.import_record_file):
                with open(self.import_record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 转换为 Set
                    return {k: set(v) for k, v in data.items()}
        except Exception as e:
            print(f"⚠️  加载导入记录失败: {e}")
        return {}

    def _save_import_record(self):
        """保存已导入文件记录"""
        try:
            # 转换 Set 为 List 以便 JSON 序列化
            data = {k: list(v) for k, v in self.imported_files.items()}
            with open(self.import_record_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存导入记录失败: {e}")

    def _get_dataset_name_from_path(self, file_path: str, assets_dir: str) -> str:
        """
        根据文件路径生成数据集名称

        Args:
            file_path: 文件路径（绝对路径）
            assets_dir: assets 目录路径

        Returns:
            数据集名称
        """
        # 计算相对路径
        rel_path = os.path.relpath(file_path, assets_dir)

        # 移除文件名，只保留目录
        parts = rel_path.split('/')[:-1]

        # 将目录名中的特殊字符替换为下划线
        dataset_name = '_'.join(parts).replace('-', '_').replace('.', '_')

        # 如果为空，使用默认名称
        if not dataset_name or dataset_name == '.':
            dataset_name = 'coze_doc_knowledge'

        return dataset_name

    def _read_file_content(self, file_path: str) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容文本
        """
        try:
            # 创建 File 对象
            file_obj = File(
                url=file_path,  # 使用本地路径作为 URL
                file_type="document"  # 标记为文档类型
            )
            content = FileOps.extract_text(file_obj)
            return content
        except Exception as e:
            print(f"  ⚠️  读取文件失败: {e}")
            return ""

    def list_files(self, assets_dir: str) -> List[str]:
        """
        扫描本地目录下的所有支持格式的文件

        Args:
            assets_dir: 目录路径

        Returns:
            文件路径列表（绝对路径）
        """
        print(f"🔍 正在扫描目录: {assets_dir}")

        if not os.path.exists(assets_dir):
            print(f"❌ 目录不存在: {assets_dir}")
            return []

        files = []
        assets_path = Path(assets_dir)

        # 递归遍历目录
        for file_path in assets_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    files.append(str(file_path))

        print(f"✅ 找到 {len(files)} 个文件\n")
        return files

    def import_to_knowledge(
        self,
        files: List[str],
        assets_dir: str,
        skip_existing: bool = True
    ):
        """
        将文件导入到知识库

        Args:
            files: 文件路径列表（绝对路径）
            assets_dir: assets 目录路径
            skip_existing: 是否跳过已导入的文件
        """
        print(f"\n🚀 开始导入到知识库")
        print(f"   总文件数: {len(files)}")
        print(f"   跳过已存在: {skip_existing}\n")

        # 按数据集分组
        dataset_files: Dict[str, List[str]] = {}
        for file_path in files:
            dataset_name = self._get_dataset_name_from_path(file_path, assets_dir)
            if dataset_name not in dataset_files:
                dataset_files[dataset_name] = []
            dataset_files[dataset_name].append(file_path)

        print(f"📋 分组为 {len(dataset_files)} 个数据集\n")

        # 统计
        success_count = 0
        skip_count = 0
        fail_count = 0

        # 按数据集导入
        for dataset_name, file_paths in dataset_files.items():
            print(f"\n📁 数据集: {dataset_name}")
            print(f"   文件数: {len(file_paths)}\n")

            # 筛选需要导入的文件
            files_to_import = []
            for file_path in file_paths:
                # 使用文件路径作为唯一标识
                file_key = os.path.relpath(file_path, assets_dir)
                # 检查是否已导入
                if skip_existing and dataset_name in self.imported_files and file_key in self.imported_files[dataset_name]:
                    print(f"  ⏭️  跳过（已导入）: {file_key}")
                    skip_count += 1
                else:
                    files_to_import.append((file_path, file_key))

            if not files_to_import:
                print("  ℹ️  没有需要导入的文件")
                continue

            # 构建文档列表
            documents = []
            for file_path, file_key in files_to_import:
                # 读取文件内容
                print(f"  📖 读取文件: {file_key}")
                content = self._read_file_content(file_path)

                if not content:
                    print(f"  ⚠️  文件内容为空: {file_key}")
                    fail_count += 1
                    continue

                # 构建文档
                documents.append(KnowledgeDocument(
                    source=DataSourceType.TEXT,  # 使用文本类型
                    raw_data=content  # 直接传入文本内容
                ))

            if not documents:
                continue

            # 导入到知识库
            try:
                print(f"  📤 正在导入 {len(documents)} 个文件...")
                response = self.knowledge_client.add_documents(
                    documents=documents,
                    table_name=dataset_name
                )

                if response.code == 0:
                    print(f"  ✅ 导入成功: {len(response.doc_ids)} 个文件")
                    success_count += len(documents)

                    # 更新导入记录
                    if dataset_name not in self.imported_files:
                        self.imported_files[dataset_name] = set()
                    for _, file_key in files_to_import:
                        self.imported_files[dataset_name].add(file_key)
                else:
                    print(f"  ❌ 导入失败: {response.msg}")
                    fail_count += len(documents)

            except Exception as e:
                print(f"  ❌ 导入异常: {e}")
                import traceback
                traceback.print_exc()
                fail_count += len(documents)

        # 保存导入记录
        self._save_import_record()

        # 汇总
        print(f"\n📊 导入完成")
        print(f"   成功: {success_count}")
        print(f"   跳过: {skip_count}")
        print(f"   失败: {fail_count}")
        print(f"   总计: {len(files)}")


def main():
    parser = argparse.ArgumentParser(
        description="本地目录文件批量导入知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入 assets 目录下的文件到知识库
  python scripts/assets_to_knowledge.py \\
      --assets-dir assets/knowledge

  # 强制重新导入所有文件
  python scripts/assets_to_knowledge.py \\
      --assets-dir assets/knowledge \\
      --force-import

  # 仅列出文件，不执行导入
  python scripts/assets_to_knowledge.py \\
      --assets-dir assets/knowledge \\
      --list-only
        """
    )

    parser.add_argument(
        "--assets-dir",
        required=True,
        help="本地目录路径，如: assets/knowledge"
    )
    parser.add_argument(
        "--force-import",
        action="store_true",
        help="强制导入所有文件（忽略已导入记录）"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="仅列出文件，不执行导入"
    )

    args = parser.parse_args()

    importer = AssetsToKnowledgeImporter()

    # 列出文件
    files = importer.list_files(args.assets_dir)

    if not files:
        print("❌ 未找到任何文件")
        sys.exit(1)

    # 仅列出模式
    if args.list_only:
        print("\n📋 文件列表:")
        for i, file_path in enumerate(files, 1):
            rel_path = os.path.relpath(file_path, args.assets_dir)
            dataset_name = importer._get_dataset_name_from_path(file_path, args.assets_dir)
            print(f"  {i}. [{dataset_name}] {rel_path}")
        return

    # 执行导入
    importer.import_to_knowledge(
        files=files,
        assets_dir=args.assets_dir,
        skip_existing=not args.force_import
    )


if __name__ == "__main__":
    main()
