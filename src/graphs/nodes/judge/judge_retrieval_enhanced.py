import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks
)

def judge_retrieval_enhanced_node(
    state: JudgeRetrievalEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeRetrievalEnhancedOutput:
    """
    title: 行为判断类增强检索
    desc: 执行2轮循环检索，扩大检索范围，获取更多规则片段
    integrations: 知识库, 大语言模型（重排序）
    """
    ctx = runtime.context
    
    logger.info("=== 行为判断类增强检索开始 ===")
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"优化查询: {state.optimized_query}")
    logger.info(f"查询复杂度: {state.query_complexity}")
    logger.info(f"检索策略: {state.retrieval_strategy}")
    
    try:
        client = KnowledgeClient(ctx=ctx)
        
        # 从检索策略中获取参数
        retrieval_strategy = state.retrieval_strategy
        
        # 第1轮：扩大检索
        top_k_first = retrieval_strategy.get("top_k_first_round", 20)
        min_score_first = retrieval_strategy.get("min_score_first_round", 0.3)
        
        query_first = state.optimized_query if state.optimized_query else state.user_query
        
        # 添加行为分析信息
        if state.behavior_subject or state.behavior_action or state.behavior_object:
            behavior_parts = []
            if state.behavior_subject:
                behavior_parts.append(f"主体:{state.behavior_subject}")
            if state.behavior_action:
                behavior_parts.append(f"动作:{state.behavior_action}")
            if state.behavior_object:
                behavior_parts.append(f"对象:{state.behavior_object}")
            query_first = f"{query_first} {' '.join(behavior_parts)}"
        
        # 添加关键词
        if state.optimized_keywords:
            keywords_str = " ".join(state.optimized_keywords)
            query_first = f"{query_first} {keywords_str}"
        
        logger.info(f"第1轮检索: top_k={top_k_first}, min_score={min_score_first}")
        logger.info(f"查询语句: {query_first}")
        
        response_first = client.search(query=query_first, top_k=top_k_first, min_score=min_score_first)
        
        # 处理第1轮结果
        first_round_results = []
        if response_first.code == 0 and response_first.chunks:
            for chunk in response_first.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                first_round_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        logger.info(f"第1轮检索结果: {len(first_round_results)}个片段")
        
        # 第2轮：精准检索
        top_k_second = retrieval_strategy.get("top_k_second_round", 15)
        min_score_second = retrieval_strategy.get("min_score_second_round", 0.5)
        
        # 构建第2轮查询（基于第1轮的高分结果）
        if first_round_results:
            top_3_contents = [r["content"][:200] for r in first_round_results[:3]]
            query_second = f"{query_first} 相关规则 禁止 要求"
            logger.info(f"第2轮检索: top_k={top_k_second}, min_score={min_score_second}")
        else:
            query_second = query_first
            logger.info(f"第1轮无结果，使用相同查询进行第2轮")
        
        response_second = client.search(query=query_second, top_k=top_k_second, min_score=min_score_second)
        
        # 处理第2轮结果
        second_round_results = []
        if response_second.code == 0 and response_second.chunks:
            for chunk in response_second.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                second_round_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        logger.info(f"第2轮检索结果: {len(second_round_results)}个片段")
        
        # 合并两轮结果，去重（按doc_id）
        all_results_dict = {}
        for result in first_round_results + second_round_results:
            doc_id = result["doc_id"]
            if doc_id not in all_results_dict:
                all_results_dict[doc_id] = result
            else:
                # 保留分数更高的结果
                if result["score"] > all_results_dict[doc_id]["score"]:
                    all_results_dict[doc_id] = result
        
        # 按分数排序，取top-10
        ranked_results = sorted(all_results_dict.values(), key=lambda x: x["score"], reverse=True)[:10]
        
        logger.info(f"=== 最终结果 ===")
        logger.info(f"结果数量: {len(ranked_results)}")
        if ranked_results:
            logger.info(f"最高分: {ranked_results[0]['score']:.4f}")
            logger.info(f"最低分: {ranked_results[-1]['score']:.4f}")
        
        return JudgeRetrievalEnhancedOutput(retrieval_results=ranked_results)
        
    except Exception as e:
        logger.error(f"增强检索发生异常: {str(e)}", exc_info=True)
        return JudgeRetrievalEnhancedOutput(retrieval_results=[])


# ==================== 行为判断类拓宽上下文节点 ====================

