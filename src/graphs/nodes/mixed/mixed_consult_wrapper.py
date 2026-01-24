"""
混合类咨询分支包装节点
用于封装咨询类的查询优化和循环检索逻辑，避免与咨询类主分支冲突
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    ConsultQueryOptimizeInput,
    ConsultQueryOptimizeOutput,
    ConsultRetrievalInput,
    ConsultRetrievalOutput
)

class MixedConsultQueryOptimizeOutput(BaseModel):
    """混合类咨询查询优化包装节点的输出（移除冲突字段）"""
    optimized_query: str = Field(default="", description="优化后的查询语句")
    optimized_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    optimization_reason: str = Field(default="", description="优化原因说明")
    # 不包含 retrieval_strategy，避免与 judge 分支冲突

def mixed_consult_query_optimize_wrapper(
    state: ConsultQueryOptimizeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedConsultQueryOptimizeOutput:
    """
    title: 混合类咨询查询优化包装
    desc: 封装咨询查询优化节点，用于混合类分支（移除冲突字段）
    integrations: 大语言模型
    """
    from graphs.nodes.consult import consult_query_optimize_node
    
    # 调用原始节点
    result = consult_query_optimize_node(state, config, runtime)
    
    # 返回新的 Output，只包含不冲突的字段
    return MixedConsultQueryOptimizeOutput(
        optimized_query=result.optimized_query,
        optimized_keywords=result.optimized_keywords,
        optimization_reason=result.optimization_reason
    )


class MixedConsultRetrievalLoopOutput(BaseModel):
    """混合类咨询循环检索包装节点的输出"""
    consult_retrieval_results: List[dict] = Field(default=[], description="咨询部分检索结果（混合类使用）")

def mixed_consult_retrieval_loop_wrapper(
    state: ConsultRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedConsultRetrievalLoopOutput:
    """
    title: 混合类咨询循环检索包装
    desc: 封装咨询循环检索节点，用于混合类分支
    integrations: 知识库, 大语言模型
    """
    from graphs.nodes.consult_loop import consult_retrieval_loop_node
    
    # 调用原始节点
    result = consult_retrieval_loop_node(state, config, runtime)
    
    # 返回新的 Output，使用 consult_retrieval_results 字段
    return MixedConsultRetrievalLoopOutput(
        consult_retrieval_results=result.retrieval_results
    )
