"""
混合类行为判断分支包装节点
用于封装行为判断类的查询优化、增强检索、拓宽上下文和违规判断逻辑，避免与行为判断类主分支冲突
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    JudgeQueryOptimizeInput,
    JudgeQueryOptimizeOutput,
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)

class MixedJudgeQueryOptimizeOutput(BaseModel):
    """混合类行为判断查询优化包装节点的输出（移除冲突字段）"""
    optimized_query: str = Field(default="", description="优化后的查询语句")
    optimized_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    optimization_reason: str = Field(default="", description="优化原因说明")
    # 不包含 retrieval_strategy，避免与 consult 分支冲突

def mixed_judge_query_optimize_wrapper(
    state: JudgeQueryOptimizeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedJudgeQueryOptimizeOutput:
    """
    title: 混合类行为判断查询优化包装
    desc: 封装行为判断查询优化节点，用于混合类分支（移除冲突字段）
    integrations: 大语言模型
    """
    from graphs.nodes.judge import judge_query_optimize_node
    
    # 调用原始节点
    result = judge_query_optimize_node(state, config, runtime)
    
    # 返回新的 Output，只包含不冲突的字段
    return MixedJudgeQueryOptimizeOutput(
        optimized_query=result.optimized_query,
        optimized_keywords=result.optimized_keywords,
        optimization_reason=result.optimization_reason
    )


class MixedJudgeRetrievalEnhancedOutput(BaseModel):
    """混合类行为判断增强检索包装节点的输出"""
    judge_retrieval_results: List[dict] = Field(default=[], description="判断部分检索结果（混合类使用）")

def mixed_judge_retrieval_enhanced_wrapper(
    state: JudgeRetrievalEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedJudgeRetrievalEnhancedOutput:
    """
    title: 混合类行为判断增强检索包装
    desc: 封装行为判断增强检索节点，用于混合类分支
    integrations: 知识库, 大语言模型（重排序）
    """
    from graphs.nodes.judge import judge_retrieval_enhanced_node
    
    # 调用原始节点
    result = judge_retrieval_enhanced_node(state, config, runtime)
    
    # 返回新的 Output，使用 judge_retrieval_results 字段
    return MixedJudgeRetrievalEnhancedOutput(
        judge_retrieval_results=result.retrieval_results
    )


def mixed_judge_context_expand_enhanced_wrapper(
    state: JudgeContextExpandEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeContextExpandEnhancedOutput:
    """
    title: 混合类行为判断拓宽上下文包装
    desc: 封装行为判断拓宽上下文节点，用于混合类分支
    integrations: 知识库, 大语言模型
    """
    from graphs.nodes.judge import judge_context_expand_enhanced_node
    return judge_context_expand_enhanced_node(state, config, runtime)


def mixed_judge_decision_wrapper(
    state: JudgeDecisionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeDecisionOutput:
    """
    title: 混合类行为判断违规判断包装
    desc: 封装行为判断违规判断节点，用于混合类分支
    integrations: 大语言模型
    """
    from graphs.nodes.judge import judge_decision_node
    return judge_decision_node(state, config, runtime)
