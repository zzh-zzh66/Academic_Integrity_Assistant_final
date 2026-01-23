#!/usr/bin/env python3
"""
测试知识库搜索功能
"""
from coze_coding_dev_sdk import KnowledgeClient, Config

# 初始化客户端（不使用Context）
config = Config()
client = KnowledgeClient(config=config)

# 测试查询
test_queries = [
    "科研诚信",
    "学术不端行为",
    "署名问题",
    "论文发表规范",
    "数据造假"
]

print("=" * 60)
print("测试知识库搜索功能")
print("=" * 60)

for query in test_queries:
    print(f"\n🔍 查询: {query}")
    print("-" * 60)
    
    response = client.search(
        query=query,
        top_k=3,
        min_score=0.3
    )
    
    if response.code == 0 and response.chunks:
        print(f"✅ 找到 {len(response.chunks)} 条结果")
        for i, chunk in enumerate(response.chunks):
            print(f"\n结果 {i+1} (Score: {chunk.score:.4f}):")
            # 只显示前200个字符
            content_preview = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            print(f"  内容: {content_preview}")
            print(f"  文档ID: {chunk.doc_id}")
    else:
        print(f"❌ 未找到结果")
        if hasattr(response, 'msg') and response.msg:
            print(f"   错误信息: {response.msg}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
