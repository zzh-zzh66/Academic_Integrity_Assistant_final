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

def judge_retrieval_node(
    state: JudgeRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeRetrievalOutput:
    """
    title: 行为判断类知识库检索
    desc: 根据行为判断类意图检索相关规范，确保与用户描述的行为高度一致
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        # 构建检索查询 - 使用行为分析增强查询
        query = state.user_query
        
        # 优先使用优化后的查询
        if state.refined_query:
            query = state.refined_query
        
        # 添加行为分析信息（如果有的话）
        if state.behavior_subject or state.behavior_action or state.behavior_object:
            behavior_parts = []
            if state.behavior_subject:
                behavior_parts.append(f"主体:{state.behavior_subject}")
            if state.behavior_action:
                behavior_parts.append(f"动作:{state.behavior_action}")
            if state.behavior_object:
                behavior_parts.append(f"对象:{state.behavior_object}")
            query = f"{query} {' '.join(behavior_parts)}"
        
        # 添加关键词（如果有）
        keywords = state.refined_keywords if state.refined_keywords else state.extracted_keywords
        if keywords:
            keywords_str = " ".join(keywords)
            query = f"{query} {keywords_str}"
        
        # 执行检索：行为判断类需要更多候选用于后续筛选
        response = client.search(
            query=query,
            top_k=15,
            min_score=0.5
        )
        
        # 处理检索结果
        retrieval_results = []
        can_judge = True
        
        if response.code == 0 and response.chunks:
            # 检查最高分是否达到阈值
            if response.chunks and response.chunks[0].score < 0.5:
                can_judge = False
            
            for chunk in response.chunks:
                # 提取文件名
                file_name = extract_file_name_from_content(chunk.content)
                
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        else:
            can_judge = False
        
        return JudgeRetrievalOutput(
            retrieval_results=retrieval_results,
            can_judge=can_judge
        )
        
    except Exception as e:
        # 发生错误时返回空结果，无法判断
        return JudgeRetrievalOutput(
            retrieval_results=[],
            can_judge=False
        )


