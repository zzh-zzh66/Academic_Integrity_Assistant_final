import os
import json
import re
import re
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    MixedSplitInput,
    MixedSplitOutput,
    MixedMergeInput,
    MixedMergeOutput
)

def mixed_split_node(
    state: MixedSplitInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedSplitOutput:
    """
    title: 混合类问题拆分
    desc: 将混合类问题拆分为咨询部分和判断部分
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
        "behavior_analysis": state.behavior_analysis,
        "standard_terms": state.standard_terms,
        "expanded_terms": state.expanded_terms,
        "action_elements": state.action_elements,
        "object_elements": state.object_elements,
        "extracted_keywords": state.extracted_keywords
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
        
        # 解析JSON响应
        result = {
            # 咨询部分
            "consult_query": "",
            "consult_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "consult_focus": "其他",
            "retrieval_strategy_consult": {
                "top_k_first_round": 20,
                "min_score_first_round": 0.25,
                "top_k_second_round": 15,
                "min_score_second_round": 0.55,
                "max_rounds": 2,
                "target_score": 0.75,
                "min_score_threshold": 0.6
            },
            # 判断部分
            "judge_query": state.user_query,
            "judge_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "behavior_subject": state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            "behavior_action": state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            "behavior_object": state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            "retrieval_strategy_judge": {
                "top_k_first_round": 20,
                "min_score_first_round": 0.3,
                "top_k_second_round": 15,
                "min_score_second_round": 0.5,
                "max_rounds": 2,
                "target_score": 0.65,
                "min_score_threshold": 0.65
            }
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                # 咨询部分
                if "consult_query" in parsed_result:
                    result["consult_query"] = parsed_result["consult_query"]
                if "consult_keywords" in parsed_result:
                    result["consult_keywords"] = parsed_result["consult_keywords"]
                if "consult_focus" in parsed_result:
                    result["consult_focus"] = parsed_result["consult_focus"]
                if "retrieval_strategy_consult" in parsed_result:
                    result["retrieval_strategy_consult"] = parsed_result["retrieval_strategy_consult"]
                # 判断部分
                if "judge_query" in parsed_result:
                    result["judge_query"] = parsed_result["judge_query"]
                if "judge_keywords" in parsed_result:
                    result["judge_keywords"] = parsed_result["judge_keywords"]
                if "behavior_subject" in parsed_result:
                    result["behavior_subject"] = parsed_result["behavior_subject"]
                if "behavior_action" in parsed_result:
                    result["behavior_action"] = parsed_result["behavior_action"]
                if "behavior_object" in parsed_result:
                    result["behavior_object"] = parsed_result["behavior_object"]
                if "retrieval_strategy_judge" in parsed_result:
                    result["retrieval_strategy_judge"] = parsed_result["retrieval_strategy_judge"]
            except json.JSONDecodeError:
                pass
        
        return MixedSplitOutput(
            consult_query=result["consult_query"],
            consult_keywords=result["consult_keywords"],
            consult_focus=result["consult_focus"],
            retrieval_strategy_consult=result["retrieval_strategy_consult"],
            judge_query=result["judge_query"],
            judge_keywords=result["judge_keywords"],
            behavior_subject=result["behavior_subject"],
            behavior_action=result["behavior_action"],
            behavior_object=result["behavior_object"],
            retrieval_strategy_judge=result["retrieval_strategy_judge"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return MixedSplitOutput(
            consult_query="",
            consult_keywords=state.extracted_keywords if state.extracted_keywords else [],
            consult_focus="其他",
            retrieval_strategy_consult={
                "top_k_first_round": 20,
                "min_score_first_round": 0.25,
                "top_k_second_round": 15,
                "min_score_second_round": 0.55,
                "max_rounds": 2,
                "target_score": 0.75,
                "min_score_threshold": 0.6
            },
            judge_query=state.user_query,
            judge_keywords=state.extracted_keywords if state.extracted_keywords else [],
            behavior_subject=state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            behavior_action=state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            behavior_object=state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            retrieval_strategy_judge={
                "top_k_first_round": 20,
                "min_score_first_round": 0.3,
                "top_k_second_round": 15,
                "min_score_second_round": 0.5,
                "max_rounds": 2,
                "target_score": 0.65,
                "min_score_threshold": 0.65
            }
        )


# ==================== 混合类整合节点 ====================

