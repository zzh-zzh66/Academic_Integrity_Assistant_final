import os
import json
import re
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    ConsultProcessInput,
    ConsultProcessOutput,
    ConsultRetrievalInput,
    ConsultRetrievalOutput,
    ConsultContextExpandInput,
    ConsultContextExpandOutput,
    ConsultRerankInput,
    ConsultRerankOutput,
    ConsultRetrievalLoopState,
    ConsultRetrievalLoopStartInput,
    ConsultRetrievalLoopStartOutput,
    ConsultRetrievalLoopEndInput,
    ConsultRetrievalLoopEndOutput,
    ComplexityInput,
    ComplexityOutput,
    ConsultQueryOptimizeInput,
    ConsultQueryOptimizeOutput,
    RerankInput,
    RerankOutput,
    ContextExtractInput,
    ContextExtractOutput,
    ImprovementAnalysisInput,
    ImprovementAnalysisOutput,
    ConsultRetrievalLoopNodeInput,
    ConsultRetrievalLoopNodeOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks,
    get_fallback_response
)


def consult_process_node(
    state: ConsultProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultProcessOutput:
    """
    title: 咨询类意图处理
    desc: 分析和优化咨询类问题，提取核心关键词和咨询焦点，使用术语预处理节点的输出增强查询
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

    # 获取术语预处理节点的输出（通过 state 参数）
    enhanced_query = state.enhanced_query if state.enhanced_query else state.user_query
    standard_terms = state.standard_terms
    expanded_terms = state.expanded_terms
    action_elements = state.action_elements
    object_elements = state.object_elements

    # 构建增强的用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "extracted_keywords": state.extracted_keywords,
        "enhanced_query": enhanced_query,
        "standard_terms": standard_terms,
        "expanded_terms": expanded_terms,
        "action_elements": action_elements,
        "object_elements": object_elements
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
            max_completion_tokens=llm_config.get("max_completion_tokens", 1000),
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
        
        # 解析JSON响应
        result = {
            "refined_query": state.user_query,
            "refined_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "consult_focus": "其他"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "refined_query" in parsed_result:
                    result["refined_query"] = parsed_result["refined_query"]
                if "refined_keywords" in parsed_result:
                    result["refined_keywords"] = parsed_result["refined_keywords"]
                if "consult_focus" in parsed_result:
                    result["consult_focus"] = parsed_result["consult_focus"]
            except json.JSONDecodeError:
                pass
        
        return ConsultProcessOutput(
            refined_query=result["refined_query"],
            refined_keywords=result["refined_keywords"],
            consult_focus=result["consult_focus"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ConsultProcessOutput(
            refined_query=state.user_query,
            refined_keywords=state.extracted_keywords if state.extracted_keywords else [],
            consult_focus="其他"
        )


def consult_retrieval_node(
    state: ConsultRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalOutput:
    """
    title: 咨询类知识库检索
    desc: 根据咨询类意图检索学术道德规范相关内容，获取更详细的说明和定义
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        # 构建检索查询
        query = state.user_query
        
        # 优先使用优化后的查询
        if state.refined_query:
            query = state.refined_query
        
        # 添加咨询焦点（如果有）
        if state.consult_focus:
            query = f"{query} {state.consult_focus}"
        
        # 添加关键词（如果有）
        keywords = state.refined_keywords if state.refined_keywords else state.extracted_keywords
        if keywords:
            keywords_str = " ".join(keywords)
            query = f"{query} {keywords_str}"
        
        # 添加咨询类增强词
        query = f"{query} 定义 要求 规范 说明"
        
        # 执行检索：咨询类需要更多信息，降低阈值
        response = client.search(
            query=query,
            top_k=15,
            min_score=0.3
        )
        
        # 处理检索结果
        retrieval_results = []
        if response.code == 0 and response.chunks:
            for chunk in response.chunks:
                # 提取文件名
                file_name = extract_file_name_from_content(chunk.content)
                
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        return ConsultRetrievalOutput(
            retrieval_results=retrieval_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return ConsultRetrievalOutput(
            retrieval_results=[]
        )


def consult_context_expand_node(
    state: ConsultContextExpandInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultContextExpandOutput:
    """
    title: 咨询类上下文扩展
    desc: 扩展咨询类检索结果，获取完整段落（500-800字）
    """
    ctx = runtime.context
    
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            
            # 扩展内容到 500-800 字
            expanded_content = expand_content_around_chunk(original_content, target_length=650)
            
            expanded_results.append({
                "content": expanded_content,
                "score": result.get("score", 0.0),
                "doc_id": result.get("doc_id", ""),
                "file_name": result.get("file_name", "")
            })
        
        return ConsultContextExpandOutput(
            expanded_results=expanded_results
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return ConsultContextExpandOutput(
            expanded_results=state.retrieval_results
        )


def consult_rerank_node(
    state: ConsultRerankInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRerankOutput:
    """
    title: 咨询类重排序
    desc: 对咨询类扩展结果进行多维度评分和排序，筛选出最相关的 5 条结果
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    try:
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
            "expanded_results": state.expanded_results
        })
        
        # 调用大语言模型
        client = LLMClient(ctx=ctx)
        
        messages = [
            {"role": "system", "content": sp},
            {"role": "user", "content": user_prompt_content}
        ]
        
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.1),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
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
        
        # 解析 JSON 响应
        try:
            # 提取 JSON 内容
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result_json = json.loads(json_str)
                ranked_results = result_json.get("ranked_results", [])
            else:
                # 无法解析 JSON，返回原始结果
                ranked_results = state.expanded_results[:5]
        except Exception as e:
            # 解析失败，返回原始结果
            ranked_results = state.expanded_results[:5]
        
        return ConsultRerankOutput(
            retrieval_results=ranked_results
        )
        
    except Exception as e:
        # 发生错误时返回前 5 条原始结果
        return ConsultRerankOutput(
            retrieval_results=state.expanded_results[:5]
        )


# ==================== 咨询类循环检索节点（旧版本，已弃用）====================

def consult_retrieval_loop_start_node(
    state: ConsultRetrievalLoopStartInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopStartOutput:
    """
    title: 咨询类循环检索入口
    desc: 初始化循环检索状态，准备开始第一轮检索
    integrations: 无
    """
    ctx = runtime.context
    
    # 初始化循环状态
    loop_state = ConsultRetrievalLoopState(
        user_query=state.user_query,
        refined_query=state.refined_query,
        refined_keywords=state.refined_keywords,
        consult_focus=state.consult_focus,
        max_rounds=2,  # 第一阶段固定2轮
        target_score=0.8,
        min_score_threshold=0.65,
        current_round=0,
        previous_score=0.0,
        current_score=0.0,
        retrieval_results=[],
        high_score_chunks=[],
        should_continue=True,
        exit_reason="",
        previous_retrieval_results=[]
    )
    
    return ConsultRetrievalLoopStartOutput(
        loop_state=loop_state
    )


def consult_retrieval_loop_end_node(
    state: ConsultRetrievalLoopEndInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopEndOutput:
    """
    title: 咨询类循环检索出口
    desc: 根据循环检索的最终状态，返回最终结果或兜底回答
    integrations: 无
    """
    ctx = runtime.context
    
    loop_state = state.loop_state
    
    # 判断是否需要兜底回答
    is_fallback = False
    fallback_message = ""
    final_results = loop_state.retrieval_results
    
    # 如果退出原因是 fallback，使用兜底回答
    if loop_state.exit_reason == "fallback":
        is_fallback = True
        fallback_message = get_fallback_response("咨询类")
        final_results = []
    
    # 如果退出原因是 score_decreased，使用上一轮结果
    elif loop_state.exit_reason == "score_decreased":
        if loop_state.previous_retrieval_results:
            final_results = loop_state.previous_retrieval_results
        else:
            # 如果没有上一轮结果，使用兜底回答
            is_fallback = True
            fallback_message = get_fallback_response("咨询类")
            final_results = []
    
    # 其他情况（success、target_score_reached、max_rounds_reached），使用当前结果
    else:
        final_results = loop_state.retrieval_results
        is_fallback = False
        fallback_message = ""
    
    return ConsultRetrievalLoopEndOutput(
        retrieval_results=final_results,
        is_fallback=is_fallback,
        fallback_message=fallback_message
    )


# ==================== 查询复杂度判断节点 ====================

def complexity_node(
    state: ComplexityInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ComplexityOutput:
    """
    title: 查询复杂度判断
    desc: 判断用户查询的复杂程度（simple/standard/complex），为后续检索策略提供依据
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
            temperature=llm_config.get("temperature", 0.3),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 500),
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
        
        # 解析JSON响应
        result = {
            "query_complexity": "standard",
            "complexity_reason": "默认标准复杂度"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "query_complexity" in parsed_result:
                    result["query_complexity"] = parsed_result["query_complexity"]
                if "complexity_reason" in parsed_result:
                    result["complexity_reason"] = parsed_result["complexity_reason"]
            except json.JSONDecodeError:
                pass
        
        return ComplexityOutput(
            query_complexity=result["query_complexity"],
            complexity_reason=result["complexity_reason"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ComplexityOutput(
            query_complexity="standard",
            complexity_reason="默认标准复杂度"
        )


# ==================== 咨询查询优化节点 ====================

def consult_query_optimize_node(
    state: ConsultQueryOptimizeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultQueryOptimizeOutput:
    """
    title: 咨询查询优化
    desc: 根据查询复杂度动态调整检索策略，优化查询语句和关键词
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
        "query_complexity": state.query_complexity,
        "refined_query": state.refined_query,
        "refined_keywords": state.refined_keywords,
        "consult_focus": state.consult_focus,
        "standard_terms": state.standard_terms,
        "expanded_terms": state.expanded_terms
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
            max_completion_tokens=llm_config.get("max_completion_tokens", 1000),
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
        
        # 解析JSON响应
        result = {
            "optimized_query": state.refined_query if state.refined_query else state.user_query,
            "optimized_keywords": state.refined_keywords if state.refined_keywords else state.extracted_keywords if hasattr(state, 'extracted_keywords') else [],
            "retrieval_strategy": {
                "top_k_first_round": 20,
                "min_score_first_round": 0.25,
                "top_k_second_round": 15,
                "min_score_second_round": 0.55,
                "max_rounds": 2,
                "target_score": 0.75,
                "min_score_threshold": 0.6
            },
            "optimization_reason": "默认优化策略（标准查询）：第1轮扩大检索范围到20个候选，第2轮精准筛选15个高质量结果"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "optimized_query" in parsed_result:
                    result["optimized_query"] = parsed_result["optimized_query"]
                if "optimized_keywords" in parsed_result:
                    result["optimized_keywords"] = parsed_result["optimized_keywords"]
                if "retrieval_strategy" in parsed_result:
                    result["retrieval_strategy"] = parsed_result["retrieval_strategy"]
                if "optimization_reason" in parsed_result:
                    result["optimization_reason"] = parsed_result["optimization_reason"]
            except json.JSONDecodeError:
                pass
        
        return ConsultQueryOptimizeOutput(
            optimized_query=result["optimized_query"],
            optimized_keywords=result["optimized_keywords"],
            retrieval_strategy=result["retrieval_strategy"],
            optimization_reason=result["optimization_reason"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ConsultQueryOptimizeOutput(
            optimized_query=state.refined_query if state.refined_query else state.user_query,
            optimized_keywords=state.refined_keywords if state.refined_keywords else state.extracted_keywords if hasattr(state, 'extracted_keywords') else [],
            retrieval_strategy={
                "top_k_first_round": 20,
                "min_score_first_round": 0.25,
                "top_k_second_round": 15,
                "min_score_second_round": 0.55,
                "max_rounds": 2,
                "target_score": 0.75,
                "min_score_threshold": 0.6
            },
            optimization_reason="默认优化策略（标准查询）：第1轮扩大检索范围到20个候选，第2轮精准筛选15个高质量结果"
        )


# ==================== 重排序节点（新版本） ====================

def rerank_node(
    state: RerankInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> RerankOutput:
    """
    title: 重排序
    desc: 对检索结果进行多维度评分和排序
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
        "expanded_results": state.expanded_results
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
            temperature=llm_config.get("temperature", 0.1),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
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
        
        # 解析JSON响应
        result = {
            "ranked_results": state.expanded_results,
            "weighted_score": 0.7,
            "top_score": 0.7,
            "top_3_avg": 0.7,
            "average_confidence": 0.7
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "ranked_results" in parsed_result:
                    result["ranked_results"] = parsed_result["ranked_results"]
                if "weighted_score" in parsed_result:
                    result["weighted_score"] = parsed_result["weighted_score"]
                if "top_score" in parsed_result:
                    result["top_score"] = parsed_result["top_score"]
                if "top_3_avg" in parsed_result:
                    result["top_3_avg"] = parsed_result["top_3_avg"]
                if "average_confidence" in parsed_result:
                    result["average_confidence"] = parsed_result["average_confidence"]
            except json.JSONDecodeError:
                pass
        
        return RerankOutput(
            ranked_results=result["ranked_results"],
            weighted_score=result["weighted_score"],
            top_score=result["top_score"],
            top_3_avg=result["top_3_avg"],
            average_confidence=result["average_confidence"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return RerankOutput(
            ranked_results=state.expanded_results,
            weighted_score=0.7,
            top_score=0.7,
            top_3_avg=0.7,
            average_confidence=0.7
        )


# ==================== 上下文提取节点 ====================

def context_extract_node(
    state: ContextExtractInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ContextExtractOutput:
    """
    title: 上下文提取
    desc: 从检索结果中提取结构化知识（关键概念、关系映射、缺失方面、摘要）
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
        "top_3_results": state.top_3_results
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
        
        # 解析JSON响应
        result = {
            "key_concepts": [],
            "relation_map": {},
            "missing_aspects": [],
            "summary": ""
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "key_concepts" in parsed_result:
                    result["key_concepts"] = parsed_result["key_concepts"]
                if "relation_map" in parsed_result:
                    result["relation_map"] = parsed_result["relation_map"]
                if "missing_aspects" in parsed_result:
                    result["missing_aspects"] = parsed_result["missing_aspects"]
                if "summary" in parsed_result:
                    result["summary"] = parsed_result["summary"]
            except json.JSONDecodeError:
                pass
        
        return ContextExtractOutput(
            key_concepts=result["key_concepts"],
            relation_map=result["relation_map"],
            missing_aspects=result["missing_aspects"],
            summary=result["summary"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ContextExtractOutput(
            key_concepts=[],
            relation_map={},
            missing_aspects=[],
            summary=""
        )


# ==================== 改善分析节点 ====================

def improvement_analysis_node(
    state: ImprovementAnalysisInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ImprovementAnalysisOutput:
    """
    title: 改善分析
    desc: 评估检索结果质量，预测改善潜力，决定是否继续检索
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
        "current_round": state.current_round,
        "previous_prev_score": state.previous_prev_score,
        "previous_score": state.previous_score,
        "current_score": state.current_score,
        "current_retrieval_results": state.current_retrieval_results,
        "structured_context": state.structured_context,
        "previous_context": state.previous_context
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
            max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
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
        
        # 解析JSON响应
        result = {
            "improvement_potential": "moderate",
            "predicted_next_score": state.current_score,
            "score_change_analysis": {
                "change_type": "normal_fluctuation",
                "change_magnitude": 0.0,
                "change_reason": "默认分析"
            },
            "recommendation": "continue",
            "recommendation_reason": "默认建议：继续检索"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "improvement_potential" in parsed_result:
                    result["improvement_potential"] = parsed_result["improvement_potential"]
                if "predicted_next_score" in parsed_result:
                    result["predicted_next_score"] = parsed_result["predicted_next_score"]
                if "score_change_analysis" in parsed_result:
                    result["score_change_analysis"] = parsed_result["score_change_analysis"]
                if "recommendation" in parsed_result:
                    result["recommendation"] = parsed_result["recommendation"]
                if "recommendation_reason" in parsed_result:
                    result["recommendation_reason"] = parsed_result["recommendation_reason"]
            except json.JSONDecodeError:
                pass
        
        return ImprovementAnalysisOutput(
            improvement_potential=result["improvement_potential"],
            predicted_next_score=result["predicted_next_score"],
            score_change_analysis=result["score_change_analysis"],
            recommendation=result["recommendation"],
            recommendation_reason=result["recommendation_reason"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ImprovementAnalysisOutput(
            improvement_potential="moderate",
            predicted_next_score=state.current_score,
            score_change_analysis={
                "change_type": "normal_fluctuation",
                "change_magnitude": 0.0,
                "change_reason": "默认分析"
            },
            recommendation="continue",
            recommendation_reason="默认建议：继续检索"
        )
