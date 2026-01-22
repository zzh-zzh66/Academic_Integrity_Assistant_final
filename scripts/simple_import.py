#!/usr/bin/env python3
"""
简化的知识库导入脚本（用于快速测试）
"""

import os
import sys
from typing import List
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
DATASET_NAME = "academic_integrity"
BATCH_SIZE = 10  # 每批导入 10 个文件

def read_file_content(file_path: str) -> str:
    """读取文件内容"""
    try:
        file_obj = File(url=file_path, file_type="document")
        content = FileOps.extract_text(file_obj)

        if not content or len(content) < 10:
            print(f"  ⚠️  文件内容过短: {len(content) if content else 0} 字符")
            return None

        error_markers = ['[解析失败]', '[FileOps Error]', 'File is not a zip file']
        if any(marker in content for marker in error_markers):
            print(f"  ⚠️  文件包含错误信息")
            return None

        return content
    except Exception as e:
        print(f"  ⚠️  读取文件失败: {e}")
        return None

def list_files(assets_dir: str, max_files: int = 50) -> List[str]:
    """扫描目录下的文件（限制数量）"""
    files = []
    assets_path = Path(assets_dir)

    for file_path in assets_path.rglob("*"):
        if file_path.is_file() and len(files) < max_files:
            ext = file_path.suffix.lower()
            if ext in {'.txt', '.md', '.pdf', '.docx'}:
                if not file_path.name.startswith('~') and not file_path.name.endswith('.crdownload'):
                    files.append(str(file_path))

    return files

def main():
    print(f"🚀 开始导入知识库")
    print(f"   目录: {ASSETS_DIR}")
    print(f"   数据集: {DATASET_NAME}")
    print(f"   批次大小: {BATCH_SIZE}\n")

    # 初始化客户端
    client = KnowledgeClient(config=Config())

    # 列出文件
    files = list_files(ASSETS_DIR, max_files=50)
    print(f"✅ 找到 {len(files)} 个文件\n")

    if not files:
        print("❌ 未找到任何文件")
        return

    # 读取文件
    documents = []
    for file_path in files:
        print(f"📖 读取文件: {os.path.relpath(file_path, ASSETS_DIR)}")
        content = read_file_content(file_path)

        if content:
            documents.append(KnowledgeDocument(
                source=DataSourceType.TEXT,
                raw_data=content
            ))
            print(f"  ✅ 成功 (长度: {len(content)} 字符)")
        else:
            print(f"  ❌ 失败")

    print(f"\n📊 成功读取 {len(documents)} 个文件\n")

    if not documents:
        print("❌ 没有有效文件可导入")
        return

    # 分批导入
    for i in range(0, len(documents), BATCH_SIZE):
        batch_docs = documents[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"📤 导入第 {batch_num}/{total_batches} 批 ({len(batch_docs)} 个文件)...")

        try:
            response = client.add_documents(
                documents=batch_docs,
                table_name=DATASET_NAME
            )

            if response.code == 0:
                print(f"  ✅ 成功: {len(response.doc_ids)} 个文件")
            else:
                print(f"  ❌ 失败: {response.msg}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")

    print(f"\n🎉 导入完成！")

    # 测试检索
    print(f"\n🧪 测试检索功能")
    test_query = "科研诚信"
    print(f"   查询: {test_query}")

    try:
        response = client.search(query=test_query, top_k=3)
        if response.code == 0 and response.chunks:
            print(f"  ✅ 检索成功: 找到 {len(response.chunks)} 个结果")
            for i, chunk in enumerate(response.chunks, 1):
                print(f"     {i}. 分数: {chunk.score:.4f}, 内容: {chunk.content[:80]}...")
        else:
            print(f"  ❌ 检索失败")
    except Exception as e:
        print(f"  ❌ 异常: {e}")

if __name__ == "__main__":
    main()
