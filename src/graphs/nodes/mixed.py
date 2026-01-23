import os
import json
import re
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
from graphs.nodes.common import extract_file_name_from_content, expand_content_around_chunk


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


def mixed_retrieval_node(
    state: MixedRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedRetrievalOutput:
    """
    title: 混合类知识库检索
    desc: 根据混合类意图检索，分两路检索后合并（咨询路+判断路）
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        all_results = []
        
        # 第一路：咨询类检索
        consult_query = state.consult_query if state.consult_query else state.user_query
        if state.consult_keywords:
            consult_query = f"{consult_query} {' '.join(state.consult_keywords)}"
        if state.consult_focus:
            consult_query = f"{consult_query} {state.consult_focus}"
        consult_query = f"{consult_query} 定义 要求 规范"
        
        consult_response = client.search(
            query=consult_query,
            top_k=15,
            min_score=0.3
        )
        
        if consult_response.code == 0 and consult_response.chunks:
            for chunk in consult_response.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                all_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name,
                    "source": "consult"
                })
        
        # 第二路：判断类检索
        judge_query = state.judge_query if state.judge_query else state.user_query
        
        # 添加行为分析信息
        if state.behavior_subject or state.behavior_action or state.behavior_object:
            behavior_parts = []
            if state.behavior_subject:
                behavior_parts.append(f"主体:{state.behavior_subject}")
            if state.behavior_action:
                behavior_parts.append(f"动作:{state.behavior_action}")
            if state.behavior_object:
                behavior_parts.append(f"对象:{state.behavior_object}")
            judge_query = f"{judge_query} {' '.join(behavior_parts)}"
        
        if state.judge_keywords:
            judge_query = f"{judge_query} {' '.join(state.judge_keywords)}"
        
        judge_response = client.search(
            query=judge_query,
            top_k=15,
            min_score=0.5
        )
        
        if judge_response.code == 0 and judge_response.chunks:
            for chunk in judge_response.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                all_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name,
                    "source": "judge"
                })
        
        # 合并去重（按doc_id去重），保留最高分
        unique_results = {}
        for result in all_results:
            doc_id = result["doc_id"]
            if doc_id not in unique_results:
                unique_results[doc_id] = result
            else:
                # 保留分数更高的结果
                if result["score"] > unique_results[doc_id]["score"]:
                    unique_results[doc_id] = result
        
        # 按分数排序，取top 6
        sorted_results = sorted(unique_results.values(), key=lambda x: x["score"], reverse=True)[:6]
        
        return MixedRetrievalOutput(
            retrieval_results=sorted_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return MixedRetrievalOutput(
            retrieval_results=[]
        )


def mixed_context_expand_node(
    state: MixedContextExpandInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedContextExpandOutput:
    """
    title: 混合类上下文扩展
    desc: 扩展混合类检索结果，咨询路扩展到段落（500-800字），判断路扩展到条款（300-500字）
    """
    ctx = runtime.context
    
    try:
        expanded_results = []
        
        for result in state.retrieval_results:
            original_content = result.get("content", "")
            source = result.get("source", "consult")
            
            # 根据来源类型决定扩展长度
            if source == "consult":
                # 咨询路扩展到 500-800 字
                expanded_content = expand_content_around_chunk(original_content, target_length=650)
            else:
                # 判断路扩展到 300-500 字
                expanded_content = expand_content_around_chunk(original_content, target_length=400)
            
            expanded_results.append({
                "content": expanded_content,
                "score": result.get("score", 0.0),
                "doc_id": result.get("doc_id", ""),
                "file_name": result.get("file_name", ""),
                "source": source
            })
        
        return MixedContextExpandOutput(
            expanded_results=expanded_results
        )
        
    except Exception as e:
        # 发生错误时返回原始结果
        return MixedContextExpandOutput(
            expanded_results=state.retrieval_results
        )


def mixed_rerank_node(
    state: MixedRerankInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedRerankOutput:
    """
    title: 混合类重排序
    desc: 对混合类扩展结果进行多维度评分和排序，筛选出最相关的 5 条结果
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
            temperature=llm_config.get("temperature", 0.1),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 2500),
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
            else:
                # 无法解析 JSON，返回原始结果
                ranked_results = state.expanded_results[:5]
        except Exception as e:
            # 解析失败，返回原始结果
            ranked_results = state.expanded_results[:5]
        
        return MixedRerankOutput(
            retrieval_results=ranked_results
        )
        
    except Exception as e:
        # 发生错误时返回前 5 条原始结果
        return MixedRerankOutput(
            retrieval_results=state.expanded_results[:5]
        )
