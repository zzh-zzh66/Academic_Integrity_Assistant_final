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

def mixed_merge_node(
    state: MixedMergeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedMergeOutput:
    """
    title: 混合类结果整合
    desc: 整合咨询和判断两部分的结果
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
        "intent_type": state.intent_type,
        "consult_retrieval_results": state.consult_retrieval_results,
        "judge_retrieval_results": state.judge_retrieval_results,
        "can_judge": state.can_judge,
        "is_violation": state.is_violation,
        "judgment_basis": state.judgment_basis,
        "confidence_score": state.confidence_score,
        "confidence_level": state.confidence_level
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
            "retrieval_results": state.consult_retrieval_results + state.judge_retrieval_results,
            "can_judge": state.can_judge,
            "is_violation": state.is_violation,
            "judgment_basis": state.judgment_basis,
            "confidence_score": state.confidence_score,
            "confidence_level": state.confidence_level
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "retrieval_results" in parsed_result:
                    result["retrieval_results"] = parsed_result["retrieval_results"]
                if "can_judge" in parsed_result:
                    result["can_judge"] = parsed_result["can_judge"]
                if "is_violation" in parsed_result:
                    result["is_violation"] = parsed_result["is_violation"]
                if "judgment_basis" in parsed_result:
                    result["judgment_basis"] = parsed_result["judgment_basis"]
                if "confidence_score" in parsed_result:
                    result["confidence_score"] = parsed_result["confidence_score"]
                if "confidence_level" in parsed_result:
                    result["confidence_level"] = parsed_result["confidence_level"]
            except json.JSONDecodeError:
                pass
        
        return MixedMergeOutput(
            retrieval_results=result["retrieval_results"],
            can_judge=result["can_judge"],
            is_violation=result["is_violation"],
            judgment_basis=result["judgment_basis"],
            confidence_score=result["confidence_score"],
            confidence_level=result["confidence_level"]
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return MixedMergeOutput(
            retrieval_results=state.consult_retrieval_results + state.judge_retrieval_results,
            can_judge=state.can_judge,
            is_violation=state.is_violation,
            judgment_basis=state.judgment_basis,
            confidence_score=state.confidence_score,
            confidence_level=state.confidence_level
        )
