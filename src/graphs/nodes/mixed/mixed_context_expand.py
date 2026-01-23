import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    MixedProcessInput,
    MixedProcessOutput,
    MixedRetrievalInput,
    MixedRetrievalOutput,
    MixedContextExpandInput,
    MixedContextExpandOutput,
    MixedRerankInput,
    MixedRerankOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks
)

def mixed_context_expand_node(
    state: MixedContextExpandInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedContextExpandOutput:
    """
    title: 混合类上下文扩展
    desc: 扩展混合类检索结果，咨询路扩展到段落（500-800字），判断路扩展到条款（300-500字）
    """
    ctx = runtime.context
    
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            source = result.get("source", "consult")
            
            # 根据来源类型决定扩展长度
            if source == "consult":
                # 咨询路扩展到 500-800 字
                expanded_content = expand_content_around_chunk(original_content, target_length=650)
            else:
                # 判断路扩展到 300-500 字
                expanded_content = expand_content_around_chunk(original_content, target_length=400)
            
            expanded_results.append({
                "content": expanded_content,
                "score": result.get("score", 0.0),
                "doc_id": result.get("doc_id", ""),
                "file_name": result.get("file_name", ""),
                "source": source
            })
        
        return MixedContextExpandOutput(
            expanded_results=expanded_results
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return MixedContextExpandOutput(
            expanded_results=state.retrieval_results
        )


