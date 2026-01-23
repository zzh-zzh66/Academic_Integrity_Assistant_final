#!/usr/bin/env python3
"""
对象存储文件批量导入知识库脚本

功能：
1. 扫描对象存储指定目录下的所有文件
2. 将文件 URI 导入到知识库（向量数据库）
3. 保持目录结构，在知识库中创建对应的数据集
4. 避免重复导入（通过记录已导入文件）
5. 支持增量更新

使用示例：
    # 导入对象存储目录到知识库
    python scripts/storage_to_knowledge.py \
        --prefix coze_knowledge_origin/test
"""

import argparse
import os
import sys
import json
from typing import List, Dict, Set
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from coze_coding_dev_sdk.s3 import S3SyncStorage
from coze_coding_dev_sdk import KnowledgeClient, Config
from coze_coding_dev_sdk.knowledge import KnowledgeDocument, DataSourceType


class StorageToKnowledgeImporter:
    """对象存储到知识库的导入器"""

    def __init__(self):
        """初始化导入器"""
        self.storage = S3SyncStorage(
            endpoint_url=os.getenv("COZE_BUCKET_ENDPOINT_URL"),
            access_key="",
            secret_key="",
            bucket_name=os.getenv("COZE_BUCKET_NAME"),
            region="cn-beijing",
        )
        
        self.bucket_name = os.getenv("COZE_BUCKET_NAME")
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

    def _get_dataset_name_from_path(self, file_path: str) -> str:
        """
        根据文件路径生成数据集名称
        
        Args:
            file_path: 文件路径（不含 bucket 名称）
            
        Returns:
            数据集名称
        """
        # 移除前缀，保留目录结构作为数据集名
        # 例如：coze_knowledge_origin/test/subdir/file.pdf -> coze_knowledge_origin_test_subdir
        parts = file_path.split('/')
        
        # 移除文件名
        parts = parts[:-1]
        
        # 将目录名中的特殊字符替换为下划线
        dataset_name = '_'.join(parts).replace('-', '_').replace('.', '_')
        
        # 如果为空，使用默认名称
        if not dataset_name or dataset_name == '':
            dataset_name = 'coze_doc_knowledge'
        
        return dataset_name

    def list_storage_files(self, prefix: str) -> List[str]:
        """
        列出对象存储中指定前缀下的所有文件
        
        Args:
            prefix: 前缀路径
            
        Returns:
            文件路径列表
        """
        print(f"🔍 正在扫描对象存储目录: {prefix}")
        
        files = []
        continuation_token = None
        
        while True:
            result = self.storage.list_files(
                prefix=prefix,
                bucket=None,
                max_keys=1000,
                continuation_token=continuation_token
            )
            
            if result["keys"]:
                files.extend(result["keys"])
            
            if not result["is_truncated"]:
                break
                
            continuation_token = result["next_continuation_token"]
        
        print(f"✅ 找到 {len(files)} 个文件\n")
        return files

    def import_to_knowledge(
        self,
        files: List[str],
        skip_existing: bool = True
    ):
        """
        将文件导入到知识库
        
        Args:
            files: 文件路径列表
            skip_existing: 是否跳过已导入的文件
        """
        print(f"\n🚀 开始导入到知识库")
        print(f"   总文件数: {len(files)}")
        print(f"   跳过已存在: {skip_existing}\n")

        # 按数据集分组
        dataset_files: Dict[str, List[str]] = {}
        for file_path in files:
            dataset_name = self._get_dataset_name_from_path(file_path)
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
                # 检查是否已导入
                if skip_existing and dataset_name in self.imported_files and file_path in self.imported_files[dataset_name]:
                    print(f"  ⏭️  跳过（已导入）: {file_path}")
                    skip_count += 1
                else:
                    files_to_import.append(file_path)

            if not files_to_import:
                print("  ℹ️  没有需要导入的文件")
                continue

            # 构建文档列表
            documents = []
            for file_path in files_to_import:
                try:
                    # 生成签名 URL（有效期 1 小时）
                    signed_url = self.storage.generate_presigned_url(
                        key=file_path,
                        expire_time=3600
                    )
                    documents.append(KnowledgeDocument(
                        source=DataSourceType.URL,  # 使用 URL 类型
                        url=signed_url  # 使用签名 URL
                    ))
                except Exception as e:
                    print(f"  ⚠️  生成签名 URL 失败: {file_path}, 错误: {e}")

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
                    self.imported_files[dataset_name].update(files_to_import)
                else:
                    print(f"  ❌ 导入失败: {response.msg}")
                    fail_count += len(documents)
                    
            except Exception as e:
                print(f"  ❌ 导入异常: {e}")
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
        description="对象存储文件批量导入知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入对象存储目录到知识库
  python scripts/storage_to_knowledge.py \\
      --prefix coze_knowledge_origin/test

  # 强制重新导入所有文件
  python scripts/storage_to_knowledge.py \\
      --prefix coze_knowledge_origin/test \\
      --force-import
        """
    )

    parser.add_argument(
        "--prefix",
        required=True,
        help="对象存储前缀路径，如: coze_knowledge_origin/test"
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

    importer = StorageToKnowledgeImporter()

    # 列出文件
    files = importer.list_storage_files(args.prefix)

    if not files:
        print("❌ 未找到任何文件")
        sys.exit(1)

    # 仅列出模式
    if args.list_only:
        print("\n📋 文件列表:")
        for i, file_path in enumerate(files, 1):
            dataset_name = importer._get_dataset_name_from_path(file_path)
            print(f"  {i}. [{dataset_name}] {file_path}")
        return

    # 执行导入
    importer.import_to_knowledge(
        files=files,
        skip_existing=not args.force_import
    )


if __name__ == "__main__":
    main()
