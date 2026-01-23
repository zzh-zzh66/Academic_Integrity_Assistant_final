import os
import json
import re
from typing import Optional
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    IntentRecognitionInput,
    IntentRecognitionOutput,
    KnowledgeRetrievalInput,
    KnowledgeRetrievalOutput,
    ResponseGenerationInput,
    ResponseGenerationOutput,
    ConsultProcessInput,
    ConsultProcessOutput,
    JudgeProcessInput,
    JudgeProcessOutput,
    MixedProcessInput,
    MixedProcessOutput
)


def intent_recognition_node(
    state: IntentRecognitionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> IntentRecognitionOutput:
    """
    title: 意图识别
    desc: 识别用户输入的意图类型（咨询类/行为判断类/混合类），并提取关键词和行为分析信息
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
    user_prompt_content = up_tpl.render({"user_query": state.user_query})
    
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
            temperature=llm_config.get("temperature", 0.0),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 1500),
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
        
        # 解析响应（使用直接文本匹配，而不是JSON解析）
        intent_type = "咨询类"  # 默认值
        extracted_keywords = []
        behavior_analysis = None
        
        # 解析意图类型
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 解析意图类型
            if line.startswith("意图类型："):
                type_text = line.replace("意图类型：", "").strip()
                if "行为判断" in type_text or "判断" in type_text:
                    intent_type = "行为判断类"
                elif "混合" in type_text:
                    intent_type = "混合类"
                else:
                    intent_type = "咨询类"
            
            # 解析关键词
            elif line.startswith("关键词："):
                keywords_text = line.replace("关键词：", "").strip()
                if keywords_text:
                    # 按逗号分隔关键词
                    extracted_keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
            
            # 解析行为分析
            elif line.startswith("主体："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["主体"] = line.replace("主体：", "").strip()
            elif line.startswith("动作："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["动作"] = line.replace("动作：", "").strip()
            elif line.startswith("对象："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["对象"] = line.replace("对象：", "").strip()
        
        # 如果没有成功解析，使用关键词匹配进行辅助判断
        if intent_type == "咨询类" and len(extracted_keywords) == 0:
            query_lower = state.user_query.lower()
            if any(word in query_lower for word in ["是否", "违规", "合规", "允许", "可以吗", "违法", "违反"]):
                intent_type = "行为判断类"
        
        return IntentRecognitionOutput(
            intent_type=intent_type,
            extracted_keywords=extracted_keywords,
            behavior_analysis=behavior_analysis
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return IntentRecognitionOutput(
            intent_type="咨询类",
            extracted_keywords=[],
            behavior_analysis=None
        )


def knowledge_retrieval_node(
    state: KnowledgeRetrievalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> KnowledgeRetrievalOutput:
    """
    title: 知识库检索
    desc: 根据意图类型和关键词检索学术道德规范相关内容
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 初始化知识库客户端
        client = KnowledgeClient(ctx=ctx)
        
        # 构建检索查询
        query = state.user_query
        
        # 如果有提取的关键词，也可以加入检索
        if state.extracted_keywords:
            keywords_str = " ".join(state.extracted_keywords)
            query = f"{query} {keywords_str}"
        
        # 执行检索
        response = client.search(
            query=query,
            top_k=5,
            min_score=0.5
        )
        
        # 处理检索结果
        retrieval_results = []
        if response.code == 0 and response.chunks:
            for chunk in response.chunks:
                retrieval_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id
                })
        
        return KnowledgeRetrievalOutput(
            retrieval_results=retrieval_results
        )
        
    except Exception as e:
        # 发生错误时返回空结果
        return KnowledgeRetrievalOutput(
            retrieval_results=[]
        )


def response_generation_node(
    state: ResponseGenerationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ResponseGenerationOutput:
    """
    title: 响应生成
    desc: 根据意图类型和知识库检索结果，按照模板生成结构化响应
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
        "retrieval_results": state.retrieval_results,
        "behavior_analysis": state.behavior_analysis
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
            max_completion_tokens=llm_config.get("max_completion_tokens", 4000),
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
        
        return ResponseGenerationOutput(
            formatted_response=response_text
        )
        
    except Exception as e:
        # 发生错误时返回默认响应
        fallback_response = f"抱歉，处理您的请求时遇到了问题。请稍后重试，或重新描述您的问题。\n\n原始问题：{state.user_query}"
        return ResponseGenerationOutput(
            formatted_response=fallback_response
        )


def consult_process_node(
    state: ConsultProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ConsultProcessOutput:
    """
    title: 咨询类意图处理
    desc: 分析和优化咨询类问题，提取核心关键词和咨询焦点
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


def judge_process_node(
    state: JudgeProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeProcessOutput:
    """
    title: 行为判断类意图处理
    desc: 拆解行为要素，判断是否需要补充信息
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
        "extracted_keywords": state.extracted_keywords,
        "behavior_analysis": state.behavior_analysis
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
            max_completion_tokens=llm_config.get("max_completion_tokens", 1500),
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
            "behavior_subject": state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            "behavior_action": state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            "behavior_object": state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            "needs_clarification": False,
            "clarification_questions": []
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
                if "behavior_subject" in parsed_result:
                    result["behavior_subject"] = parsed_result["behavior_subject"]
                if "behavior_action" in parsed_result:
                    result["behavior_action"] = parsed_result["behavior_action"]
                if "behavior_object" in parsed_result:
                    result["behavior_object"] = parsed_result["behavior_object"]
                if "needs_clarification" in parsed_result:
                    result["needs_clarification"] = parsed_result["needs_clarification"]
                if "clarification_questions" in parsed_result:
                    result["clarification_questions"] = parsed_result["clarification_questions"]
            except json.JSONDecodeError:
                pass
        
        return JudgeProcessOutput(
            refined_query=result["refined_query"],
            refined_keywords=result["refined_keywords"],
            behavior_subject=result["behavior_subject"],
            behavior_action=result["behavior_action"],
            behavior_object=result["behavior_object"],
            needs_clarification=result["needs_clarification"],
            clarification_questions=result["clarification_questions"]
        )
        
    except Exception as e:
        # 发生错误时返回默认值
        return JudgeProcessOutput(
            refined_query=state.user_query,
            refined_keywords=state.extracted_keywords if state.extracted_keywords else [],
            behavior_subject=state.behavior_analysis.get("主体", "") if state.behavior_analysis else "",
            behavior_action=state.behavior_analysis.get("动作", "") if state.behavior_analysis else "",
            behavior_object=state.behavior_analysis.get("对象", "") if state.behavior_analysis else "",
            needs_clarification=False,
            clarification_questions=[]
        )


def mixed_process_node(
    state: MixedProcessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MixedProcessOutput:
    """
    title: 混合类意图处理
    desc: 拆分为咨询部分和行为判断部分，分别提取关键信息
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
        "extracted_keywords": state.extracted_keywords,
        "behavior_analysis": state.behavior_analysis
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
