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

