"""
循环检索子图定义
包含咨询类的循环检索子图
将consult_retrieval_node、consult_context_expand_node、consult_rerank_node封装成一个子图
"""

import os
import json
import re
from typing import Literal
from jinja2 import Template
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks,
    get_fallback_response
)


# ==================== 子图状态定义 ====================

class ConsultRetrievalLoopState(BaseModel):
    """咨询类循环检索子图状态
    
    注意：此状态必须与GlobalState兼容，包含所有检索相关的字段
    """
    # ==================== 来自GlobalState的字段 ====================
    user_query: str = Field(default="", description="用户输入的查询问题")
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: list = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点")
    retrieval_results: list = Field(default=[], description="知识库检索结果")
    
    # ==================== 循环控制字段 ====================
    max_rounds: int = Field(default=2, description="最大循环轮次")
    target_score: float = Field(default=0.8, description="目标分数（达到即退出）")
    min_score_threshold: float = Field(default=0.65, description="最低阈值（达到最大轮次后判断）")
    
    # ==================== 循环状态字段 ====================
    current_round: int = Field(default=0, description="当前轮次")
    previous_score: float = Field(default=0.0, description="上一轮分数")
    current_score: float = Field(default=0.0, description="当前分数（加权求和）")
    high_score_chunks: list = Field(default=[], description="top-3高分内容（用于下一轮上下文）")
    exit_reason: str = Field(default="", description="退出原因：target_score_reached/score_decreased/max_rounds_reached/fallback")
    previous_retrieval_results: list = Field(default=[], description="上一轮的检索结果（用于分数下降时回退）")


# ==================== 包装节点：咨询类知识库检索 ====================

def consult_retrieval_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类知识库检索（子图节点）
    desc: 根据咨询类意图检索学术道德规范相关内容
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 保存上一轮结果（用于分数下降时回退）
        if state.current_round > 0:
            previous_results = state.retrieval_results.copy()
        else:
            previous_results = []
        
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
        if state.refined_keywords:
            keywords_str = " ".join(state.refined_keywords)
            query = f"{query} {keywords_str}"
        
        # 添加咨询类增强词
        query = f"{query} 定义 要求 规范 说明"
        
        # 如果是第二轮，添加top-3高分内容作为上下文
        if state.current_round >= 1 and state.high_score_chunks:
            context_parts = ["根据已检索到的优质内容："]
            context_parts.extend(state.high_score_chunks)
            context_parts.append(f"，请继续检索更多关于{query}的相关信息。")
            query = " ".join(context_parts)
        
        # 执行检索：咨询类需要更多信息，降低阈值
        # 第一轮用top_k=15，第二轮用top_k=10
        top_k = 10 if state.current_round >= 1 else 15
        min_score = 0.3 if state.current_round == 0 else 0.6
        
        response = client.search(
            query=query,
            top_k=top_k,
            min_score=min_score
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
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.retrieval_results = retrieval_results
        updated_state.previous_retrieval_results = previous_results
        
        return updated_state
        
    except Exception as e:
        # 发生错误时返回空结果
        return state


# ==================== 包装节点：咨询类上下文扩展 ====================

def consult_context_expand_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类上下文扩展（子图节点）
    desc: 扩展咨询类检索结果，获取完整段落
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
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.retrieval_results = expanded_results
        
        return updated_state
        
    except Exception as e:
        # 发生错误时返回原始结果
        return state


# ==================== 包装节点：咨询类重排序 ====================

def consult_rerank_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类重排序（子图节点）
    desc: 对咨询类扩展结果进行多维度评分和排序，计算加权总分
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    try:
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
                ranked_results = state.retrieval_results[:5]
        except Exception as e:
            # 解析失败，返回原始结果
            ranked_results = state.retrieval_results[:5]
        
        # 计算加权总分
        weighted_score = calculate_weighted_score(ranked_results)
        
        # 提取top-3高分内容（用于下一轮）
        high_score_chunks = extract_top_k_chunks(ranked_results, 3)
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.previous_score = state.current_score
        updated_state.current_score = weighted_score
        updated_state.current_round = state.current_round + 1  # 轮次递增
        updated_state.retrieval_results = ranked_results
        updated_state.high_score_chunks = high_score_chunks
        
        # 设置退出原因
        if weighted_score >= state.target_score:
            updated_state.exit_reason = "target_score_reached"
        elif updated_state.current_round >= state.max_rounds:
            if weighted_score >= state.min_score_threshold:
                updated_state.exit_reason = "max_rounds_reached"
            else:
                updated_state.exit_reason = "fallback"
        elif updated_state.current_round > 1 and weighted_score < state.previous_score:
            updated_state.exit_reason = "score_decreased"
        
        return updated_state
        
    except Exception as e:
        # 发生错误时，返回原始状态
        updated_state = state.model_copy(deep=True)
        updated_state.current_round = state.current_round + 1
        updated_state.exit_reason = "fallback"
        return updated_state


# ==================== 循环条件判断 ====================

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
    builder.add_node("consult_retrieval_wrapper", consult_retrieval_wrapper_node)
    builder.add_node("consult_context_expand_wrapper", consult_context_expand_wrapper_node)
    builder.add_node("consult_rerank_wrapper", consult_rerank_wrapper_node)
    
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


# 创建并导出子图实例
consult_retrieval_subgraph = create_consult_retrieval_subgraph()
