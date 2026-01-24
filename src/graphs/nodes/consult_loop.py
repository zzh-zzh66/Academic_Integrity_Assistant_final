"""
咨询类循环检索节点（调用子图）
这个文件专门用于封装咨询类循环检索节点，避免循环导入
"""

import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    ConsultRetrievalInput,
    ConsultRetrievalOutput,
    ConsultRetrievalLoopState,
    ConsultResultsConsolidationInput
)

# 配置日志
logger = logging.getLogger("consult_loop")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler("/app/work/logs/bypass/app.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def consult_retrieval_loop_node(
    state: ConsultRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalOutput:
    """
    title: 咨询类循环检索（调用子图）
    desc: 通过调用子图实现咨询类的循环检索逻辑，支持动态检索策略
    integrations: 知识库, 大语言模型
    """
    logger.info("=" * 80)
    logger.info("咨询类循环检索节点开始执行")
    logger.info("=" * 80)
    
    # 延迟导入子图，避免循环依赖
    from graphs.loop_graph import consult_retrieval_subgraph
    
    # 从state中获取retrieval_strategy和query_complexity（如果存在）
    retrieval_strategy = getattr(state, 'retrieval_strategy', {}) if hasattr(state, 'retrieval_strategy') else {}
    query_complexity = getattr(state, 'query_complexity', 'standard') if hasattr(state, 'query_complexity') else 'standard'
    
    # 记录输入参数
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"优化查询: {state.refined_query}")
    logger.info(f"查询复杂度: {query_complexity}")
    logger.info(f"检索策略: {retrieval_strategy}")
    
    # 提取动态参数（支持多轮检索策略）
    strategy_max_rounds = retrieval_strategy.get("max_rounds", 2)
    strategy_target_score = retrieval_strategy.get("target_score", 0.75)
    strategy_min_score_threshold = retrieval_strategy.get("min_score_threshold", 0.6)
    
    # 提取多轮检索参数
    strategy_top_k_first_round = retrieval_strategy.get("top_k_first_round", 20)
    strategy_min_score_first_round = retrieval_strategy.get("min_score_first_round", 0.25)
    strategy_top_k_second_round = retrieval_strategy.get("top_k_second_round", 15)
    strategy_min_score_second_round = retrieval_strategy.get("min_score_second_round", 0.55)
    
    # 兼容旧的API（如果没有多轮参数，则回退到单轮参数）
    if "top_k_first_round" not in retrieval_strategy:
        strategy_top_k_first_round = retrieval_strategy.get("top_k", 20)
        strategy_min_score_first_round = retrieval_strategy.get("min_score", 0.25)
        strategy_top_k_second_round = retrieval_strategy.get("top_k", 15)
        strategy_min_score_second_round = retrieval_strategy.get("min_score", 0.55)
    
    # 根据复杂度设置默认参数
    if query_complexity == "simple":
        default_top_k = 10
        default_min_score = 0.4
        default_max_rounds = 1
    elif query_complexity == "complex":
        default_top_k = 20
        default_min_score = 0.25
        default_max_rounds = 3
    else:  # standard
        default_top_k = 15
        default_min_score = 0.3
        default_max_rounds = 2
    
    # 使用retrieval_strategy中的参数（如果有的话）
    max_rounds = strategy_max_rounds if strategy_max_rounds else default_max_rounds
    target_score = strategy_target_score if strategy_target_score else 0.8
    min_score_threshold = strategy_min_score_threshold if strategy_min_score_threshold else 0.65
    
    # 根据复杂度设置不同轮次的参数（作为默认值）
    if query_complexity == "simple":
        # 简单查询：快速聚焦
        default_top_k_first_round = 12
        default_min_score_first_round = 0.35
        default_top_k_second_round = 8
        default_min_score_second_round = 0.65
        default_max_rounds = 2
    elif query_complexity == "complex":
        # 复杂查询：全面覆盖
        default_top_k_first_round = 25
        default_min_score_first_round = 0.2
        default_top_k_second_round = 20
        default_min_score_second_round = 0.5
        default_max_rounds = 2
    else:  # standard
        # 标准查询：平衡策略（方案A）
        default_top_k_first_round = 20
        default_min_score_first_round = 0.25
        default_top_k_second_round = 15
        default_min_score_second_round = 0.55
        default_max_rounds = 2
    
    # 使用retrieval_strategy中的参数（如果有的话），否则使用复杂度默认值
    top_k_first_round = strategy_top_k_first_round if strategy_top_k_first_round else default_top_k_first_round
    min_score_first_round = strategy_min_score_first_round if strategy_min_score_first_round else default_min_score_first_round
    top_k_second_round = strategy_top_k_second_round if strategy_top_k_second_round else default_top_k_second_round
    min_score_second_round = strategy_min_score_second_round if strategy_min_score_second_round else default_min_score_second_round
    max_rounds = strategy_max_rounds if strategy_max_rounds else default_max_rounds
    
    # 记录最终使用的参数
    logger.info(f"最终参数:")
    logger.info(f"  max_rounds: {max_rounds}")
    logger.info(f"  target_score: {target_score}")
    logger.info(f"  min_score_threshold: {min_score_threshold}")
    logger.info(f"  top_k_first_round: {top_k_first_round}, min_score_first_round: {min_score_first_round}")
    logger.info(f"  top_k_second_round: {top_k_second_round}, min_score_second_round: {min_score_second_round}")
    
    # 1. 将父图状态转换为子图状态
    subgraph_state = ConsultRetrievalLoopState(
        user_query=state.user_query,
        refined_query=state.refined_query,
        refined_keywords=state.refined_keywords,
        consult_focus=getattr(state, 'consult_focus', ''),
        # 传递检索策略和复杂度
        retrieval_strategy=retrieval_strategy,
        query_complexity=query_complexity,
        # 循环控制参数
        max_rounds=max_rounds,
        target_score=target_score,
        min_score_threshold=min_score_threshold,
        # 动态参数（简化为2轮）
        top_k_first_round=top_k_first_round,
        top_k_second_round=top_k_second_round,
        top_k_third_round=8,  # 保留兼容性，但不会使用
        min_score_first_round=min_score_first_round,
        min_score_second_round=min_score_second_round,
        min_score_third_round=0.7,  # 保留兼容性，但不会使用
        # 初始化状态
        current_round=0,
        previous_score=0.0,
        current_score=0.0,
        retrieval_results=[],
        high_score_chunks=[],
        exit_reason="",
        previous_retrieval_results=[]
    )
    
    # 2. 调用子图
    # 动态导入子图，避免编译时循环检测
    from graphs.loop_graph import create_consult_retrieval_subgraph
    subgraph = create_consult_retrieval_subgraph()
    logger.info("开始调用子图...")
    subgraph_result_dict = subgraph.invoke(subgraph_state.model_dump())  # type: ignore[attribute-error]
    
    # 记录子图结果
    logger.info("=" * 80)
    logger.info("子图调用完成")
    logger.info("=" * 80)
    logger.info(f"最终轮次: {subgraph_result_dict.get('current_round', 0)}")
    logger.info(f"最终分数: {subgraph_result_dict.get('current_score', 0):.4f}")
    logger.info(f"退出原因: {subgraph_result_dict.get('exit_reason', '')}")
    logger.info(f"检索结果数: {len(subgraph_result_dict.get('retrieval_results', []))}")

    # 3. 判断是否需要兜底回答
    final_results = subgraph_result_dict.get("retrieval_results", [])

    # 如果退出原因是 fallback 或 score_decreased，可能需要特殊处理
    exit_reason = subgraph_result_dict.get("exit_reason", "")
    if exit_reason == "fallback":
        # 分数太低，使用空结果
        logger.warning("退出原因: fallback，使用空结果")
        final_results = []
    elif exit_reason == "score_decreased":
        # 分数下降，使用上一轮结果
        logger.info("退出原因: score_decreased，使用上一轮结果")
        previous_results = subgraph_result_dict.get("previous_retrieval_results", [])
        if previous_results:
            final_results = previous_results
    else:
        logger.info(f"正常退出: {exit_reason}")
    
    logger.info(f"最终返回结果数: {len(final_results)}")
    logger.info("=" * 80)
    
    # 提取历史和当前结果（用于整合节点）
    history_results = subgraph_result_dict.get("previous_retrieval_results", [])
    current_results = subgraph_result_dict.get("retrieval_results", [])
    
    # 如果退出原因是 score_decreased，交换历史和当前
    if exit_reason == "score_decreased":
        history_results = subgraph_result_dict.get("retrieval_results", [])
        current_results = subgraph_result_dict.get("previous_retrieval_results", [])
    
    logger.info(f"历史结果数: {len(history_results)}")
    logger.info(f"当前结果数: {len(current_results)}")
    
    # 4. 将子图输出转换回父图状态
    return ConsultRetrievalOutput(
        retrieval_results=final_results,
        history_results=history_results,
        current_results=current_results
    )
