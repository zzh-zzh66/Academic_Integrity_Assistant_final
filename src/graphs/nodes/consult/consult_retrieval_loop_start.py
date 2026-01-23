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

def consult_retrieval_loop_start_node(
    state: ConsultRetrievalLoopStartInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalLoopStartOutput:
    """
    title: 咨询类循环检索入口
    desc: 初始化循环检索状态，准备开始第一轮检索
    integrations: 无
    """
    ctx = runtime.context
    
    # 初始化循环状态
    loop_state = ConsultRetrievalLoopState(
        user_query=state.user_query,
        refined_query=state.refined_query,
        refined_keywords=state.refined_keywords,
        consult_focus=state.consult_focus,
        max_rounds=2,  # 第一阶段固定2轮
        target_score=0.8,
        min_score_threshold=0.65,
        current_round=0,
        previous_score=0.0,
        current_score=0.0,
        retrieval_results=[],
        high_score_chunks=[],
        should_continue=True,
        exit_reason="",
        previous_retrieval_results=[]
    )
    
    return ConsultRetrievalLoopStartOutput(
        loop_state=loop_state
    )


