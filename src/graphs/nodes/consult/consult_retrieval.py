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

def consult_retrieval_node(
    state: ConsultRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultRetrievalOutput:
    """
    title: 咨询类知识库检索
    desc: 根据咨询类意图检索学术道德规范相关内容，获取更详细的说明和定义
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        # 构建检索查询
        query = state.user_query
        
        # 优先使用优化后的查询
        if state.refined_query:
            query = state.refined_query
        
        # 添加咨询焦点（如果有）
        if state.consult_focus:
            query = f"{query} {state.consult_focus}"
        
        # 添加关键词（如果有）
        keywords = state.refined_keywords if state.refined_keywords else state.extracted_keywords
        if keywords:
            keywords_str = " ".join(keywords)
            query = f"{query} {keywords_str}"
        
        # 添加咨询类增强词
        query = f"{query} 定义 要求 规范 说明"
        
        # 执行检索：咨询类需要更多信息，降低阈值
        response = client.search(
            query=query,
            top_k=15,
            min_score=0.3
        )
        
        # 处理检索结果
        retrieval_results = []
        if response.code == 0 and response.chunks:
            for chunk in response.chunks:
                # 提取文件名
                file_name = extract_file_name_from_content(chunk.content)
                
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        return ConsultRetrievalOutput(
            retrieval_results=retrieval_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return ConsultRetrievalOutput(
            retrieval_results=[]
        )


