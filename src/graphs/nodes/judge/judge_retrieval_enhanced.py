import os
import json
import logging
import math
from typing import List, Dict, Set, Tuple
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

logger = logging.getLogger(__name__)

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


# ==================== 去重和重排序工具函数 ====================

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的Jaccard相似度
    
    Args:
        text1: 文本1
        text2: 文本2
    
    Returns:
        Jaccard相似度（0-1之间）
    """
    # 将文本分词（按空格和标点符号）
    set1 = set(text1.split())
    set2 = set(text2.split())
    
    # 计算交集和并集
    intersection = set1 & set2
    union = set1 | set2
    
    # 避免除以0
    if len(union) == 0:
        return 0.0
    
    return len(intersection) / len(union)


def greedy_clustering(
    results: List[Dict],
    similarity_threshold: float = 0.70
) -> List[List[Dict]]:
    """
    贪心聚类算法，基于Jaccard相似度对检索结果进行聚类
    
    Args:
        results: 检索结果列表，每个元素包含content、score、doc_id等字段
        similarity_threshold: 相似度阈值，高于此值归为同一类
    
    Returns:
        聚类列表，每个元素是一个聚类（包含多个结果）
    """
    if not results:
        return []
    
    # 按分数降序排序
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
    
    clusters = []
    for result in sorted_results:
        assigned = False
        for cluster in clusters:
            # 检查是否与聚类中的任一结果相似
            for cluster_result in cluster:
                similarity = calculate_jaccard_similarity(
                    result["content"],
                    cluster_result["content"]
                )
                if similarity >= similarity_threshold:
                    cluster.append(result)
                    assigned = True
                    break
            if assigned:
                break
        
        if not assigned:
            # 创建新聚类
            clusters.append([result])
    
    logger.info(f"聚类完成: 共{len(clusters)}个聚类")
    return clusters


def select_representative_chunks(
    clusters: List[List[Dict]]
) -> List[Dict]:
    """
    从每个聚类中选择代表性片段（策略A：保留最高分片段）
    
    Args:
        clusters: 聚类列表
    
    Returns:
        代表性片段列表
    """
    representatives = []
    
    for cluster in clusters:
        # 策略A：每个聚类只保留最高分片段
        representative = max(cluster, key=lambda x: x["score"])
        representatives.append(representative)
    
    logger.info(f"选择代表片段: 从{len(clusters)}个聚类中选择了{len(representatives)}个代表片段")
    return representatives


def mmr_rerank(
    results: List[Dict],
    lambda_param: float = 0.88,
    top_k: int = 12
) -> List[Dict]:
    """
    MMR（Maximal Marginal Relevance）重排序算法
    平衡相关性和多样性
    
    Args:
        results: 检索结果列表，每个元素包含content、score等字段
        lambda_param: 相关性权重（0-1之间），越高越重视相关性
        top_k: 返回的top-k结果数量
    
    Returns:
        重排序后的结果列表
    """
    if not results:
        return []
    
    # 标准化分数到0-1之间
    scores = [r["score"] for r in results]
    max_score = max(scores)
    min_score = min(scores)
    
    if max_score - min_score == 0:
        normalized_scores = [1.0 for _ in scores]
    else:
        normalized_scores = [
            (score - min_score) / (max_score - min_score)
            for score in scores
        ]
    
    # 为结果添加标准化分数
    results_with_normalized = [
        {**r, "normalized_score": ns}
        for r, ns in zip(results, normalized_scores)
    ]
    
    selected = []
    remaining = results_with_normalized.copy()
    
    # 选择第一个结果（相关性最高的）
    first_result = max(remaining, key=lambda x: x["normalized_score"])
    selected.append(first_result)
    remaining.remove(first_result)
    
    # 选择剩余的top_k-1个结果
    while len(selected) < top_k and remaining:
        best_idx = -1
        best_score = -1
        
        for idx, candidate in enumerate(remaining):
            # 计算MMR分数
            # MMR = lambda * Rel - (1-lambda) * MaxSim
            relevance = candidate["normalized_score"]
            
            # 计算与已选结果的最大相似度
            max_sim = 0.0
            for s in selected:
                sim = calculate_jaccard_similarity(
                    candidate["content"],
                    s["content"]
                )
                if sim > max_sim:
                    max_sim = sim
            
            # MMR分数
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
            
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        
        if best_idx >= 0:
            selected.append(remaining[best_idx])
            remaining.pop(best_idx)
        else:
            break
    
    logger.info(f"MMR重排序完成: 从{len(results)}个结果中选择了{len(selected)}个（lambda={lambda_param}）")
    return selected

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
        
        # 合并两轮结果（不去重，保留所有片段用于聚类）
        all_results = []
        for result in first_round_results + second_round_results:
            all_results.append(result)
        
        logger.info(f"合并后总结果: {len(all_results)}个片段")
        
        # 步骤1: 贪心聚类（Jaccard, threshold=0.70）
        logger.info("开始贪心聚类...")
        clusters = greedy_clustering(all_results, similarity_threshold=0.70)
        
        # 步骤2: 每个聚类保留最高分片段（策略A）
        logger.info("选择代表片段...")
        representative_chunks = select_representative_chunks(clusters)
        
        # 步骤3: MMR重排序（lambda=0.88, top_k=12）
        logger.info("执行MMR重排序...")
        ranked_results = mmr_rerank(
            representative_chunks,
            lambda_param=0.88,
            top_k=12
        )
        
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
