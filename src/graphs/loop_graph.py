"""
循环检索子图定义
包含咨询类、行为判断类、混合类的循环检索子图
"""

from langgraph.graph import StateGraph, END
from typing import Literal
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    GlobalState,
    ConsultRetrievalLoopState,
    ConsultRetrievalInput,
    ConsultRetrievalOutput,
    ConsultContextExpandInput,
    ConsultContextExpandOutput,
    ConsultRerankInput,
    ConsultRerankOutput
)
from graphs.nodes import (
    consult_retrieval_node,
    consult_context_expand_node,
    consult_rerank_node
)
from graphs.nodes.common import (
    calculate_weighted_score,
    extract_top_k_chunks
)


# ==================== 咨询类循环检索包装器节点 ====================

def consult_retrieval_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类循环检索包装器
    desc: 将循环状态转换为检索节点输入，执行检索，将输出转换回循环状态
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
    
    # 创建检索节点输入
    retrieval_input = ConsultRetrievalInput(
        user_query=state.user_query,
        extracted_keywords=state.refined_keywords,
        refined_query=state.refined_query,
        refined_keywords=state.refined_keywords,
        consult_focus=state.consult_focus
    )
    
    # 调用检索节点
    retrieval_output = consult_retrieval_node(
        state=retrieval_input,
        config=config,
        runtime=runtime
    )
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.retrieval_results = retrieval_output.retrieval_results
    updated_state.previous_retrieval_results = previous_results
    
    return updated_state


def consult_context_expand_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类上下文扩展包装器
    desc: 将循环状态转换为扩展节点输入，执行扩展，将输出转换回循环状态
    integrations: 无
    """
    ctx = runtime.context
    
    # 创建扩展节点输入
    expand_input = ConsultContextExpandInput(
        retrieval_results=state.retrieval_results,
        user_query=state.user_query
    )
    
    # 调用扩展节点
    expand_output = consult_context_expand_node(
        state=expand_input,
        config=config,
        runtime=runtime
    )
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.retrieval_results = expand_output.expanded_results
    
    return updated_state


def consult_rerank_loop_wrapper_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 咨询类重排序包装器
    desc: 将循环状态转换为重排序节点输入，执行重排序，计算分数，将输出转换回循环状态
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 创建重排序节点输入
    rerank_input = ConsultRerankInput(
        expanded_results=state.retrieval_results,
        user_query=state.user_query
    )
    
    # 调用重排序节点
    rerank_output = consult_rerank_node(
        state=rerank_input,
        config=config,
        runtime=runtime
    )
    
    # 计算加权总分
    weighted_score = calculate_weighted_score(rerank_output.retrieval_results)
    
    # 提取top-3高分内容（用于下一轮）
    high_score_chunks = extract_top_k_chunks(rerank_output.retrieval_results, 3)
    
    # 更新循环状态
    updated_state = state.model_copy(deep=True)
    updated_state.previous_score = state.current_score
    updated_state.current_score = weighted_score
    updated_state.retrieval_results = rerank_output.retrieval_results
    updated_state.high_score_chunks = high_score_chunks
    
    return updated_state


# ==================== 咨询类循环条件判断 ====================

def should_continue_consult_loop(state: ConsultRetrievalLoopState) -> Literal["continue", "exit_success", "exit_fallback"]:
    """
    title: 咨询类循环条件判断
    desc: 判断是否继续循环检索，根据分数变化和阈值决定退出策略
    """
    # 1. 判断是否达到目标分数
    if state.current_score >= state.target_score:
        updated_state = state.model_copy(deep=True)
        updated_state.exit_reason = "target_score_reached"
        updated_state.should_continue = False
        return "exit_success"
    
    # 2. 判断分数是否下降（仅从第二轮开始）
    if state.current_round > 1:
        if state.current_score < state.previous_score:
            updated_state = state.model_copy(deep=True)
            updated_state.exit_reason = "score_decreased"
            updated_state.should_continue = False
            return "exit_fallback"
    
    # 3. 判断是否达到最大轮次
    if state.current_round >= state.max_rounds:
        # 检查是否达到最低阈值
        if state.current_score >= state.min_score_threshold:
            updated_state = state.model_copy(deep=True)
            updated_state.exit_reason = "max_rounds_reached"
            updated_state.should_continue = False
            return "exit_success"
        else:
            updated_state = state.model_copy(deep=True)
            updated_state.exit_reason = "fallback"
            updated_state.should_continue = False
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
