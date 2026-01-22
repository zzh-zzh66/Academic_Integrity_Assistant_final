#!/usr/bin/env python3
"""
将 assets/knowledge 目录下的所有文件导入到向量数据库
支持保持目录结构，跳过无法导入的文件（如 .doc 文件）
"""
import os
import sys
from pathlib import Path
from typing import List, Tuple, Set
from coze_coding_dev_sdk import KnowledgeClient, Config, KnowledgeDocument
from coze_coding_dev_sdk.knowledge.models import DataSourceType

# 添加 src 目录到 Python 路径
project_root = os.getenv("COZE_WORKSPACE_PATH")
if project_root:
    src_path = os.path.join(project_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from utils.file.file import FileOps
from utils.file.file import File


def collect_files(knowledge_dir: str) -> List[Tuple[str, str]]:
    """
    收集知识库目录下的所有文件，返回（文件路径，相对路径）列表
    
    Args:
        knowledge_dir: 知识库根目录
        
    Returns:
        List[Tuple[文件完整路径, 相对于knowledge_dir的路径]]
    """
    files = []
    knowledge_path = Path(knowledge_dir)
    
    if not knowledge_path.exists():
        print(f"❌ 目录不存在: {knowledge_dir}")
        return files
    
    skip_count = 0
    for file_path in knowledge_path.rglob("*"):
        # 跳过目录和特殊文件
        if not file_path.is_file():
            continue
        
        # 跳过临时文件
        if file_path.name.startswith("~$") or file_path.name.startswith("."):
            skip_count += 1
            continue
        
        # 跳过 .doc 文件（仅支持 .docx）
        if file_path.suffix.lower() == ".doc":
            skip_count += 1
            continue
        
        # 跳过图片文件（无法提取文本）
        if file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            skip_count += 1
            continue
        
        # 跳过 .crdownload 等未完成下载的文件
        if file_path.suffix.lower() in [".crdownload", ".tmp", ".part"]:
            skip_count += 1
            continue
        
        # 计算相对路径，用于保持目录结构
        relative_path = file_path.relative_to(knowledge_path)
        files.append((str(file_path), str(relative_path)))
    
    print(f"⏭️  已跳过 {skip_count} 个不支持的文件")
    
    return files


def extract_file_content(file_path: str) -> Tuple[bool, str]:
    """
    提取文件内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        Tuple[是否成功, 文件内容]
    """
    try:
        file_obj = File(url=file_path, file_type="document")
        content = FileOps.extract_text(file_obj)
        
        # 检查是否包含错误信息
        if not content or content.strip() == "":
            return False, ""
        
        if "failed to parse" in content.lower() or "error" in content.lower() and len(content) < 200:
            return False, content
        
        # 检查内容长度
        if len(content.strip()) < 10:
            return False, content
        
        return True, content
    except Exception as e:
        print(f"❌ 提取文件内容失败 {file_path}: {e}")
        return False, str(e)


def import_batch(client: KnowledgeClient, batch_data: List[Tuple[str, str]], table_name: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    批量导入文件
    
    Args:
        client: 知识库客户端
        batch_data: List[Tuple[文件路径, 相对路径]]
        table_name: 表名
        
    Returns:
        Tuple[成功的文档ID列表, 失败的文件列表]
    """
    success_ids = []
    failed_files = []
    
    documents = []
    file_paths = []
    
    for file_path, relative_path in batch_data:
        success, content = extract_file_content(file_path)
        
        if not success or not content:
            print(f"❌ 文件内容提取失败或内容为空，跳过: {relative_path}")
            failed_files.append((file_path, relative_path))
            continue
        
        # 添加文件路径信息以保持目录结构
        structured_content = f"[文件路径: {relative_path}]\n\n{content}"
        
        doc = KnowledgeDocument(
            source=DataSourceType.TEXT,
            raw_data=structured_content
        )
        documents.append(doc)
        file_paths.append((file_path, relative_path))
    
    if not documents:
        return success_ids, failed_files
    
    try:
        response = client.add_documents(
            documents=documents,
            table_name=table_name
        )
        
        if response.code == 0 and response.doc_ids:
            success_ids.extend(response.doc_ids)
            print(f"✅ 成功导入 {len(response.doc_ids)} 个文件")
        else:
            print(f"❌ 批量导入失败: {response.msg}")
            failed_files.extend(file_paths)
    except Exception as e:
        print(f"❌ 批量导入异常: {e}")
        failed_files.extend(file_paths)
    
    return success_ids, failed_files


def main():
    """主函数"""
    print("=" * 60)
    print("开始导入知识库文件")
    print("=" * 60)
    
    # 配置
    knowledge_dir = "assets/knowledge"
    table_name = "coze_doc_knowledge"
    batch_size = 10  # 减少批次大小，避免超时
    
    # 初始化客户端
    config = Config()
    client = KnowledgeClient(config=config)
    
    # 收集所有文件
    print(f"\n📁 扫描目录: {knowledge_dir}")
    files = collect_files(knowledge_dir)
    
    if not files:
        print("❌ 没有找到可导入的文件")
        return
    
    print(f"📊 共找到 {len(files)} 个文件")
    
    # 分批导入
    all_success_ids = []
    all_failed_files = []
    
    total_batches = (len(files) + batch_size - 1) // batch_size
    
    for i in range(0, len(files), batch_size):
        batch_num = i // batch_size + 1
        batch_data = files[i:i + batch_size]
        
        print(f"\n📦 处理批次 {batch_num}/{total_batches} ({len(batch_data)} 个文件)")
        
        success_ids, failed_files = import_batch(
            client=client,
            batch_data=batch_data,
            table_name=table_name
        )
        
        all_success_ids.extend(success_ids)
        all_failed_files.extend(failed_files)
    
    # 输出总结
    print("\n" + "=" * 60)
    print("导入完成！")
    print("=" * 60)
    print(f"✅ 成功导入: {len(all_success_ids)} 个文件")
    print(f"❌ 导入失败: {len(all_failed_files)} 个文件")
    
    if all_failed_files:
        print("\n失败的文件列表:")
        for file_path, relative_path in all_failed_files[:10]:  # 只显示前10个
            print(f"  - {relative_path}")
        if len(all_failed_files) > 10:
            print(f"  ... 还有 {len(all_failed_files) - 10} 个文件")
    
    # 保存成功的文档ID到文件，方便后续删除
    if all_success_ids:
        ids_file = "scripts/imported_doc_ids.txt"
        with open(ids_file, "w") as f:
            for doc_id in all_success_ids:
                f.write(f"{doc_id}\n")
        print(f"\n💾 成功的文档ID已保存到: {ids_file}")
    
    return all_success_ids, all_failed_files


if __name__ == "__main__":
    success_ids, failed_files = main()
