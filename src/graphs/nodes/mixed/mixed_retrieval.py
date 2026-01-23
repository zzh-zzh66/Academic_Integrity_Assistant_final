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

def mixed_retrieval_node(
    state: MixedRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedRetrievalOutput:
    """
    title: 混合类知识库检索
    desc: 根据混合类意图检索，分两路检索后合并（咨询路+判断路）
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        all_results = []
        
        # 第一路：咨询类检索
        consult_query = state.consult_query if state.consult_query else state.user_query
        if state.consult_keywords:
            consult_query = f"{consult_query} {' '.join(state.consult_keywords)}"
        if state.consult_focus:
            consult_query = f"{consult_query} {state.consult_focus}"
        consult_query = f"{consult_query} 定义 要求 规范"
        
        consult_response = client.search(
            query=consult_query,
            top_k=15,
            min_score=0.3
        )
        
        if consult_response.code == 0 and consult_response.chunks:
            for chunk in consult_response.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                all_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name,
                    "source": "consult"
                })
        
        # 第二路：判断类检索
        judge_query = state.judge_query if state.judge_query else state.user_query
        
        # 添加行为分析信息
        if state.behavior_subject or state.behavior_action or state.behavior_object:
            behavior_parts = []
            if state.behavior_subject:
                behavior_parts.append(f"主体:{state.behavior_subject}")
            if state.behavior_action:
                behavior_parts.append(f"动作:{state.behavior_action}")
            if state.behavior_object:
                behavior_parts.append(f"对象:{state.behavior_object}")
            judge_query = f"{judge_query} {' '.join(behavior_parts)}"
        
        if state.judge_keywords:
            judge_query = f"{judge_query} {' '.join(state.judge_keywords)}"
        
        judge_response = client.search(
            query=judge_query,
            top_k=15,
            min_score=0.5
        )
        
        if judge_response.code == 0 and judge_response.chunks:
            for chunk in judge_response.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                all_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name,
                    "source": "judge"
                })
        
        # 合并去重（按doc_id去重），保留最高分
        unique_results = {}
        for result in all_results:
            doc_id = result["doc_id"]
            if doc_id not in unique_results:
                unique_results[doc_id] = result
            else:
                # 保留分数更高的结果
                if result["score"] > unique_results[doc_id]["score"]:
                    unique_results[doc_id] = result
        
        # 按分数排序，取top 6
        sorted_results = sorted(unique_results.values(), key=lambda x: x["score"], reverse=True)[:6]
        
        return MixedRetrievalOutput(
            retrieval_results=sorted_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return MixedRetrievalOutput(
            retrieval_results=[]
        )


