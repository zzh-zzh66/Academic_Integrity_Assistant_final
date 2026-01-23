"""
循环检索子图定义
咨询类的循环检索子图，支持动态检索策略
"""

import os
import time
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import KnowledgeClient

from graphs.state import (
    ConsultRetrievalLoopState,
    RerankInput,
    RerankOutput,
    ContextExtractInput,
    ContextExtractOutput,
    ImprovementAnalysisInput,
    ImprovementAnalysisOutput
)
from graphs.nodes.common import extract_file_name_from_content
from graphs.loop_config_loader import config_loader

# 配置日志
logger = logging.getLogger("consult_retrieval")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler("/app/work/logs/bypass/app.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==================== 循环内部节点1：知识库检索 ====================

def consult_retrieval_internal_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 知识库检索（内部）
    desc: 根据动态检索策略执行知识库检索
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
        
        # 记录输入信息
        logger.info(f"=== 咨询类检索开始 - 第{state.current_round}轮 ===")
        logger.info(f"用户查询: {state.user_query}")
        logger.info(f"优化查询: {state.refined_query}")
        logger.info(f"咨询焦点: {state.consult_focus}")
        logger.info(f"优化关键词: {state.refined_keywords}")
        logger.info(f"上一轮结果数: {len(previous_results)}")
        
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
            logger.info(f"第{state.current_round}轮使用上下文增强")
        
        logger.info(f"最终查询语句: {query}")
        
        # 根据当前轮次和检索策略确定参数
        current_round = state.current_round
        retrieval_strategy = state.retrieval_strategy
        
        # 使用动态参数（优先从retrieval_strategy中获取）
        if current_round == 0:
            top_k = retrieval_strategy.get("top_k", state.top_k_first_round)
            min_score = retrieval_strategy.get("min_score", state.min_score_first_round)
        elif current_round == 1:
            top_k = retrieval_strategy.get("top_k", state.top_k_second_round)
            min_score = retrieval_strategy.get("min_score", state.min_score_second_round)
        else:
            top_k = retrieval_strategy.get("top_k", state.top_k_third_round)
            min_score = retrieval_strategy.get("min_score", state.min_score_third_round)
        
        logger.info(f"检索参数: top_k={top_k}, min_score={min_score}")
        
        response = client.search(
            query=query,
            top_k=top_k,
            min_score=min_score
        )
        
        # 记录知识库响应
        logger.info(f"知识库响应: code={response.code}, chunks数量={len(response.chunks) if hasattr(response, 'chunks') else 0}")
        
        # 处理检索结果
        retrieval_results = []
        if response.code == 0 and response.chunks:
            logger.info(f"=== 原始chunks分数统计 ===")
            for idx, chunk in enumerate(response.chunks):
                logger.info(f"  Chunk[{idx}]: score={chunk.score}, doc_id={chunk.doc_id}")
                
                # 提取文件名
                file_name = extract_file_name_from_content(chunk.content)
                
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        # 记录最终结果
        logger.info(f"=== 过滤后结果 ===")
        logger.info(f"结果数量: {len(retrieval_results)}")
        if retrieval_results:
            logger.info(f"最高分: {max(r['score'] for r in retrieval_results)}")
            logger.info(f"最低分: {min(r['score'] for r in retrieval_results)}")
            logger.info(f"平均分: {sum(r['score'] for r in retrieval_results) / len(retrieval_results):.4f}")
            for idx, result in enumerate(retrieval_results):
                logger.info(f"  Result[{idx}]: score={result['score']:.4f}, file={result['file_name']}")
        else:
            logger.warning(f"没有检索到任何结果！所有结果都被min_score={min_score}过滤掉了")
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.retrieval_results = retrieval_results
        updated_state.previous_retrieval_results = previous_results
        
        return updated_state
        
    except Exception as e:
        # 发生错误时返回空结果
        return state


# ==================== 循环内部节点2：内容扩展 ====================

def consult_expand_internal_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 内容扩展（内部）
    desc: 扩展检索结果，获取完整段落
    """
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            
            # 简单扩展：直接使用原内容
            expanded_content = original_content
            
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


# ==================== 循环内部节点3：重排序 ====================

def rerank_internal_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 重排序（内部）
    desc: 对检索结果进行多维度评分和排序
    integrations: 大语言模型
    """
    # 延迟导入，避免循环依赖
    from graphs.nodes.consult import rerank_node
    from graphs.nodes.common import calculate_weighted_score, extract_top_k_chunks
    
    try:
        logger.info(f"=== 重排序节点开始 - 第{state.current_round}轮 ===")
        logger.info(f"输入结果数: {len(state.retrieval_results)}")
        
        # 获取配置文件路径
        config_path = config_loader.get_node_config_path("consult", "rerank")
        
        # 调用rerank_node
        rerank_input = RerankInput(
            user_query=state.user_query,
            expanded_results=state.retrieval_results
        )
        
        # 临时创建config，包含llm_cfg路径
        temp_config = RunnableConfig(
            configurable={},
            metadata={"llm_cfg": config_path} if config_path else {}
        )
        
        rerank_output = rerank_node(rerank_input, temp_config, runtime)
        
        # 计算加权总分（使用rerank输出的weighted_score）
        weighted_score = rerank_output.weighted_score
        
        # 提取top-3高分内容
        high_score_chunks = []
        for result in rerank_output.ranked_results[:3]:
            high_score_chunks.append(result.get("content", ""))
        
        # 记录重排序结果
        logger.info(f"=== 重排序结果 ===")
        logger.info(f"加权总分: {weighted_score:.4f}")
        logger.info(f"top_score: {rerank_output.top_score:.4f}")
        logger.info(f"top_3_avg: {rerank_output.top_3_avg:.4f}")
        logger.info(f"average_confidence: {rerank_output.average_confidence:.4f}")
        logger.info(f"目标分数: {state.target_score:.4f}")
        logger.info(f"最低阈值: {state.min_score_threshold:.4f}")
        logger.info(f"上一轮分数: {state.previous_score:.4f}")
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.previous_prev_score = state.previous_score
        updated_state.previous_score = state.current_score
        updated_state.current_score = weighted_score
        updated_state.current_round = state.current_round + 1
        updated_state.retrieval_results = rerank_output.ranked_results
        updated_state.high_score_chunks = high_score_chunks
        updated_state.ranked_results = rerank_output.ranked_results
        updated_state.top_score = rerank_output.top_score
        updated_state.top_3_avg = rerank_output.top_3_avg
        updated_state.average_confidence = rerank_output.average_confidence
        
        # 设置退出原因
        if weighted_score >= state.target_score:
            updated_state.exit_reason = "target_score_reached"
            logger.info(f"✓ 达到目标分数，退出原因: target_score_reached")
        elif updated_state.current_round >= state.max_rounds:
            if weighted_score >= state.min_score_threshold:
                updated_state.exit_reason = "max_rounds_reached"
                logger.info(f"✓ 达到最大轮次但分数达标，退出原因: max_rounds_reached")
            else:
                updated_state.exit_reason = "fallback"
                logger.warning(f"✗ 达到最大轮次但分数未达标，退出原因: fallback")
        elif updated_state.current_round > 1 and weighted_score < state.previous_score:
            updated_state.exit_reason = "score_decreased"
            logger.warning(f"✗ 分数下降，退出原因: score_decreased")
        else:
            logger.info(f"继续下一轮检索，当前轮次: {updated_state.current_round}/{state.max_rounds}")
        
        return updated_state
        
    except Exception as e:
        logger.error(f"重排序节点发生异常: {str(e)}", exc_info=True)
        # 发生错误时，返回原始状态
        updated_state = state.model_copy(deep=True)
        updated_state.current_round = state.current_round + 1
        updated_state.exit_reason = "fallback"
        return updated_state


# ==================== 循环内部节点4：上下文提取 ====================

def context_extract_internal_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 上下文提取（内部）
    desc: 从top-3结果中提取结构化知识
    integrations: 大语言模型
    """
    # 延迟导入，避免循环依赖
    from graphs.nodes.consult import context_extract_node
    
    try:
        # 检查配置：是否执行context_extract节点
        if not config_loader.should_execute_node("consult", "context_extract", state.current_round):
            # 不执行，直接返回
            return state
        
        # 获取配置文件路径
        config_path = config_loader.get_node_config_path("consult", "context_extract")
        if not config_path:
            return state
        
        # 提取top-3结果
        top_3_results = state.ranked_results[:3] if state.ranked_results else state.retrieval_results[:3]
        
        # 调用context_extract_node
        context_extract_input = ContextExtractInput(
            user_query=state.user_query,
            top_3_results=top_3_results
        )
        
        # 临时创建config，包含llm_cfg路径
        temp_config = RunnableConfig(
            configurable={},
            metadata={"llm_cfg": config_path}
        )
        
        context_extract_output = context_extract_node(context_extract_input, temp_config, runtime)
        
        # 保存上一轮上下文
        updated_state = state.model_copy(deep=True)
        updated_state.previous_context = state.structured_context.copy() if state.structured_context else {}
        
        # 更新结构化上下文
        updated_state.structured_context = {
            "key_concepts": context_extract_output.key_concepts,
            "relation_map": context_extract_output.relation_map,
            "missing_aspects": context_extract_output.missing_aspects,
            "summary": context_extract_output.summary
        }
        updated_state.key_concepts = context_extract_output.key_concepts
        updated_state.relation_map = context_extract_output.relation_map
        updated_state.missing_aspects = context_extract_output.missing_aspects
        updated_state.context_summary = context_extract_output.summary
        
        return updated_state
        
    except Exception as e:
        # 发生错误时，返回原始状态
        return state


# ==================== 循环内部节点5：改善分析 ====================

def improvement_analysis_internal_node(
    state: ConsultRetrievalLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopState:
    """
    title: 改善分析（内部）
    desc: 评估检索结果质量，决定是否继续检索
    integrations: 大语言模型
    """
    # 延迟导入，避免循环依赖
    from graphs.nodes.consult import improvement_analysis_node
    
    try:
        # 检查配置：是否执行improvement_analysis节点
        if not config_loader.should_execute_node("consult", "improvement_analysis", state.current_round):
            # 不执行，直接返回
            return state
        
        # 获取配置文件路径
        config_path = config_loader.get_node_config_path("consult", "improvement_analysis")
        if not config_path:
            return state
        
        # 调用improvement_analysis_node
        improvement_input = ImprovementAnalysisInput(
            user_query=state.user_query,
            current_round=state.current_round,
            previous_prev_score=state.previous_prev_score,
            previous_score=state.previous_score,
            current_score=state.current_score,
            current_retrieval_results=state.retrieval_results,
            structured_context=state.structured_context,
            previous_context=state.previous_context
        )
        
        # 临时创建config，包含llm_cfg路径
        temp_config = RunnableConfig(
            configurable={},
            metadata={"llm_cfg": config_path}
        )
        
        improvement_output = improvement_analysis_node(improvement_input, temp_config, runtime)
        
        # 更新状态
        updated_state = state.model_copy(deep=True)
        updated_state.improvement_potential = improvement_output.improvement_potential
        updated_state.predicted_next_score = improvement_output.predicted_next_score
        updated_state.score_change_analysis = improvement_output.score_change_analysis
        updated_state.recommendation = improvement_output.recommendation
        
        # 根据建议决定退出策略
        if improvement_output.recommendation == "exit_now":
            updated_state.exit_reason = "target_score_reached"
        elif improvement_output.recommendation == "exit_best_effort":
            updated_state.exit_reason = "max_rounds_reached"
        
        return updated_state
        
    except Exception as e:
        # 发生错误时，返回原始状态
        return state


# ==================== 循环条件判断 ====================

def should_continue_consult_loop(state: ConsultRetrievalLoopState) -> Literal["continue", "exit_success", "exit_fallback"]:
    """
    title: 咨询类循环条件判断
    desc: 判断是否继续循环检索
    """
    logger.info(f"=== 循环条件判断 - 第{state.current_round}轮 ===")
    logger.info(f"当前分数: {state.current_score:.4f}")
    logger.info(f"目标分数: {state.target_score:.4f}")
    logger.info(f"最低阈值: {state.min_score_threshold:.4f}")
    logger.info(f"上一轮分数: {state.previous_score:.4f}")
    logger.info(f"已设置退出原因: {state.exit_reason}")
    
    # 1. 判断是否达到目标分数
    if state.current_score >= state.target_score:
        logger.info(f"✓ 达到目标分数，决定: exit_success")
        return "exit_success"
    
    # 2. 判断是否已退出（由improvement_analysis_node设置）
    if state.exit_reason in ["target_score_reached", "max_rounds_reached"]:
        logger.info(f"✓ 节点已设置成功退出，决定: exit_success")
        return "exit_success"
    elif state.exit_reason == "fallback":
        logger.info(f"✗ 节点已设置兜底退出，决定: exit_fallback")
        return "exit_fallback"
    
    # 3. 判断分数是否下降（仅从第二轮开始）
    if state.current_round > 1:
        if state.current_score < state.previous_score:
            logger.info(f"✗ 分数下降({state.previous_score:.4f} -> {state.current_score:.4f})，决定: exit_fallback")
            return "exit_fallback"
    
    # 4. 判断是否达到最大轮次
    if state.current_round >= state.max_rounds:
        # 检查是否达到最低阈值
        if state.current_score >= state.min_score_threshold:
            logger.info(f"✓ 达到最大轮次但分数达标，决定: exit_success")
            return "exit_success"
        else:
            logger.info(f"✗ 达到最大轮次且分数未达标，决定: exit_fallback")
            return "exit_fallback"
    
    # 5. 继续循环
    logger.info(f"→ 继续下一轮检索，决定: continue")
    return "continue"


# ==================== 创建咨询类循环检索子图 ====================

def create_consult_retrieval_subgraph() -> StateGraph:
    """
    创建咨询类循环检索子图
    
    Returns:
        编译后的子图
    """
    # 创建子图状态图
    builder = StateGraph(
        ConsultRetrievalLoopState,
        input_schema=None,
        output_schema=None
    )
    
    # 添加节点
    builder.add_node("consult_retrieval_internal", consult_retrieval_internal_node)
    builder.add_node("consult_expand_internal", consult_expand_internal_node)
    builder.add_node("rerank_internal", rerank_internal_node)
    builder.add_node("context_extract_internal", context_extract_internal_node)
    builder.add_node("improvement_analysis_internal", improvement_analysis_internal_node)
    
    # 设置入口点
    builder.set_entry_point("consult_retrieval_internal")
    
    # 添加边：检索 → 扩展 → 重排序 → 上下文提取 → 改善分析
    builder.add_edge("consult_retrieval_internal", "consult_expand_internal")
    builder.add_edge("consult_expand_internal", "rerank_internal")
    builder.add_edge("rerank_internal", "context_extract_internal")
    builder.add_edge("context_extract_internal", "improvement_analysis_internal")
    
    # 添加条件边：改善分析 → 继续循环或退出
    builder.add_conditional_edges(
        source="improvement_analysis_internal",
        path=should_continue_consult_loop,
        path_map={
            "continue": "consult_retrieval_internal",  # 继续循环
            "exit_success": END,  # 成功退出
            "exit_fallback": END  # 兜底退出
        }
    )
    
    # 编译子图
    consult_retrieval_subgraph = builder.compile()
    
    return consult_retrieval_subgraph


# 创建并导出子图实例
consult_retrieval_subgraph = create_consult_retrieval_subgraph()
