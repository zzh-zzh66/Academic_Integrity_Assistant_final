import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    JudgeProcessInput,
    JudgeProcessOutput,
    JudgeRetrievalInput,
    JudgeRetrievalOutput,
    JudgeContextExpandInput,
    JudgeContextExpandOutput,
    JudgeRerankInput,
    JudgeRerankOutput,
    JudgeQueryOptimizeInput,
    JudgeQueryOptimizeOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks
)

def judge_context_expand_node(
    state: JudgeContextExpandInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeContextExpandOutput:
    """
    title: 行为判断类上下文扩展
    desc: 扩展行为判断类检索结果，获取完整条款（300-500字）
    """
    ctx = runtime.context
    
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            
            # 扩展内容到 300-500 字
            expanded_content = expand_content_around_chunk(original_content, target_length=400)
            
            expanded_results.append({
                "content": expanded_content,
                "score": result.get("score", 0.0),
                "doc_id": result.get("doc_id", ""),
                "file_name": result.get("file_name", "")
            })
        
        return JudgeContextExpandOutput(
            expanded_results=expanded_results
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return JudgeContextExpandOutput(
            expanded_results=state.retrieval_results
        )


