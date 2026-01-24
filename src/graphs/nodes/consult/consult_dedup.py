"""
咨询类去重和重排序算法模块

实现咨询类循环检索的去重和优化算法：
- 轮内去重：贪心聚类 + MMR重排序
- 轮间去重：基于Jaccard相似度的简单去重

关键参数：
- 轮内Jaccard阈值：0.70
- 轮间Jaccard阈值：0.75
- MMR lambda：0.85（比行为判断类稍低，保留更多多样性）
- MMR top_k：10
"""

import logging
from typing import List, Dict, Set

# 配置日志
logger = logging.getLogger("consult_dedup")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler("/app/work/logs/bypass/app.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==================== 基础工具函数 ====================

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


# ==================== 轮内去重算法 ====================

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
    
    logger.info(f"贪心聚类完成: 共{len(clusters)}个聚类（阈值={similarity_threshold}）")
    for i, cluster in enumerate(clusters):
        avg_score = sum(r["score"] for r in cluster) / len(cluster)
        logger.info(f"  聚类[{i}]: {len(cluster)}个片段, 平均分={avg_score:.4f}")
    
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
    lambda_param: float = 0.85,
    top_k: int = 10
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
    
    if max_score == min_score:
        normalized_scores = [1.0] * len(scores)
    else:
        normalized_scores = [
            (s - min_score) / (max_score - min_score)
            for s in scores
        ]
    
    # 创建带标准化分数的结果列表
    normalized_results = []
    for idx, result in enumerate(results):
        normalized_results.append({
            "content": result["content"],
            "score": result["score"],
            "normalized_score": normalized_scores[idx],
            "doc_id": result.get("doc_id", ""),
            "file_name": result.get("file_name", "")
        })
    
    # MMR算法
    selected_indices = []
    remaining_indices = list(range(len(normalized_results)))
    
    # 选择第一个结果（相关性最高的）
    first_idx = max(range(len(normalized_results)), key=lambda i: normalized_results[i]["normalized_score"])
    selected_indices.append(first_idx)
    remaining_indices.remove(first_idx)
    
    # 迭代选择后续结果
    while len(selected_indices) < top_k and remaining_indices:
        best_idx = None
        best_score = -float('inf')
        
        for idx in remaining_indices:
            # 计算相关性
            relevance = normalized_results[idx]["normalized_score"]
            
            # 计算与已选结果的最大相似度（惩罚项）
            max_similarity = 0.0
            for selected_idx in selected_indices:
                similarity = calculate_jaccard_similarity(
                    normalized_results[idx]["content"],
                    normalized_results[selected_idx]["content"]
                )
                max_similarity = max(max_similarity, similarity)
            
            # MMR分数 = lambda * 相关性 - (1 - lambda) * 最大相似度
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
            
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        
        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        else:
            break
    
    # 构建结果列表
    reranked_results = []
    for idx in selected_indices:
        result = normalized_results[idx].copy()
        # 移除normalized_score字段（不需要传递到下游）
        result.pop("normalized_score", None)
        reranked_results.append(result)
    
    logger.info(f"MMR重排序完成: 从{len(results)}个片段中选择了{len(reranked_results)}个（lambda={lambda_param}, top_k={top_k}）")
    
    return reranked_results


def intra_round_deduplication(
    results: List[Dict],
    similarity_threshold: float = 0.70,
    mmr_lambda: float = 0.85,
    mmr_top_k: int = 10
) -> List[Dict]:
    """
    轮内去重流程：聚类 → 选代表 → MMR重排序
    
    Args:
        results: 检索结果列表
        similarity_threshold: Jaccard相似度阈值
        mmr_lambda: MMR相关性权重
        mmr_top_k: MMR返回的top-k数量
    
    Returns:
        去重并重排序后的结果列表
    """
    if not results:
        return []
    
    logger.info(f"=== 轮内去重开始 ===")
    logger.info(f"输入: {len(results)}个片段")
    
    # 步骤1：贪心聚类
    clusters = greedy_clustering(results, similarity_threshold=similarity_threshold)
    
    # 步骤2：选择代表片段
    representatives = select_representative_chunks(clusters)
    
    # 步骤3：MMR重排序
    reranked = mmr_rerank(representatives, lambda_param=mmr_lambda, top_k=mmr_top_k)
    
    logger.info(f"=== 轮内去重完成 ===")
    logger.info(f"输出: {len(reranked)}个片段")
    
    return reranked


# ==================== 轮间去重算法 ====================

def jaccard_dedup(
    all_results: List[Dict],
    similarity_threshold: float = 0.75
) -> List[Dict]:
    """
    基于Jaccard相似度的简单去重（用于轮间去重）
    
    Args:
        all_results: 所有结果列表（历史+当前）
        similarity_threshold: Jaccard相似度阈值
    
    Returns:
        去重后的结果列表
    """
    if not all_results:
        return []
    
    logger.info(f"=== 轮间去重开始 ===")
    logger.info(f"输入: {len(all_results)}个片段")
    
    # 按分数降序排序
    sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)
    
    deduped_results = []
    
    for result in sorted_results:
        is_duplicate = False
        
        # 检查是否与已选结果相似
        for selected in deduped_results:
            similarity = calculate_jaccard_similarity(
                result["content"],
                selected["content"]
            )
            if similarity >= similarity_threshold:
                is_duplicate = True
                logger.debug(f"发现重复片段 (相似度={similarity:.4f}, threshold={similarity_threshold})")
                break
        
        if not is_duplicate:
            deduped_results.append(result)
    
    logger.info(f"=== 轮间去重完成 ===")
    logger.info(f"输出: {len(deduped_results)}个片段（去除了{len(all_results) - len(deduped_results)}个重复片段）")
    
    return deduped_results


# ==================== 轮间去重增强版（支持历史+当前合并） ====================

def merge_and_dedup(
    history_results: List[Dict],
    current_results: List[Dict],
    similarity_threshold: float = 0.75
) -> List[Dict]:
    """
    合并历史结果和当前结果，并进行去重
    
    Args:
        history_results: 历史结果列表
        current_results: 当前结果列表
        similarity_threshold: Jaccard相似度阈值
    
    Returns:
        去重后的合并结果列表（保留所有来源标记）
    """
    logger.info(f"=== 合并并去重开始 ===")
    logger.info(f"历史结果: {len(history_results)}个片段")
    logger.info(f"当前结果: {len(current_results)}个片段")
    
    # 合并所有结果
    all_results = history_results + current_results
    
    # 执行去重
    deduped = jaccard_dedup(all_results, similarity_threshold=similarity_threshold)
    
    logger.info(f"=== 合并并去重完成 ===")
    logger.info(f"输出: {len(deduped)}个片段")
    
    return deduped
