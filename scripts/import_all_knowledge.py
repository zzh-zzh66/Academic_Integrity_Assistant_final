#!/usr/bin/env python3
"""
完整导入所有文件到知识库
"""

import os
import sys
import json
import time
from typing import List, Dict
from pathlib import Path

# 添加项目根目录和 src 目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from coze_coding_dev_sdk import KnowledgeClient, Config
from coze_coding_dev_sdk.knowledge import KnowledgeDocument, DataSourceType
from utils.file.file import FileOps, File

# 配置
ASSETS_DIR = "assets/knowledge"
IMPORT_RECORD_FILE = "scripts/all_files_import_record.json"
BATCH_SIZE = 50

# 测试查询
TEST_QUERIES = [
    "科研诚信建设规范是什么",
    "什么是学术不端行为",
    "论文署名的规范要求有哪些",
    "科研失信行为如何处理",
    "人工智能在科研中的应用规范"
]

def read_file_content(file_path: str) -> str:
    """读取文件内容"""
    try:
        file_obj = File(url=file_path, file_type="document")
        content = FileOps.extract_text(file_obj)

        if not content or len(content) < 10:
            return None

        error_markers = ['[解析失败]', '[FileOps Error]', 'File is not a zip file']
        if any(marker in content for marker in error_markers):
            return None

        return content
    except Exception as e:
        return None

def get_dataset_name(file_path: str, assets_dir: str) -> str:
    """根据文件路径生成数据集名称（保留目录结构）"""
    rel_path = os.path.relpath(file_path, assets_dir)
    parts = rel_path.split('/')[:-1]
    dataset_name = '_'.join(parts).replace('-', '_').replace('.', '_')
    if not dataset_name or dataset_name == '.':
        dataset_name = 'coze_doc_knowledge'
    return dataset_name

def list_files(assets_dir: str) -> List[str]:
    """扫描所有有效文件"""
    files = []
    skipped = []
    assets_path = Path(assets_dir)

    for file_path in assets_path.rglob("*"):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in {'.txt', '.md', '.pdf', '.docx'}:
                if not file_path.name.startswith('~') and not file_path.name.endswith('.crdownload'):
                    files.append(str(file_path))
            elif ext == '.doc':
                skipped.append(str(file_path))

    print(f"✅ 找到 {len(files)} 个有效文件")
    if skipped:
        print(f"⚠️  跳过 {len(skipped)} 个 .doc 文件")

    return files

def load_import_record() -> Dict[str, set]:
    """加载导入记录"""
    try:
        if os.path.exists(IMPORT_RECORD_FILE):
            with open(IMPORT_RECORD_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {k: set(v) for k, v in data.items()}
    except Exception as e:
        print(f"⚠️  加载记录失败: {e}")
    return {}

def save_import_record(record: Dict[str, set]):
    """保存导入记录"""
    try:
        data = {k: list(v) for k, v in record.items()}
        with open(IMPORT_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  保存记录失败: {e}")

def test_knowledge(client: KnowledgeClient) -> Dict:
    """测试知识库效果"""
    print(f"\n🧪 测试知识库效果")

    results = {
        "total": len(TEST_QUERIES),
        "success": 0,
        "failed": 0,
        "total_chunks": 0,
        "avg_score": 0.0
    }

    total_score = 0.0

    for i, query in enumerate(TEST_QUERIES, 1):
        try:
            response = client.search(query=query, top_k=5)

            if response.code == 0 and response.chunks:
                print(f"  [{i}/{len(TEST_QUERIES)}] ✅ {query}: {len(response.chunks)} 个结果")
                scores = [chunk.score for chunk in response.chunks]
                avg_score = sum(scores) / len(scores)
                total_score += avg_score
                results["success"] += 1
                results["total_chunks"] += len(response.chunks)
            else:
                print(f"  [{i}/{len(TEST_QUERIES)}] ❌ {query}: 无结果")
                results["failed"] += 1
        except Exception as e:
            print(f"  [{i}/{len(TEST_QUERIES)}] ❌ {query}: 异常 ({e})")
            results["failed"] += 1

    if results["success"] > 0:
        results["avg_score"] = total_score / results["success"]

    print(f"\n📊 测试结果:")
    print(f"   成功: {results['success']}/{results['total']}")
    print(f"   失败: {results['failed']}/{results['total']}")
    print(f"   平均分数: {results['avg_score']:.4f}")

    return results

def main():
    print("=" * 60)
    print("🚀 开始导入所有文件到知识库")
    print("=" * 60)
    print(f"   目录: {ASSETS_DIR}")
    print(f"   批次大小: {BATCH_SIZE}")
    print("=" * 60)

    # 初始化客户端
    client = KnowledgeClient(config=Config())

    # 列出文件
    print(f"\n🔍 扫描文件...")
    files = list_files(ASSETS_DIR)

    if not files:
        print("❌ 未找到任何文件")
        return

    # 加载导入记录
    import_record = load_import_record()

    # 按数据集分组
    dataset_files: Dict[str, List[str]] = {}
    for file_path in files:
        dataset_name = get_dataset_name(file_path, ASSETS_DIR)
        if dataset_name not in dataset_files:
            dataset_files[dataset_name] = []
        dataset_files[dataset_name].append(file_path)

    print(f"\n📋 分组为 {len(dataset_files)} 个数据集")

    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0

    # 按数据集导入
    for idx, (dataset_name, file_paths) in enumerate(dataset_files.items(), 1):
        print(f"\n📁 [{idx}/{len(dataset_files)}] 数据集: {dataset_name}")
        print(f"   文件数: {len(file_paths)}")

        # 筛选需要导入的文件
        files_to_import = []
        for file_path in file_paths:
            file_key = os.path.relpath(file_path, ASSETS_DIR)
            if dataset_name in import_record and file_key in import_record[dataset_name]:
                skip_count += 1
            else:
                files_to_import.append((file_path, file_key))

        if not files_to_import:
            print(f"   ℹ️  全部已导入")
            continue

        # 读取文件
        documents = []
        successful_keys = []

        for file_path, file_key in files_to_import[:100]:  # 限制每个数据集最多 100 个文件
            content = read_file_content(file_path)
            if content:
                documents.append(KnowledgeDocument(source=DataSourceType.TEXT, raw_data=content))
                successful_keys.append(file_key)

        if not documents:
            print(f"   ⚠️  没有有效文件")
            continue

        print(f"   ✅ 成功读取 {len(documents)} 个文件")

        # 分批导入
        for i in range(0, len(documents), BATCH_SIZE):
            batch_docs = documents[i:i + BATCH_SIZE]
            batch_keys = successful_keys[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE

            try:
                response = client.add_documents(
                    documents=batch_docs,
                    table_name=dataset_name
                )

                if response.code == 0:
                    success_count += len(response.doc_ids)
                    print(f"   [{batch_num}/{total_batches}] ✅ 导入成功: {len(response.doc_ids)} 个文件")

                    # 更新记录
                    if dataset_name not in import_record:
                        import_record[dataset_name] = set()
                    import_record[dataset_name].update(batch_keys)
                    save_import_record(import_record)
                else:
                    fail_count += len(batch_docs)
                    print(f"   [{batch_num}/{total_batches}] ❌ 导入失败: {response.msg}")
            except Exception as e:
                fail_count += len(batch_docs)
                print(f"   [{batch_num}/{total_batches}] ❌ 异常: {e}")

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 导入汇总:")
    print(f"   成功: {success_count}")
    print(f"   跳过: {skip_count}")
    print(f"   失败: {fail_count}")
    print(f"   总计: {len(files)}")
    print(f"{'='*60}")

    # 测试效果
    test_results = test_knowledge(client)

    # 判断是否成功
    if test_results["success"] >= 3 and test_results["avg_score"] >= 0.3:
        print(f"\n{'='*60}")
        print(f"🎉 导入成功并通过测试！")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"⚠️  导入完成，但测试未通过")
        print(f"   建议: 检查数据集内容或增加测试查询")
        print(f"{'='*60}")

if __name__ == "__main__":
    main()
