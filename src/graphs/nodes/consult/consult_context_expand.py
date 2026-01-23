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

def consult_context_expand_node(
    state: ConsultContextExpandInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultContextExpandOutput:
    """
    title: 咨询类上下文扩展
    desc: 扩展咨询类检索结果，获取完整段落（500-800字）
    """
    ctx = runtime.context
    
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            
            # 扩展内容到 500-800 字
            expanded_content = expand_content_around_chunk(original_content, target_length=650)
            
            expanded_results.append({
                "content": expanded_content,
                "score": result.get("score", 0.0),
                "doc_id": result.get("doc_id", ""),
                "file_name": result.get("file_name", "")
            })
        
        return ConsultContextExpandOutput(
            expanded_results=expanded_results
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return ConsultContextExpandOutput(
            expanded_results=state.retrieval_results
        )


