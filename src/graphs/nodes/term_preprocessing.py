import os
import json
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    TermPreprocessingInput,
    TermPreprocessingOutput
)


def term_preprocessing_node(
    state: TermPreprocessingInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TermPreprocessingOutput:
    """
    title: 术语预处理
    desc: 基于术语映射表进行术语转化、关联拓展和语义增强，提升知识库检索的准确性和召回率
    integrations: 无
    """
    ctx = runtime.context

    try:
        # 读取术语映射表
        mapping_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "assets/academic_integrity_term_mapping.json")

        if not os.path.exists(mapping_file):
            # 如果映射表不存在，返回原始查询
            return TermPreprocessingOutput(
                standard_terms=[],
                expanded_terms=[],
                action_elements=[],
                object_elements=[],
                enhanced_query=state.user_query,
                term_confidence=0.0
            )

        with open(mapping_file, 'r', encoding='utf-8') as fd:
            term_mapping = json.load(fd)

        # 合并用户查询和提取的关键词
        query_text = state.user_query
        if state.extracted_keywords:
            query_text += " " + " ".join(state.extracted_keywords)

        # === 步骤1：术语转化（口语化 → 标准化）===
        standard_terms = _map_colloquial_to_standard(query_text, term_mapping)

        # === 步骤2：关联拓展（related_terms 递归扩展）===
        expanded_terms = _expand_related_terms(standard_terms, term_mapping, max_depth=2)

        # === 步骤3：语义增强（action_elements + object_elements）===
        action_elements = []
        object_elements = []

        for term in expanded_terms:
            if term in term_mapping:
                term_info = term_mapping[term]
                if "action_elements" in term_info:
                    action_elements.extend(term_info["action_elements"])
                if "object_elements" in term_info:
                    object_elements.extend(term_info["object_elements"])

        # 去重
        action_elements = list(set(action_elements))
        object_elements = list(set(object_elements))

        # === 构建增强查询 ===
        enhanced_query_parts = []

        # 1. 添加标准术语
        if standard_terms:
            enhanced_query_parts.extend(standard_terms)

        # 2. 添加扩展术语
        if expanded_terms:
            enhanced_query_parts.extend(expanded_terms)

        # 3. 添加行为要素
        if action_elements:
            enhanced_query_parts.extend(action_elements)

        # 4. 添加对象要素
        if object_elements:
            enhanced_query_parts.extend(object_elements)

        # 5. 添加原始查询和关键词
        enhanced_query_parts.append(state.user_query)
        if state.extracted_keywords:
            enhanced_query_parts.extend(state.extracted_keywords)

        # 去重并构建最终查询
        enhanced_query_parts = list(set(enhanced_query_parts))
        enhanced_query = " ".join(enhanced_query_parts)

        # === 计算置信度 ===
        confidence = 0.0
        if standard_terms:
            confidence = 0.9  # 成功匹配到标准术语，置信度高
        elif state.extracted_keywords:
            confidence = 0.5  # 有关键词但未匹配到术语，置信度中等
        else:
            confidence = 0.0  # 无匹配，置信度低

        return TermPreprocessingOutput(
            standard_terms=standard_terms,
            expanded_terms=expanded_terms,
            action_elements=action_elements,
            object_elements=object_elements,
            enhanced_query=enhanced_query,
            term_confidence=confidence
        )

    except Exception as e:
        # 发生错误时返回原始查询
        return TermPreprocessingOutput(
            standard_terms=[],
            expanded_terms=[],
            action_elements=[],
            object_elements=[],
            enhanced_query=state.user_query,
            term_confidence=0.0
        )


def _map_colloquial_to_standard(query_text: str, term_mapping: dict) -> list:
    """
    将口语化术语映射到标准术语

    Args:
        query_text: 查询文本
        term_mapping: 术语映射表

    Returns:
        标准术语列表
    """
    standard_terms = []

    for term_name, term_info in term_mapping.items():
        # 检查标准术语本身（如果用户直接使用标准术语）
        if term_name in query_text:
            standard_terms.append(term_name)
            continue

        # 检查 colloquial_terms（口语化术语）
        colloquial_terms = term_info.get("colloquial_terms", [])
        for colloquial_term in colloquial_terms:
            if colloquial_term in query_text:
                standard_terms.append(term_name)
                break  # 匹配到一个就跳出

        # 检查 synonyms（同义词）
        synonyms = term_info.get("synonyms", [])
        for synonym in synonyms:
            if synonym in query_text:
                standard_terms.append(term_name)
                break  # 匹配到一个就跳出

        # 检查 action_elements（行为要素）
        action_elements = term_info.get("action_elements", [])
        for action in action_elements:
            if action in query_text:
                standard_terms.append(term_name)
                break  # 匹配到一个就跳出

        # 检查 object_elements（对象要素）
        object_elements = term_info.get("object_elements", [])
        for obj in object_elements:
            if obj in query_text:
                standard_terms.append(term_name)
                break  # 匹配到一个就跳出

    # 去重
    standard_terms = list(set(standard_terms))

    return standard_terms


def _expand_related_terms(standard_terms: list, term_mapping: dict, max_depth: int = 2) -> list:
    """
    关联拓展：递归获取相关术语

    Args:
        standard_terms: 标准术语列表
        term_mapping: 术语映射表
        max_depth: 递归深度

    Returns:
        扩展后的术语列表
    """
    expanded_terms = set(standard_terms)
    visited = set(standard_terms)

    def _expand(terms: list, depth: int):
        if depth >= max_depth:
            return

        new_terms = set()

        for term in terms:
            if term in term_mapping:
                related_terms = term_mapping[term].get("related_terms", [])
                for related_term in related_terms:
                    if related_term not in visited and related_term in term_mapping:
                        new_terms.add(related_term)
                        visited.add(related_term)
                        expanded_terms.add(related_term)

        # 递归扩展
        if new_terms:
            _expand(list(new_terms), depth + 1)

    _expand(standard_terms, 0)

    return list(expanded_terms)
