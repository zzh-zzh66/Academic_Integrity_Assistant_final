"""
循环检索子图定义
包含咨询类的循环检索子图
"""

import os
import json
from jinja2 import Template
from langgraph.graph import StateGraph, END
from typing import Literal
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    ConsultRetrievalLoopState,
    ConsultRetrievalInput,
    ConsultRetrievalOutput,
    ConsultContextExpandInput,
    ConsultContextExpandOutput,
    ConsultRerankInput,
    ConsultRerankOutput
)
from graphs.nodes.common import (
    calculate_weighted_score,
    extract_top_k_chunks,
    expand_content_around_chunk,
    extract_file_name_from_content,
    get_fallback_response
)


# ==================== 咨询类循环检索包装器节点（内联实现）====================

def consult_retrieval_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类循环检索包装器
    desc: 在子图中执行知识库检索
    integrations: 知识库
    """
    ctx = runtime.context
    
    # 保存上一轮结果（用于分数下降时回退）
    if state.current_round > 0:
        previous_results = state.retrieval_results.copy()
    else:
        previous_results = []
    
    # 构建检索查询
    query = state.refined_query
    
    # 如果是第二轮，添加top-3高分内容作为上下文
    if state.current_round >= 1 and state.high_score_chunks:
        context_parts = ["根据已检索到的优质内容："]
        context_parts.extend(state.high_score_chunks)
        context_parts.append(f"，请继续检索更多关于{query}的相关信息。")
        query = " ".join(context_parts)
    
    # 添加关键词
    if state.refined_keywords:
        keywords_str = " ".join(state.refined_keywords)
        query = f"{query} {keywords_str}"
    
    # 添加咨询类增强词
    query = f"{query} 定义 要求 规范 说明"
    
    # 执行检索
    client = KnowledgeClient(ctx=ctx)
    response = client.search(
        query=query,
        top_k=10,
        min_score=0.6
    )
    
    # 处理检索结果
    retrieval_results = []
    if response.code == 0 and response.chunks:
        for chunk in response.chunks:
            retrieval_results.append({
                "content": chunk.content,
                "score": chunk.score,
                "doc_id": chunk.doc_id,
                "file_name": extract_file_name_from_content(chunk.content) if hasattr(chunk, 'content') else ""
            })
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.retrieval_results = retrieval_results
    updated_state.previous_retrieval_results = previous_results
    
    return updated_state


def consult_context_expand_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类上下文扩展包装器
    desc: 在子图中执行上下文扩展
    integrations: 无
    """
    ctx = runtime.context
    
    # 扩展每个检索结果
    expanded_results = []
    for result in state.retrieval_results:
        content = result.get("content", "")
        expanded_content = expand_content_around_chunk(content, window_size=200)
        
        expanded_results.append({
            "content": expanded_content,
            "score": result.get("score", 0.0),
            "doc_id": result.get("doc_id", ""),
            "file_name": result.get("file_name", "")
        })
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.retrieval_results = expanded_results
    
    return updated_state


def consult_rerank_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类重排序包装器
    desc: 在子图中执行重排序和评分
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/consult_rerank_cfg.json")
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "expanded_results": state.retrieval_results
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
        
        # 解析JSON响应
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group(0)
            try:
                result_data = json.loads(json_str)
                retrieval_results = result_data.get("ranked_results", [])
            except:
                retrieval_results = state.retrieval_results
        else:
            retrieval_results = state.retrieval_results
        
    except Exception as e:
        retrieval_results = state.retrieval_results
    
    # 计算加权总分
    weighted_score = calculate_weighted_score(retrieval_results)
    
    # 提取top-3高分内容（用于下一轮）
    high_score_chunks = extract_top_k_chunks(retrieval_results, 3)
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.previous_score = state.current_score
    updated_state.current_score = weighted_score
    updated_state.current_round = state.current_round + 1  # 轮次递增
    updated_state.retrieval_results = retrieval_results
    updated_state.high_score_chunks = high_score_chunks
    
    # 设置退出原因
    if weighted_score >= state.target_score:
        updated_state.exit_reason = "target_score_reached"
    elif state.current_round >= state.max_rounds:
        if weighted_score >= state.min_score_threshold:
            updated_state.exit_reason = "max_rounds_reached"
        else:
            updated_state.exit_reason = "fallback"
    elif state.current_round > 1 and weighted_score < state.previous_score:
        updated_state.exit_reason = "score_decreased"
    
    return updated_state


# ==================== 咨询类循环条件判断 ====================

def should_continue_consult_loop(state: ConsultRetrievalLoopState) -> Literal["continue", "exit_success", "exit_fallback"]:
    """
    title: 咨询类循环条件判断
    desc: 判断是否继续循环检索，根据分数变化和阈值决定退出策略
    """
    # 1. 判断是否达到目标分数
    if state.current_score >= state.target_score:
        return "exit_success"
    
    # 2. 判断分数是否下降（仅从第二轮开始）
    if state.current_round > 1:
        if state.current_score < state.previous_score:
            return "exit_fallback"
    
    # 3. 判断是否达到最大轮次
    if state.current_round >= state.max_rounds:
        # 检查是否达到最低阈值
        if state.current_score >= state.min_score_threshold:
            return "exit_success"
        else:
            return "exit_fallback"
    
    # 4. 继续循环
    return "continue"


# ==================== 咨询类循环检索子图 ====================

def create_consult_retrieval_subgraph() -> StateGraph:
    """
    创建咨询类循环检索子图
    
    Returns:
        编译后的子图
    """
    # 创建子图状态图
    builder = StateGraph(
        ConsultRetrievalLoopState,
        input_schema=None,  # 子图不需要单独的input_schema
        output_schema=None  # 子图不需要单独的output_schema
    )
    
    # 添加节点
    builder.add_node("consult_retrieval_wrapper", consult_retrieval_loop_wrapper_node)
    builder.add_node("consult_context_expand_wrapper", consult_context_expand_loop_wrapper_node)
    builder.add_node("consult_rerank_wrapper", consult_rerank_loop_wrapper_node)
    
    # 设置入口点
    builder.set_entry_point("consult_retrieval_wrapper")
    
    # 添加边：检索 → 扩展 → 重排序
    builder.add_edge("consult_retrieval_wrapper", "consult_context_expand_wrapper")
    builder.add_edge("consult_context_expand_wrapper", "consult_rerank_wrapper")
    
    # 添加条件边：重排序 → 继续循环或退出
    builder.add_conditional_edges(
        source="consult_rerank_wrapper",
        path=should_continue_consult_loop,
        path_map={
            "continue": "consult_retrieval_wrapper",  # 继续循环
            "exit_success": END,  # 成功退出
            "exit_fallback": END  # 兜底退出
        }
    )
    
    # 编译子图
    consult_retrieval_subgraph = builder.compile()
    
    return consult_retrieval_subgraph


# 创建子图实例
consult_retrieval_subgraph = create_consult_retrieval_subgraph()
