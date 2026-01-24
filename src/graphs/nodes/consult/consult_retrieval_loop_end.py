import os
import json
import re
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    ConsultProcessInput,
    ConsultProcessOutput,
    ConsultRetrievalInput,
    ConsultRetrievalOutput,
    ConsultContextExpandInput,
    ConsultContextExpandOutput,
    ConsultRerankInput,
    ConsultRerankOutput,
    ConsultRetrievalLoopState,
    ConsultRetrievalLoopStartInput,
    ConsultRetrievalLoopStartOutput,
    ConsultRetrievalLoopEndInput,
    ConsultRetrievalLoopEndOutput,
    ComplexityInput,
    ComplexityOutput,
    ConsultQueryOptimizeInput,
    ConsultQueryOptimizeOutput,
    RerankInput,
    RerankOutput,
    ContextExtractInput,
    ContextExtractOutput,
    ImprovementAnalysisInput,
    ImprovementAnalysisOutput,
    ConsultRetrievalLoopNodeInput,
    ConsultRetrievalLoopNodeOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks,
    get_fallback_response
)

def consult_retrieval_loop_end_node(
    state: ConsultRetrievalLoopEndInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopEndOutput:
    """
    title: 咨询类循环检索出口
    desc: 根据循环检索的最终状态，返回最终结果或兜底回答
    integrations: 无
    """
    ctx = runtime.context
    
    loop_state = state.loop_state
    
    # 判断是否需要兜底回答
    is_fallback = False
    fallback_message = ""
    final_results = loop_state.retrieval_results
    
    # 初始化历史和当前结果
    history_results = loop_state.previous_retrieval_results if loop_state.previous_retrieval_results else []
    current_results = loop_state.retrieval_results
    
    # 如果退出原因是 fallback，使用兜底回答
    if loop_state.exit_reason == "fallback":
        is_fallback = True
        fallback_message = get_fallback_response("咨询类")
        final_results = []
        history_results = []
        current_results = []
    
    # 如果退出原因是 score_decreased，使用上一轮结果
    elif loop_state.exit_reason == "score_decreased":
        if loop_state.previous_retrieval_results:
            final_results = loop_state.previous_retrieval_results
            history_results = loop_state.previous_retrieval_results
            current_results = []  # 分数下降，放弃当前结果
        else:
            # 如果没有上一轮结果，使用兜底回答
            is_fallback = True
            fallback_message = get_fallback_response("咨询类")
            final_results = []
            history_results = []
            current_results = []
    
    # 其他情况（success、target_score_reached、max_rounds_reached），使用当前结果
    else:
        final_results = loop_state.retrieval_results
        is_fallback = False
        fallback_message = ""
    
    return ConsultRetrievalLoopEndOutput(
        retrieval_results=final_results,
        history_results=history_results,
        current_results=current_results,
        is_fallback=is_fallback,
        fallback_message=fallback_message
    )


# ==================== 查询复杂度判断节点 ====================

