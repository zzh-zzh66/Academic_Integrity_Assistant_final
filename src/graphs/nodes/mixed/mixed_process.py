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

def mixed_process_node(
    state: MixedProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedProcessOutput:
    """
    title: 混合类意图处理
    desc: 拆分为咨询部分和行为判断部分，分别提取关键信息，使用术语预处理节点的输出增强查询
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
        
        # 解析JSON响应
        result = {
            "consult_query": "",
            "consult_keywords": [],
            "consult_focus": "其他",
            "judge_query": state.user_query,
            "judge_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "behavior_subject": state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            "behavior_action": state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            "behavior_object": state.behavior_analysis.get("对象", "") if state.behavior_analysis else ""
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "consult_query" in parsed_result:
                    result["consult_query"] = parsed_result["consult_query"]
                if "consult_keywords" in parsed_result:
                    result["consult_keywords"] = parsed_result["consult_keywords"]
                if "consult_focus" in parsed_result:
                    result["consult_focus"] = parsed_result["consult_focus"]
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
            except json.JSONDecodeError:
                pass
        
        return MixedProcessOutput(
            consult_query=result["consult_query"],
            consult_keywords=result["consult_keywords"],
            consult_focus=result["consult_focus"],
            judge_query=result["judge_query"],
            judge_keywords=result["judge_keywords"],
            behavior_subject=result["behavior_subject"],
            behavior_action=result["behavior_action"],
            behavior_object=result["behavior_object"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return MixedProcessOutput(
            consult_query="",
            consult_keywords=[],
            consult_focus="其他",
            judge_query=state.user_query,
            judge_keywords=state.extracted_keywords if state.extracted_keywords else [],
            behavior_subject=state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            behavior_action=state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            behavior_object=state.behavior_analysis.get("对象", "") if state.behavior_analysis else ""
        )


