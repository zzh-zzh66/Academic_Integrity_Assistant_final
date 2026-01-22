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
        '.docx',  # Word 文档（仅支持 .docx，不支持旧版 .doc）
    }

    # 排除的文件前缀（临时文件等）
    EXCLUDED_PREFIXES = {'~$', '.~', '._'}

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
            数据集名称（仅包含 ASCII 字符）
        """
        # 计算相对路径
        rel_path = os.path.relpath(file_path, assets_dir)

        # 移除文件名，只保留目录
        parts = rel_path.split('/')[:-1]

        # 将目录名中的中文字符转换为拼音，或使用默认值
        # 简化方案：将所有非 ASCII 字符替换为下划线
        dataset_name = '_'.join(parts)

        # 清理名称：只保留字母、数字、下划线和连字符
        import re
        dataset_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dataset_name)

        # 移除连续的下划线
        dataset_name = re.sub(r'_+', '_', dataset_name)

        # 移除首尾的下划线和连字符
        dataset_name = dataset_name.strip('_-')

        # 如果为空，使用默认名称
        if not dataset_name:
            dataset_name = 'coze_doc_knowledge'

        # 限制名称长度（有些系统可能有限制）
        if len(dataset_name) > 50:
            dataset_name = dataset_name[:50]

        return dataset_name

    def _read_file_content(self, file_path: str) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容文本，如果读取失败返回 None
        """
        try:
            # 创建 File 对象
            file_obj = File(
                url=file_path,  # 使用本地路径作为 URL
                file_type="document"  # 标记为文档类型
            )
            content = FileOps.extract_text(file_obj)

            # 检查内容是否有效
            if not content or len(content) < 10:
                print(f"  ⚠️  文件内容过短: {len(content) if content else 0} 字符")
                return None

            # 检查是否包含错误信息（更全面的检测）
            error_markers = [
                '[解析失败]', '[FileOps Error]', 'File is not a zip file',
                'fetching data failed', 'Coze Knowledge',
                'Failed to read document', 'Unsupported file format'
            ]
            content_lower = content.lower()
            if any(marker.lower() in content_lower for marker in error_markers):
                print(f"  ⚠️  文件包含错误信息")
                print(f"     错误内容预览: {content[:150]}...")
                return None

            # 检查是否为纯空白字符
            if not content.strip():
                print(f"  ⚠️  文件内容为空白")
                return None

            # 检查内容是否主要为特殊字符（可能是乱码）
            import re
            # 统计中文字符、英文字符和数字的数量
            text_chars = len(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9\s]', content))
            if text_chars / len(content) < 0.3:
                print(f"  ⚠️  文件内容异常（可能为乱码）")
                print(f"     有效字符比例: {text_chars/len(content):.2%}")
                return None

            return content
        except Exception as e:
            print(f"  ⚠️  读取文件失败: {e}")
            return None

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
        skipped_doc_files = []
        skipped_temp_files = []
        assets_path = Path(assets_dir)

        # 递归遍历目录
        for file_path in assets_path.rglob("*"):
            if file_path.is_file():
                file_name = file_path.name
                ext = file_path.suffix.lower()

                # 检查是否为临时文件
                if any(file_name.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
                    skipped_temp_files.append(str(file_path))
                    continue

                if ext in self.SUPPORTED_EXTENSIONS:
                    files.append(str(file_path))
                elif ext == '.doc':
                    # 跳过旧版 .doc 文件
                    skipped_doc_files.append(str(file_path))

        print(f"✅ 找到 {len(files)} 个文件")

        if skipped_doc_files:
            print(f"⚠️  跳过 {len(skipped_doc_files)} 个 .doc 文件（仅支持 .docx 格式）")
            if len(skipped_doc_files) <= 5:
                for f in skipped_doc_files:
                    print(f"     - {os.path.basename(f)}")
            else:
                for f in skipped_doc_files[:3]:
                    print(f"     - {os.path.basename(f)}")
                print(f"     ... 还有 {len(skipped_doc_files) - 3} 个文件")

        if skipped_temp_files:
            print(f"⚠️  跳过 {len(skipped_temp_files)} 个临时文件")
            if len(skipped_temp_files) <= 5:
                for f in skipped_temp_files:
                    print(f"     - {os.path.basename(f)}")
            else:
                for f in skipped_temp_files[:3]:
                    print(f"     - {os.path.basename(f)}")
                print(f"     ... 还有 {len(skipped_temp_files) - 3} 个文件")

        print()
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

            # 构建文档列表（只包含成功读取的文件）
            documents = []
            successful_files = []  # 记录成功读取的文件
            failed_files = []      # 记录读取失败的文件

            for file_path, file_key in files_to_import:
                # 读取文件内容
                print(f"  📖 读取文件: {file_key}")
                content = self._read_file_content(file_path)

                if content is None:
                    print(f"  ⚠️  文件读取失败或无效: {file_key}")
                    failed_files.append(file_key)
                    fail_count += 1
                    continue

                # 构建文档
                documents.append(KnowledgeDocument(
                    source=DataSourceType.TEXT,  # 使用文本类型
                    raw_data=content  # 直接传入文本内容
                ))
                successful_files.append(file_key)
                print(f"  ✅ 文件读取成功: {file_key} (长度: {len(content)} 字符)")

            if not documents:
                print(f"  ℹ️  该数据集没有有效文件可导入")
                print(f"     失败文件数: {len(failed_files)}")
                continue

            # 分批导入（每批最多 10 个文件，便于调试）
            batch_size = 10
            total_batches = (len(documents) + batch_size - 1) // batch_size

            for batch_idx in range(0, len(documents), batch_size):
                batch_docs = documents[batch_idx:batch_idx + batch_size]
                batch_files = successful_files[batch_idx:batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1

                # 导入到知识库
                try:
                    print(f"  📤 正在导入第 {batch_num}/{total_batches} 批 ({len(batch_docs)} 个文件)...")

                    # 调试：打印第一个文档的前 200 字符
                    if batch_docs and batch_docs[0].raw_data:
                        preview = batch_docs[0].raw_data[:200].replace('\n', ' ')
                        print(f"  🔍 调试信息 - 第一个文档内容预览: {preview}...")

                    response = self.knowledge_client.add_documents(
                        documents=batch_docs,
                        table_name=dataset_name
                    )

                    if response.code == 0:
                        print(f"  ✅ 批次 {batch_num} 导入成功: {len(response.doc_ids)} 个文件")
                        success_count += len(response.doc_ids)

                        # 更新导入记录
                        if dataset_name not in self.imported_files:
                            self.imported_files[dataset_name] = set()
                        self.imported_files[dataset_name].update(batch_files)
                    else:
                        print(f"  ❌ 批次 {batch_num} 导入失败")
                        print(f"     错误代码: {response.code}")
                        print(f"     错误信息: {response.msg}")

                        # 打印失败批次中的文件列表
                        print(f"     失败文件列表:")
                        for f in batch_files:
                            print(f"       - {f}")

                        fail_count += len(batch_docs)

                except Exception as e:
                    print(f"  ❌ 批次 {batch_num} 导入异常: {e}")
                    import traceback
                    traceback.print_exc()
                    fail_count += len(batch_docs)

            # 显示失败文件列表
            if failed_files:
                print(f"  ⚠️  读取失败的文件 ({len(failed_files)} 个):")
                for f in failed_files[:5]:  # 只显示前 5 个
                    print(f"     - {f}")
                if len(failed_files) > 5:
                    print(f"     ... 还有 {len(failed_files) - 5} 个文件")

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
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="测试模式：仅导入第一个文件用于调试"
    )

    args = parser.parse_args()

    importer = AssetsToKnowledgeImporter()

    # 列出文件
    files = importer.list_files(args.assets_dir)

    if not files:
        print("❌ 未找到任何文件")
        sys.exit(1)

    # 测试模式：只导入第一个文件
    if args.test_mode:
        print("\n🧪 测试模式：仅导入第一个文件")
        files = files[:1]

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
