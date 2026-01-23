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

def rerank_node(
    state: RerankInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> RerankOutput:
    """
    title: 重排序
    desc: 对检索结果进行多维度评分和排序
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
        "expanded_results": state.expanded_results
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
            "ranked_results": state.expanded_results,
            "weighted_score": 0.7,
            "top_score": 0.7,
            "top_3_avg": 0.7,
            "average_confidence": 0.7
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "ranked_results" in parsed_result:
                    result["ranked_results"] = parsed_result["ranked_results"]
                if "weighted_score" in parsed_result:
                    result["weighted_score"] = parsed_result["weighted_score"]
                if "top_score" in parsed_result:
                    result["top_score"] = parsed_result["top_score"]
                if "top_3_avg" in parsed_result:
                    result["top_3_avg"] = parsed_result["top_3_avg"]
                if "average_confidence" in parsed_result:
                    result["average_confidence"] = parsed_result["average_confidence"]
            except json.JSONDecodeError:
                pass
        
        return RerankOutput(
            ranked_results=result["ranked_results"],
            weighted_score=result["weighted_score"],
            top_score=result["top_score"],
            top_3_avg=result["top_3_avg"],
            average_confidence=result["average_confidence"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return RerankOutput(
            ranked_results=state.expanded_results,
            weighted_score=0.7,
            top_score=0.7,
            top_3_avg=0.7,
            average_confidence=0.7
        )


# ==================== 上下文提取节点 ====================

