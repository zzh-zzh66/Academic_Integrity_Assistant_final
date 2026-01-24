"""
咨询类结果整合节点
用于整合多轮检索结果，合并去重并生成统一输出
"""

import logging
import re
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import ConsultResultsConsolidationInput, ConsultResultsConsolidationOutput
from graphs.nodes.consult.consult_dedup import merge_and_dedup

# 配置日志
logger = logging.getLogger("consult_consolidation")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler("/app/work/logs/bypass/app.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def consult_results_consolidation_node(
    state: ConsultResultsConsolidationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultResultsConsolidationOutput:
    """
    title: 咨询类结果整合
    desc: 整合多轮检索结果，合并去重并生成统一输出
    integrations: 无（纯计算）
    """
    ctx = runtime.context
    
    logger.info("=" * 80)
    logger.info("咨询类结果整合节点开始执行")
    logger.info("=" * 80)
    
    # 步骤1：合并历史和当前结果
    logger.info(f"=== 步骤1：合并结果 ===")
    logger.info(f"历史结果: {len(state.history_results)}个片段")
    logger.info(f"当前结果: {len(state.current_results)}个片段")
    
    all_results = state.history_results + state.current_results
    
    if not all_results:
        logger.warning("没有检索结果，返回空结果")
        return ConsultResultsConsolidationOutput(
            unified_results=[],
            total_count=0,
            avg_score=0.0,
            max_score=0.0,
            top_3_contents=[],
            summary="未检索到相关资料"
        )
    
    # 步骤2：轮间去重（Jaccard 0.75）
    logger.info(f"=== 步骤2：轮间去重 ===")
    deduped_results = merge_and_dedup(
        history_results=state.history_results,
        current_results=state.current_results,
        similarity_threshold=0.75
    )
    
    # 步骤3：质量过滤（score >= 0.3）
    logger.info(f"=== 步骤3：质量过滤 ===")
    filtered_results = [r for r in deduped_results if r.get("score", 0.0) >= 0.3]
    logger.info(f"过滤后: {len(filtered_results)}个片段（score >= 0.3）")
    
    if not filtered_results:
        logger.warning("过滤后没有结果，返回空结果")
        return ConsultResultsConsolidationOutput(
            unified_results=[],
            total_count=0,
            avg_score=0.0,
            max_score=0.0,
            top_3_contents=[],
            summary="未检索到足够相关的资料"
        )
    
    # 步骤4：重新排序（按分数降序）
    logger.info(f"=== 步骤4：重新排序 ===")
    sorted_results = sorted(filtered_results, key=lambda x: x.get("score", 0.0), reverse=True)
    
    # 步骤5：保留top-15
    logger.info(f"=== 步骤5：保留top-15 ===")
    top_results = sorted_results[:15]
    logger.info(f"最终保留: {len(top_results)}个片段")
    
    # 步骤6：计算评估指标
    logger.info(f"=== 步骤6：计算评估指标 ===")
    total_count = len(top_results)
    
    scores = [r.get("score", 0.0) for r in top_results]
    avg_score = sum(scores) / total_count if total_count > 0 else 0.0
    max_score = max(scores) if scores else 0.0
    
    logger.info(f"总片段数: {total_count}")
    logger.info(f"平均分数: {avg_score:.4f}")
    logger.info(f"最高分数: {max_score:.4f}")
    
    # 步骤7：提取top-3内容
    logger.info(f"=== 步骤7：提取top-3内容 ===")
    top_3_contents = [r.get("content", "") for r in top_results[:3]]
    
    # 步骤8：生成summary（简单规则）
    logger.info(f"=== 步骤8：生成summary ===")
    summary = _generate_summary(total_count, max_score, avg_score, top_3_contents, state.user_query)
    
    logger.info(f"Summary: {summary}")
    logger.info("=" * 80)
    
    return ConsultResultsConsolidationOutput(
        unified_results=top_results,
        total_count=total_count,
        avg_score=avg_score,
        max_score=max_score,
        top_3_contents=top_3_contents,
        summary=summary,
        retrieval_results=top_results  # 供response_generation使用
    )


def _generate_summary(
    total_count: int,
    max_score: float,
    avg_score: float,
    top_3_contents: list,
    user_query: str
) -> str:
    """
    生成检索结果的简要总结（简单规则，不使用LLM）
    
    Args:
        total_count: 总片段数
        max_score: 最高分数
        avg_score: 平均分数
        top_3_contents: top-3内容
        user_query: 用户查询
    
    Returns:
        简要总结文本
    """
    # 基础信息
    summary_parts = [
        f"检索到{total_count}条相关资料",
        f"最高相关性{max_score:.2f}",
        f"平均相关性{avg_score:.2f}"
    ]
    
    # 提取关键词（从top-3内容中）
    keywords = _extract_keywords(top_3_contents, user_query)
    if keywords:
        summary_parts.append(f"涵盖{'、'.join(keywords[:5])}等{len(keywords)}个方面")
    
    return "，".join(summary_parts) + "。"


def _extract_keywords(contents: list, user_query: str) -> list:
    """
    从内容中提取关键词（简单规则）
    
    Args:
        contents: 内容列表
        user_query: 用户查询
    
    Returns:
        关键词列表
    """
    # 合并所有内容
    all_text = " ".join(contents)
    
    # 提取中文关键词（2-6字的词组）
    pattern = r'[\u4e00-\u9fa5]{2,6}'
    keywords = re.findall(pattern, all_text)
    
    # 去重并过滤
    keywords = list(set(keywords))
    
    # 过滤掉常见停用词（简化版）
    stopwords = {
        "的", "是", "在", "了", "和", "与", "或", "等", "及", "以及",
        "这个", "那个", "这些", "那些", "其中", "其中",
        "可以", "应该", "需要", "必须", "包括", "涉及", "关于"
    }
    keywords = [k for k in keywords if k not in stopwords]
    
    # 返回前10个关键词
    return keywords[:10]
