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
    desc: 整合咨询和判断两部分的结果，使用大模型生成结构化JSON
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
    
    logger.info("=== 混合类结果整合开始 ===")
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"咨询分支结果数: {len(state.consult_retrieval_results)}")
    logger.info(f"判断分支结果数: {len(state.judge_retrieval_results)}")
    logger.info(f"是否能够判断: {state.can_judge}")
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "consult_retrieval_results": json.dumps(state.consult_retrieval_results, ensure_ascii=False),
        "can_judge": state.can_judge,
        "is_violation": state.is_violation,
        "judgment_basis": state.judgment_basis,
        "confidence_score": state.confidence_score,
        "confidence_level": state.confidence_level,
        "judge_retrieval_results": json.dumps(state.judge_retrieval_results, ensure_ascii=False)
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
            temperature=llm_config.get("temperature", 0.2),
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
        
        # 默认结果
        result = {
            "consult_part": {
                "summary": "咨询分支结果摘要",
                "key_points": [],
                "rules_cited": [],
                "retrieval_results": state.consult_retrieval_results
            },
            "judge_part": {
                "is_violation": state.is_violation,
                "can_judge": state.can_judge,
                "judgment_basis": state.judgment_basis,
                "confidence_score": state.confidence_score,
                "confidence_level": state.confidence_level,
                "rules_cited": [],
                "retrieval_results": state.judge_retrieval_results
            },
            "summary": f"咨询部分检索到{len(state.consult_retrieval_results)}个结果，行为判断部分检索到{len(state.judge_retrieval_results)}个结果",
            "overlap_analysis": {
                "has_overlap": False,
                "overlap_content": [],
                "overlap_rules": [],
                "handling_strategy": "去重"
            },
            "merged_reason": "默认整合：直接合并两个分支的结果"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "consult_part" in parsed_result:
                    result["consult_part"] = parsed_result["consult_part"]
                if "judge_part" in parsed_result:
                    result["judge_part"] = parsed_result["judge_part"]
                if "summary" in parsed_result:
                    result["summary"] = parsed_result["summary"]
                if "overlap_analysis" in parsed_result:
                    result["overlap_analysis"] = parsed_result["overlap_analysis"]
                if "merged_reason" in parsed_result:
                    result["merged_reason"] = parsed_result["merged_reason"]
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
        
        logger.info(f"整合完成，摘要: {result['summary'][:100]}")
        
        # 构建检索结果（用于响应生成节点）
        merged_retrieval_results = state.consult_retrieval_results + state.judge_retrieval_results
        
        # 构建判断结果（用于响应生成节点）
        judgment_result = {
            "can_judge": result["judge_part"].get("can_judge", state.can_judge),
            "is_violation": result["judge_part"].get("is_violation", state.is_violation),
            "judgment_basis": result["judge_part"].get("judgment_basis", state.judgment_basis),
            "confidence_score": result["judge_part"].get("confidence_score", state.confidence_score),
            "confidence_level": result["judge_part"].get("confidence_level", state.confidence_level)
        }
        
        return MixedMergeOutput(
            consult_part=result["consult_part"],
            judge_part=result["judge_part"],
            summary=result["summary"],
            overlap_analysis=result["overlap_analysis"],
            retrieval_results=merged_retrieval_results,
            judgment_result=judgment_result,
            merged_reason=result["merged_reason"]
        )
        
    except Exception as e:
        logger.error(f"结果整合发生异常: {str(e)}", exc_info=True)
        # 发生错误时返回默认结果
        merged_retrieval_results = state.consult_retrieval_results + state.judge_retrieval_results
        judgment_result = {
            "can_judge": state.can_judge,
            "is_violation": state.is_violation,
            "judgment_basis": state.judgment_basis,
            "confidence_score": state.confidence_score,
            "confidence_level": state.confidence_level
        }
        return MixedMergeOutput(
            consult_part={
                "summary": "咨询分支结果摘要",
                "key_points": [],
                "rules_cited": [],
                "retrieval_results": state.consult_retrieval_results
            },
            judge_part={
                "is_violation": state.is_violation,
                "can_judge": state.can_judge,
                "judgment_basis": state.judgment_basis,
                "confidence_score": state.confidence_score,
                "confidence_level": state.confidence_level,
                "rules_cited": [],
                "retrieval_results": state.judge_retrieval_results
            },
            summary=f"咨询部分检索到{len(state.consult_retrieval_results)}个结果，行为判断部分检索到{len(state.judge_retrieval_results)}个结果",
            overlap_analysis={
                "has_overlap": False,
                "overlap_content": [],
                "overlap_rules": [],
                "handling_strategy": "去重"
            },
            retrieval_results=merged_retrieval_results,
            judgment_result=judgment_result,
            merged_reason="整合异常，使用默认结果"
        )
