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

