#!/usr/bin/env python3
"""
带测试功能的知识库导入脚本

功能：
1. 扫描本地 assets/knowledge 目录下的所有文件
2. 读取文件内容并导入到知识库
3. 保留目录结构
4. 测试知识库导入效果
5. 如果效果不好，删除导入记录并重试
6. 循环直到成功

使用示例：
    python scripts/import_knowledge_with_test.py \
        --assets-dir assets/knowledge
"""

import argparse
import os
import sys
import json
import time
from typing import List, Dict, Set
from pathlib import Path

# 添加项目根目录和 src 目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from coze_coding_dev_sdk import KnowledgeClient, Config
from coze_coding_dev_sdk.knowledge import KnowledgeDocument, DataSourceType
from utils.file.file import FileOps, File


class KnowledgeImporterWithTest:
    """带测试功能的知识库导入器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        '.txt', '.md', '.markdown',
        '.pdf',
        '.docx',
    }

    # 测试查询列表
    TEST_QUERIES = [
        "科研诚信建设规范是什么",
        "什么是学术不端行为",
        "论文署名的规范要求有哪些",
        "科研失信行为如何处理",
        "人工智能在科研中的应用规范"
    ]

    def __init__(self):
        """初始化导入器"""
        self.knowledge_client = KnowledgeClient(config=Config())

        # 记录已导入文件
        self.import_record_file = "scripts/knowledge_import_record.json"
        self.imported_files: Dict[str, Set[str]] = self._load_import_record()

        # 记录测试结果
        self.test_result_file = "scripts/knowledge_test_results.json"

    def _load_import_record(self) -> Dict[str, Set[str]]:
        """加载已导入文件记录"""
        try:
            if os.path.exists(self.import_record_file):
                with open(self.import_record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {k: set(v) for k, v in data.items()}
        except Exception as e:
            print(f"⚠️  加载导入记录失败: {e}")
        return {}

    def _save_import_record(self):
        """保存已导入文件记录"""
        try:
            data = {k: list(v) for k, v in self.imported_files.items()}
            with open(self.import_record_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存导入记录失败: {e}")

    def _clear_import_record(self):
        """清空导入记录"""
        self.imported_files = {}
        self._save_import_record()
        print("🗑️  已清空导入记录")

    def _get_dataset_name_from_path(self, file_path: str, assets_dir: str) -> str:
        """根据文件路径生成数据集名称"""
        rel_path = os.path.relpath(file_path, assets_dir)
        parts = rel_path.split('/')[:-1]
        dataset_name = '_'.join(parts).replace('-', '_').replace('.', '_')
        if not dataset_name or dataset_name == '.':
            dataset_name = 'coze_doc_knowledge'
        return dataset_name

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            file_obj = File(url=file_path, file_type="document")
            content = FileOps.extract_text(file_obj)

            if not content or len(content) < 10:
                print(f"  ⚠️  文件内容过短: {len(content) if content else 0} 字符")
                return None

            error_markers = ['[解析失败]', '[FileOps Error]', 'File is not a zip file']
            if any(marker in content for marker in error_markers):
                print(f"  ⚠️  文件包含错误信息: {content[:100]}")
                return None

            return content
        except Exception as e:
            print(f"  ⚠️  读取文件失败: {e}")
            return None

    def list_files(self, assets_dir: str) -> List[str]:
        """扫描目录下的所有支持格式的文件"""
        print(f"🔍 正在扫描目录: {assets_dir}")

        if not os.path.exists(assets_dir):
            print(f"❌ 目录不存在: {assets_dir}")
            return []

        files = []
        skipped_files = []
        assets_path = Path(assets_dir)

        for file_path in assets_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    # 跳过临时文件
                    if not file_path.name.startswith('~') and not file_path.name.endswith('.crdownload'):
                        files.append(str(file_path))
                elif ext == '.doc':
                    skipped_files.append(str(file_path))

        print(f"✅ 找到 {len(files)} 个有效文件")

        if skipped_files:
            print(f"⚠️  跳过 {len(skipped_files)} 个 .doc 文件（仅支持 .docx 格式）")

        print()
        return files

    def import_to_knowledge(
        self,
        files: List[str],
        assets_dir: str,
        skip_existing: bool = False
    ) -> bool:
        """
        将文件导入到知识库

        Returns:
            是否成功导入（有文件导入成功即为 True）
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
                file_key = os.path.relpath(file_path, assets_dir)
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
            successful_files = []
            failed_files = []

            for file_path, file_key in files_to_import:
                print(f"  📖 读取文件: {file_key}")
                content = self._read_file_content(file_path)

                if content is None:
                    print(f"  ⚠️  文件读取失败或无效: {file_key}")
                    failed_files.append(file_key)
                    fail_count += 1
                    continue

                documents.append(KnowledgeDocument(
                    source=DataSourceType.TEXT,
                    raw_data=content
                ))
                successful_files.append(file_key)
                print(f"  ✅ 文件读取成功: {file_key} (长度: {len(content)} 字符)")

            if not documents:
                print(f"  ℹ️  该数据集没有有效文件可导入")
                continue

            # 分批导入
            batch_size = 50
            total_batches = (len(documents) + batch_size - 1) // batch_size

            for batch_idx in range(0, len(documents), batch_size):
                batch_docs = documents[batch_idx:batch_idx + batch_size]
                batch_files = successful_files[batch_idx:batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1

                try:
                    print(f"  📤 正在导入第 {batch_num}/{total_batches} 批 ({len(batch_docs)} 个文件)...")
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
                        print(f"  ❌ 批次 {batch_num} 导入失败: {response.msg}")
                        fail_count += len(batch_docs)

                except Exception as e:
                    print(f"  ❌ 批次 {batch_num} 导入异常: {e}")
                    import traceback
                    traceback.print_exc()
                    fail_count += len(batch_docs)

        # 保存导入记录
        self._save_import_record()

        # 汇总
        print(f"\n📊 导入完成")
        print(f"   成功: {success_count}")
        print(f"   跳过: {skip_count}")
        print(f"   失败: {fail_count}")
        print(f"   总计: {len(files)}")

        return success_count > 0

    def test_knowledge_quality(self) -> Dict:
        """
        测试知识库导入效果

        Returns:
            测试结果字典
        """
        print(f"\n🧪 开始测试知识库效果")
        print(f"   测试查询数: {len(self.TEST_QUERIES)}\n")

        test_results = {
            "total_queries": len(self.TEST_QUERIES),
            "successful_queries": 0,
            "failed_queries": 0,
            "total_results": 0,
            "average_score": 0.0,
            "query_details": []
        }

        total_score = 0.0

        for i, query in enumerate(self.TEST_QUERIES, 1):
            print(f"\n[{i}/{len(self.TEST_QUERIES)}] 测试查询: {query}")

            try:
                response = self.knowledge_client.search(
                    query=query,
                    top_k=5,
                    min_score=0.0
                )

                if response.code == 0 and response.chunks:
                    print(f"  ✅ 检索成功: 找到 {len(response.chunks)} 个结果")

                    # 计算平均分数
                    scores = [chunk.score for chunk in response.chunks]
                    avg_score = sum(scores) / len(scores)
                    total_score += avg_score

                    # 显示第一个结果的内容预览
                    if response.chunks:
                        content_preview = response.chunks[0].content[:100]
                        print(f"  📄 第一个结果: {content_preview}...")
                        print(f"  📊 平均分数: {avg_score:.4f}")

                    test_results["successful_queries"] += 1
                    test_results["total_results"] += len(response.chunks)
                    test_results["query_details"].append({
                        "query": query,
                        "success": True,
                        "result_count": len(response.chunks),
                        "average_score": avg_score
                    })
                else:
                    print(f"  ❌ 检索失败: {response.msg if hasattr(response, 'msg') else '未找到结果'}")
                    test_results["failed_queries"] += 1
                    test_results["query_details"].append({
                        "query": query,
                        "success": False,
                        "result_count": 0,
                        "average_score": 0.0
                    })
            except Exception as e:
                print(f"  ❌ 测试异常: {e}")
                test_results["failed_queries"] += 1
                test_results["query_details"].append({
                    "query": query,
                    "success": False,
                    "result_count": 0,
                    "average_score": 0.0,
                    "error": str(e)
                })

        # 计算总体平均分数
        if test_results["successful_queries"] > 0:
            test_results["average_score"] = total_score / test_results["successful_queries"]

        # 保存测试结果
        with open(self.test_result_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)

        # 汇总
        print(f"\n📊 测试结果汇总:")
        print(f"   成功查询: {test_results['successful_queries']}/{test_results['total_queries']}")
        print(f"   失败查询: {test_results['failed_queries']}/{test_results['total_queries']}")
        print(f"   总结果数: {test_results['total_results']}")
        print(f"   平均分数: {test_results['average_score']:.4f}")

        return test_results

    def is_test_passed(self, test_results: Dict) -> bool:
        """
        判断测试是否通过

        判断标准：
        1. 成功查询数 >= 3（至少 60% 的查询有结果）
        2. 平均分数 >= 0.3
        """
        success_rate = test_results["successful_queries"] / test_results["total_queries"]
        avg_score = test_results["average_score"]

        print(f"\n✅ 测试通过标准:")
        print(f"   成功率: {success_rate:.2%} (要求 >= 60%)")
        print(f"   平均分数: {avg_score:.4f} (要求 >= 0.3)")

        if success_rate >= 0.6 and avg_score >= 0.3:
            print(f"\n🎉 测试通过！")
            return True
        else:
            print(f"\n❌ 测试未通过，需要重新导入")
            return False

    def run_with_retry(
        self,
        assets_dir: str,
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        """
        带重试机制的导入和测试

        Args:
            assets_dir: 目录路径
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        print("=" * 60)
        print("🚀 开始知识库导入（带测试和重试机制）")
        print("=" * 60)
        print(f"   目录: {assets_dir}")
        print(f"   最大重试次数: {max_retries}")
        print(f"   重试延迟: {retry_delay} 秒")
        print("=" * 60)

        # 列出文件
        files = self.list_files(assets_dir)

        if not files:
            print("❌ 未找到任何文件")
            return False

        retry_count = 0
        while retry_count <= max_retries:
            print(f"\n{'='*60}")
            print(f"📌 第 {retry_count + 1} 次尝试")
            print(f"{'='*60}")

            # 清空导入记录（第一次除外）
            if retry_count > 0:
                print(f"\n🔄 重新导入：清空之前的导入记录")
                self._clear_import_record()
                time.sleep(retry_delay)

            # 执行导入
            import_success = self.import_to_knowledge(
                files=files,
                assets_dir=assets_dir,
                skip_existing=False  # 不跳过已导入的文件
            )

            if not import_success:
                print(f"\n❌ 导入失败，没有成功导入任何文件")
                retry_count += 1
                continue

            # 测试效果
            test_results = self.test_knowledge_quality()

            # 判断是否通过
            if self.is_test_passed(test_results):
                print(f"\n{'='*60}")
                print(f"🎉 导入成功并通过测试！")
                print(f"{'='*60}")
                return True
            else:
                print(f"\n{'='*60}")
                print(f"❌ 测试未通过，准备重试...")
                print(f"{'='*60}")
                retry_count += 1

                if retry_count <= max_retries:
                    print(f"\n⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)

        # 达到最大重试次数
        print(f"\n{'='*60}")
        print(f"❌ 达到最大重试次数 ({max_retries})，导入失败")
        print(f"{'='*60}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="带测试功能的知识库导入脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入并测试（自动重试直到成功）
  python scripts/import_knowledge_with_test.py \\
      --assets-dir assets/knowledge

  # 设置最大重试次数
  python scripts/import_knowledge_with_test.py \\
      --assets-dir assets/knowledge \\
      --max-retries 5
        """
    )

    parser.add_argument(
        "--assets-dir",
        required=True,
        help="本地目录路径，如: assets/knowledge"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="最大重试次数（默认: 3）"
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=5,
        help="重试延迟（秒，默认: 5）"
    )

    args = parser.parse_args()

    importer = KnowledgeImporterWithTest()

    # 运行带重试的导入
    success = importer.run_with_retry(
        assets_dir=args.assets_dir,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )

    if success:
        print(f"\n✅ 任务完成！")
        sys.exit(0)
    else:
        print(f"\n❌ 任务失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
