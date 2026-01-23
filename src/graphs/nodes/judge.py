import os
import json
import re
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
    JudgeQueryOptimizeOutput,
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)
from graphs.nodes.common import extract_file_name_from_content, expand_content_around_chunk


def judge_process_node(
    state: JudgeProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeProcessOutput:
    """
    title: 行为判断类意图处理
    desc: 拆解行为要素，判断是否需要补充信息，使用术语预处理节点的输出增强查询
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)

    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))

    # 获取术语预处理节点的输出（通过 state 参数）
    enhanced_query = state.enhanced_query if state.enhanced_query else state.user_query
    standard_terms = state.standard_terms
    expanded_terms = state.expanded_terms
    action_elements = state.action_elements
    object_elements = state.object_elements

    # 构建增强的用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "extracted_keywords": state.extracted_keywords,
        "behavior_analysis": state.behavior_analysis,
        "enhanced_query": enhanced_query,
        "standard_terms": standard_terms,
        "expanded_terms": expanded_terms,
        "action_elements": action_elements,
        "object_elements": object_elements
    })
    
    # 调用大语言模型
    client = LLMClient(ctx=ctx)
    
    messages = [
        {"role": "system", "content": sp},
        {"role": "user", "content": user_prompt_content}
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.3),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 1500),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        # 解析JSON响应
        result = {
            "refined_query": state.user_query,
            "refined_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "behavior_subject": state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            "behavior_action": state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            "behavior_object": state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            "needs_clarification": False,
            "clarification_questions": []
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "refined_query" in parsed_result:
                    result["refined_query"] = parsed_result["refined_query"]
                if "refined_keywords" in parsed_result:
                    result["refined_keywords"] = parsed_result["refined_keywords"]
                if "behavior_subject" in parsed_result:
                    result["behavior_subject"] = parsed_result["behavior_subject"]
                if "behavior_action" in parsed_result:
                    result["behavior_action"] = parsed_result["behavior_action"]
                if "behavior_object" in parsed_result:
                    result["behavior_object"] = parsed_result["behavior_object"]
                if "needs_clarification" in parsed_result:
                    result["needs_clarification"] = parsed_result["needs_clarification"]
                if "clarification_questions" in parsed_result:
                    result["clarification_questions"] = parsed_result["clarification_questions"]
            except json.JSONDecodeError:
                pass
        
        return JudgeProcessOutput(
            refined_query=result["refined_query"],
            refined_keywords=result["refined_keywords"],
            behavior_subject=result["behavior_subject"],
            behavior_action=result["behavior_action"],
            behavior_object=result["behavior_object"],
            needs_clarification=result["needs_clarification"],
            clarification_questions=result["clarification_questions"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return JudgeProcessOutput(
            refined_query=state.user_query,
            refined_keywords=state.extracted_keywords if state.extracted_keywords else [],
            behavior_subject=state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            behavior_action=state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            behavior_object=state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            needs_clarification=False,
            clarification_questions=[]
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


def judge_rerank_node(
    state: JudgeRerankInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeRerankOutput:
    """
    title: 行为判断类重排序
    desc: 对行为判断类扩展结果进行高精度评分和排序，筛选出最相关的 3 条结果
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    try:
        # 读取配置文件
        cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
        with open(cfg_file, 'r', encoding='utf-8') as fd:
            _cfg = json.load(fd)
        
        llm_config = _cfg.get("config", {})
        sp = _cfg.get("sp", "")
        up_tpl = Template(_cfg.get("up", ""))
        
        # 渲染用户提示词
        user_prompt_content = up_tpl.render({
            "user_query": state.user_query,
            "expanded_results": state.expanded_results
        })
        
        # 调用大语言模型
        client = LLMClient(ctx=ctx)
        
        messages = [
            {"role": "system", "content": sp},
            {"role": "user", "content": user_prompt_content}
        ]
        
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.0),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        response_text = response_text.strip()
        
        # 解析 JSON 响应
        try:
            # 提取 JSON 内容
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result_json = json.loads(json_str)
                ranked_results = result_json.get("ranked_results", [])
                can_judge = result_json.get("can_judge", True)
            else:
                # 无法解析 JSON，返回原始结果
                ranked_results = state.expanded_results[:3]
                can_judge = len(state.expanded_results) > 0
        except Exception as e:
            # 解析失败，返回原始结果
            ranked_results = state.expanded_results[:3]
            can_judge = len(state.expanded_results) > 0
        
        return JudgeRerankOutput(
            retrieval_results=ranked_results,
            can_judge=can_judge
        )
        
    except Exception as e:
        # 发生错误时返回前 3 条原始结果，并标记为无法判断
        return JudgeRerankOutput(
            retrieval_results=state.expanded_results[:3],
            can_judge=False
        )


# ==================== 行为判断类增强节点 ====================

def judge_query_optimize_node(
    state: JudgeQueryOptimizeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeQueryOptimizeOutput:
    """
    title: 行为判断类查询优化
    desc: 根据查询复杂度动态调整检索策略，优化查询语句和关键词
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "query_complexity": state.query_complexity,
        "refined_query": state.refined_query,
        "refined_keywords": state.refined_keywords,
        "behavior_subject": state.behavior_subject,
        "behavior_action": state.behavior_action,
        "behavior_object": state.behavior_object,
        "standard_terms": state.standard_terms,
        "expanded_terms": state.expanded_terms
    })
    
    # 调用大语言模型
    client = LLMClient(ctx=ctx)
    
    messages = [
        {"role": "system", "content": sp},
        {"role": "user", "content": user_prompt_content}
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.3),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 1000),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        response_text = response_text.strip()
        
        # 解析JSON响应
        result = {
            "optimized_query": state.refined_query if state.refined_query else state.user_query,
            "optimized_keywords": state.refined_keywords if state.refined_keywords else state.extracted_keywords if hasattr(state, 'extracted_keywords') else [],
            "retrieval_strategy": {
                "top_k_first_round": 20,
                "min_score_first_round": 0.3,
                "top_k_second_round": 15,
                "min_score_second_round": 0.5,
                "max_rounds": 2,
                "target_score": 0.65,
                "min_score_threshold": 0.65
            },
            "optimization_reason": "默认优化策略（标准查询）：第1轮扩大检索范围到20个候选，第2轮精准筛选15个高质量结果"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "optimized_query" in parsed_result:
                    result["optimized_query"] = parsed_result["optimized_query"]
                if "optimized_keywords" in parsed_result:
                    result["optimized_keywords"] = parsed_result["optimized_keywords"]
                if "retrieval_strategy" in parsed_result:
                    result["retrieval_strategy"] = parsed_result["retrieval_strategy"]
                if "optimization_reason" in parsed_result:
                    result["optimization_reason"] = parsed_result["optimization_reason"]
            except json.JSONDecodeError:
                pass
        
        return JudgeQueryOptimizeOutput(
            optimized_query=result["optimized_query"],
            optimized_keywords=result["optimized_keywords"],
            retrieval_strategy=result["retrieval_strategy"],
            optimization_reason=result["optimization_reason"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return JudgeQueryOptimizeOutput(
            optimized_query=state.refined_query if state.refined_query else state.user_query,
            optimized_keywords=state.refined_keywords if state.refined_keywords else state.extracted_keywords if hasattr(state, 'extracted_keywords') else [],
            retrieval_strategy={
                "top_k_first_round": 20,
                "min_score_first_round": 0.3,
                "top_k_second_round": 15,
                "min_score_second_round": 0.5,
                "max_rounds": 2,
                "target_score": 0.65,
                "min_score_threshold": 0.65
            },
            optimization_reason="默认优化策略（标准查询）：第1轮扩大检索范围到20个候选，第2轮精准筛选15个高质量结果"
        )

