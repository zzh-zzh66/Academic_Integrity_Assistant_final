import os
import json
import re
from typing import Optional
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    IntentRecognitionInput,
    IntentRecognitionOutput,
    TermPreprocessingInput,
    TermPreprocessingOutput,
    KnowledgeRetrievalInput,
    KnowledgeRetrievalOutput,
    ResponseGenerationInput,
    ResponseGenerationOutput
)


def intent_recognition_node(
    state: IntentRecognitionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> IntentRecognitionOutput:
    """
    title: 意图识别
    desc: 识别用户输入的意图类型（咨询类/行为判断类/混合类），并提取关键词和行为分析信息
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({"user_query": state.user_query})
    
    # 调用大语言模型
    client = LLMClient(ctx=ctx)
    
    messages = [
        {"role": "system", "content": sp},
        {"role": "user", "content": user_prompt_content}
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.0),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 1500),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        response_text = response_text.strip()
        
        # 解析响应（使用直接文本匹配，而不是JSON解析）
        intent_type = "咨询类"  # 默认值
        extracted_keywords = []
        behavior_analysis = None
        
        # 解析意图类型
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 解析意图类型
            if line.startswith("意图类型："):
                type_text = line.replace("意图类型：", "").strip()
                if "行为判断" in type_text or "判断" in type_text:
                    intent_type = "行为判断类"
                elif "混合" in type_text:
                    intent_type = "混合类"
                else:
                    intent_type = "咨询类"
            
            # 解析关键词
            elif line.startswith("关键词："):
                keywords_text = line.replace("关键词：", "").strip()
                if keywords_text:
                    # 按逗号分隔关键词
                    extracted_keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
            
            # 解析行为分析
            elif line.startswith("主体："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["主体"] = line.replace("主体：", "").strip()
            elif line.startswith("动作："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["动作"] = line.replace("动作：", "").strip()
            elif line.startswith("对象："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["对象"] = line.replace("对象：", "").strip()
        
        # 如果没有成功解析，使用关键词匹配进行辅助判断
        if intent_type == "咨询类" and len(extracted_keywords) == 0:
            query_lower = state.user_query.lower()
            if any(word in query_lower for word in ["是否", "违规", "合规", "允许", "可以吗", "违法", "违反"]):
                intent_type = "行为判断类"
        
        return IntentRecognitionOutput(
            intent_type=intent_type,
            extracted_keywords=extracted_keywords,
            behavior_analysis=behavior_analysis
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return IntentRecognitionOutput(
            intent_type="咨询类",
            extracted_keywords=[],
            behavior_analysis=None
        )


def knowledge_retrieval_node(
    state: KnowledgeRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> KnowledgeRetrievalOutput:
    """
    title: 知识库检索
    desc: 根据意图类型和关键词检索学术道德规范相关内容
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        # 构建检索查询
        query = state.user_query
        
        # 如果有提取的关键词，也可以加入检索
        if state.extracted_keywords:
            keywords_str = " ".join(state.extracted_keywords)
            query = f"{query} {keywords_str}"
        
        # 执行检索
        response = client.search(
            query=query,
            top_k=5,
            min_score=0.5
        )
        
        # 处理检索结果
        retrieval_results = []
        if response.code == 0 and response.chunks:
            for chunk in response.chunks:
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id
                })
        
        return KnowledgeRetrievalOutput(
            retrieval_results=retrieval_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return KnowledgeRetrievalOutput(
            retrieval_results=[]
        )


def extract_file_name_from_content(content: str) -> str:
    """
    从知识库内容中提取文件名
    
    Args:
        content: 知识库检索返回的内容
        
    Returns:
        文件名称
    """
    # 匹配 [文件路径: xxx/yyy.pdf] 格式
    match = re.search(r'\[文件路径:\s*[^\]]*?([^/\\\[\]]+\.(?:pdf|docx|txt))\]', content)
    if match:
        return match.group(1)
    return ""


def expand_content_around_chunk(chunk_content: str, target_length: int) -> str:
    """
    扩展 chunk 内容，扩展到语义完整单元
    
    Args:
        chunk_content: 原始 chunk 内容
        target_length: 目标长度（字符数）
    
    Returns:
        扩展后的内容
    """
    # 如果内容已经足够长，直接返回
    if len(chunk_content) >= target_length * 0.8:
        return chunk_content
    
    # 尝试按段落扩展
    paragraphs = re.split(r'\n\n+', chunk_content)
    
    # 如果只有一个段落或无法分割，尝试按句子扩展
    if len(paragraphs) <= 1:
        # 按句子分割（句号、问号、感叹号）
        sentences = re.split(r'([。！？])', chunk_content)
        
        # 重构句子列表
        full_sentences = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                full_sentences.append(sentences[i] + sentences[i + 1])
        
        # 如果有多个句子，尝试扩展
        if len(full_sentences) > 1:
            # 尝试扩展到目标长度
            expanded = chunk_content
            sentence_count = len(full_sentences)
            
            # 从中心向两端扩展
            center_idx = sentence_count // 2
            result_sentences = full_sentences
            
            # 如果原始内容不是从第一个句子开始的，尝试扩展
            if chunk_content.startswith(full_sentences[0]):
                # 从第一个句子开始，向后扩展
                expanded_text = ""
                for i, sentence in enumerate(result_sentences):
                    expanded_text += sentence
                    if len(expanded_text) >= target_length:
                        return expanded_text[:target_length]
                return expanded_text
            else:
                # 尝试扩展到目标长度
                return chunk_content
        else:
            return chunk_content
    else:
        # 有多个段落，尝试扩展到目标长度
        expanded = ""
        for para in paragraphs:
            expanded += para + "\n\n"
            if len(expanded) >= target_length:
                # 截断到目标长度
                result = expanded[:target_length]
                # 确保在段落边界截断
                last_newline = result.rfind("\n\n")
                if last_newline > target_length * 0.5:
                    result = result[:last_newline]
                return result.strip()
        return expanded.strip()
    
    return chunk_content


def response_generation_node(
    state: ResponseGenerationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ResponseGenerationOutput:
    """
    title: 响应生成
    desc: 根据意图类型和知识库检索结果，按照模板生成结构化响应
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "intent_type": state.intent_type,
        "retrieval_results": state.retrieval_results,
        "behavior_analysis": state.behavior_analysis
    })
    
    # 调用大语言模型
    client = LLMClient(ctx=ctx)
    
    messages = [
        {"role": "system", "content": sp},
        {"role": "user", "content": user_prompt_content}
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.3),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 4000),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        return ResponseGenerationOutput(
            formatted_response=response_text
        )
        
    except Exception as e:
        # 发生错误时返回默认响应
        fallback_response = f"抱歉，处理您的请求时遇到了问题。请稍后重试，或重新描述您的问题。\n\n原始问题：{state.user_query}"
        return ResponseGenerationOutput(
            formatted_response=fallback_response
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
