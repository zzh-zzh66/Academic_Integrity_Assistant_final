#!/usr/bin/env python3
"""
测试术语预处理节点的功能
"""
import os
import sys
import json

# 添加项目根目录到 Python 路径
project_root = os.getenv("COZE_WORKSPACE_PATH")
if project_root:
    src_path = os.path.join(project_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from graphs.nodes.common import (
    _map_colloquial_to_standard,
    _expand_related_terms
)


def test_term_mapping():
    """
    测试术语映射功能
    """
    print("=" * 60)
    print("测试术语映射功能")
    print("=" * 60)

    # 读取术语映射表
    mapping_file = os.path.join(project_root, "assets/academic_integrity_term_mapping.json")
    with open(mapping_file, 'r', encoding='utf-8') as fd:
        term_mapping = json.load(fd)

    test_cases = [
        "什么是学术造假？",
        "找人代写论文算不算违规？",
        "科研诚信的基本要求是什么？",
        "我怀疑有人学术作弊",
        "买卖论文的后果是什么"
    ]

    for query in test_cases:
        print(f"\n📝 测试查询: {query}")

        # 步骤1：术语转化
        standard_terms = _map_colloquial_to_standard(query, term_mapping)
        print(f"   标准术语: {standard_terms}")

        # 步骤2：关联拓展
        expanded_terms = _expand_related_terms(standard_terms, term_mapping, max_depth=2)
        print(f"   扩展术语: {expanded_terms}")

        # 步骤3：语义增强
        action_elements = []
        object_elements = []
        for term in expanded_terms:
            if term in term_mapping:
                term_info = term_mapping[term]
                if "action_elements" in term_info:
                    action_elements.extend(term_info["action_elements"])
                if "object_elements" in term_info:
                    object_elements.extend(term_info["object_elements"])

        action_elements = list(set(action_elements))
        object_elements = list(set(object_elements))

        print(f"   行为要素: {action_elements[:5]}...")  # 只显示前5个
        print(f"   对象要素: {object_elements[:5]}...")  # 只显示前5个

        # 构建增强查询
        enhanced_query_parts = standard_terms + expanded_terms + action_elements + object_elements + [query]
        enhanced_query = " ".join(list(set(enhanced_query_parts)))
        print(f"   增强查询长度: {len(enhanced_query)} 字符")


if __name__ == "__main__":
    test_term_mapping()
