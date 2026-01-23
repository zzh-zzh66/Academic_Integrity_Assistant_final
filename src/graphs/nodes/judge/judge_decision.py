import os
import json
import logging
import re
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

logger = logging.getLogger(__name__)

from graphs.state import (
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks
)

def judge_decision_node(
    state: JudgeDecisionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeDecisionOutput:
    """
    title: 行为判断类违规判断
    desc: 基于拓宽的上下文判断是否违规，并评估置信度
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
    
    logger.info("=== 行为判断类违规判断开始 ===")
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"完整段落数: {len(state.full_context_paragraphs)}")
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "full_context_paragraphs": state.full_context_paragraphs,
        "related_rules": state.related_rules,
        "decision_basis": state.decision_basis,
        "behavior_subject": state.behavior_subject,
        "behavior_action": state.behavior_action,
        "behavior_object": state.behavior_object
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
            temperature=llm_config.get("temperature", 0.1),
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
            "can_judge": True,
            "is_violation": False,
            "judgment_basis": state.decision_basis,
            "relevant_rules": state.related_rules,
            "confidence_score": 0.7,
            "confidence_level": "medium",
            "needs_clarification": False,
            "clarification_questions": [],
            "missing_information": [],
            "ambiguity_reasons": [],
            "suggested_actions": [],
            "warning_notes": []
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "can_judge" in parsed_result:
                    result["can_judge"] = parsed_result["can_judge"]
                if "is_violation" in parsed_result:
                    result["is_violation"] = parsed_result["is_violation"]
                if "judgment_basis" in parsed_result:
                    result["judgment_basis"] = parsed_result["judgment_basis"]
                if "relevant_rules" in parsed_result:
                    result["relevant_rules"] = parsed_result["relevant_rules"]
                if "confidence_score" in parsed_result:
                    result["confidence_score"] = parsed_result["confidence_score"]
                if "confidence_level" in parsed_result:
                    result["confidence_level"] = parsed_result["confidence_level"]
                if "needs_clarification" in parsed_result:
                    result["needs_clarification"] = parsed_result["needs_clarification"]
                if "clarification_questions" in parsed_result:
                    result["clarification_questions"] = parsed_result["clarification_questions"]
                if "missing_information" in parsed_result:
                    result["missing_information"] = parsed_result["missing_information"]
                if "ambiguity_reasons" in parsed_result:
                    result["ambiguity_reasons"] = parsed_result["ambiguity_reasons"]
                if "suggested_actions" in parsed_result:
                    result["suggested_actions"] = parsed_result["suggested_actions"]
                if "warning_notes" in parsed_result:
                    result["warning_notes"] = parsed_result["warning_notes"]
            except json.JSONDecodeError:
                pass
        
        logger.info(f"判断结果: can_judge={result['can_judge']}, is_violation={result.get('is_violation', None)}")
        logger.info(f"置信度: {result['confidence_score']:.2f} ({result['confidence_level']})")
        
        return JudgeDecisionOutput(**result)
        
    except Exception as e:
        logger.error(f"违规判断发生异常: {str(e)}", exc_info=True)
        return JudgeDecisionOutput(
            can_judge=False,
            is_violation=None,
            judgment_basis="处理异常，无法进行判断",
            relevant_rules=[],
            confidence_score=0.0,
            confidence_level="low",
            needs_clarification=False,
            clarification_questions=[],
            missing_information=[],
            ambiguity_reasons=[],
            suggested_actions=[],
            warning_notes=[]
        )
