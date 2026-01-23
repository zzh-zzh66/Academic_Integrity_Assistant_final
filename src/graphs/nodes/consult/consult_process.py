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

def consult_process_node(
    state: ConsultProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultProcessOutput:
    """
    title: 咨询类意图处理
    desc: 分析和优化咨询类问题，提取核心关键词和咨询焦点，使用术语预处理节点的输出增强查询
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
        
        # 解析JSON响应
        result = {
            "refined_query": state.user_query,
            "refined_keywords": state.extracted_keywords if state.extracted_keywords else [],
            "consult_focus": "其他"
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
                if "consult_focus" in parsed_result:
                    result["consult_focus"] = parsed_result["consult_focus"]
            except json.JSONDecodeError:
                pass
        
        return ConsultProcessOutput(
            refined_query=result["refined_query"],
            refined_keywords=result["refined_keywords"],
            consult_focus=result["consult_focus"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return ConsultProcessOutput(
            refined_query=state.user_query,
            refined_keywords=state.extracted_keywords if state.extracted_keywords else [],
            consult_focus="其他"
        )


