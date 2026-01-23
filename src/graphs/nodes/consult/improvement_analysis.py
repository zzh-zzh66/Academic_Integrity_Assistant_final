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

def improvement_analysis_node(
    state: ImprovementAnalysisInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ImprovementAnalysisOutput:
    """
    title: 改善分析
    desc: 评估检索结果质量，预测改善潜力，决定是否继续检索
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
        "current_round": state.current_round,
        "previous_prev_score": state.previous_prev_score,
        "previous_score": state.previous_score,
        "current_score": state.current_score,
        "current_retrieval_results": state.current_retrieval_results,
        "structured_context": state.structured_context,
        "previous_context": state.previous_context
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
            "improvement_potential": "moderate",
            "predicted_next_score": state.current_score,
            "score_change_analysis": {
                "change_type": "normal_fluctuation",
                "change_magnitude": 0.0,
                "change_reason": "默认分析"
            },
            "recommendation": "continue",
            "recommendation_reason": "默认建议：继续检索"
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "improvement_potential" in parsed_result:
                    result["improvement_potential"] = parsed_result["improvement_potential"]
                if "predicted_next_score" in parsed_result:
                    result["predicted_next_score"] = parsed_result["predicted_next_score"]
                if "score_change_analysis" in parsed_result:
                    result["score_change_analysis"] = parsed_result["score_change_analysis"]
                if "recommendation" in parsed_result:
                    result["recommendation"] = parsed_result["recommendation"]
                if "recommendation_reason" in parsed_result:
                    result["recommendation_reason"] = parsed_result["recommendation_reason"]
            except json.JSONDecodeError:
                pass
        
        return ImprovementAnalysisOutput(
            improvement_potential=result["improvement_potential"],
            predicted_next_score=result["predicted_next_score"],
            score_change_analysis=result["score_change_analysis"],
            recommendation=result["recommendation"],
            recommendation_reason=result["recommendation_reason"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ImprovementAnalysisOutput(
            improvement_potential="moderate",
            predicted_next_score=state.current_score,
            score_change_analysis={
                "change_type": "normal_fluctuation",
                "change_magnitude": 0.0,
                "change_reason": "默认分析"
            },
            recommendation="continue",
            recommendation_reason="默认建议：继续检索"
        )
