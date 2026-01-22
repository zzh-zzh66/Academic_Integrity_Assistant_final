import os
import json
import re
from typing import Optional
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient, KnowledgeDocument, ChunkConfig
from utils.file.file import FileOps

from graphs.state import (
    IntentRecognitionInput,
    IntentRecognitionOutput,
    KnowledgeRetrievalInput,
    KnowledgeRetrievalOutput,
    ResponseGenerationInput,
    ResponseGenerationOutput,
    QueryTypeInput,
    QueryTypeOutput,
    DocumentImportInput,
    DocumentImportOutput,
    DocumentImportResponseInput,
    DocumentImportResponseOutput
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
        
        # 解析JSON响应
        result = {
            "intent_type": "咨询类",
            "extracted_keywords": [],
            "behavior_analysis": None
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "intent_type" in parsed_result:
                    result["intent_type"] = parsed_result["intent_type"]
                if "extracted_keywords" in parsed_result:
                    result["extracted_keywords"] = parsed_result["extracted_keywords"]
                if "behavior_analysis" in parsed_result:
                    result["behavior_analysis"] = parsed_result["behavior_analysis"]
            except json.JSONDecodeError:
                pass
        
        return IntentRecognitionOutput(
            intent_type=result["intent_type"],
            extracted_keywords=result["extracted_keywords"],
            behavior_analysis=result["behavior_analysis"]
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


def query_type_node(
    state: QueryTypeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> QueryTypeOutput:
    """
    title: 查询类型判断
    desc: 判断用户是进行查询还是上传文档
    """
    ctx = runtime.context
    
    # 判断逻辑：如果有上传文件，则为upload类型；否则为query类型
    if state.document_file is not None:
        return QueryTypeOutput(query_type="upload")
    else:
        return QueryTypeOutput(query_type="query")


def document_import_node(
    state: DocumentImportInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DocumentImportOutput:
    """
    title: 文档导入
    desc: 将用户上传的文档导入到知识库中
    integrations: 知识库
    """
    ctx = runtime.context
    
    try:
        # 检查文件是否存在
        if state.document_file is None:
            return DocumentImportOutput(
                import_success=False,
                import_message="未找到上传的文件",
                document_count=0
            )
        
        # 读取文件内容
        file_content = FileOps.extract_text(state.document_file)
        
        if not file_content or len(file_content.strip()) == 0:
            return DocumentImportOutput(
                import_success=False,
                import_message="文件内容为空，无法导入",
                document_count=0
            )
        
        # 初始化知识库客户端
        kb_client = KnowledgeClient(ctx=ctx)
        
        # 创建文档对象
        doc = KnowledgeDocument(
            source=0,  # 0 表示 TEXT 类型
            raw_data=file_content
        )
        
        # 配置分块参数
        chunk_config = ChunkConfig(
            separator="\n\n",
            max_tokens=1500,
            remove_extra_spaces=True
        )
        
        # 导入文档到知识库
        response = kb_client.add_documents(
            documents=[doc],
            table_name="coze_doc_knowledge",
            chunk_config=chunk_config
        )
        
        if response.code == 0:
            doc_count = len(response.doc_ids) if response.doc_ids else 1
            return DocumentImportOutput(
                import_success=True,
                import_message=f"文档导入成功！已导入 {doc_count} 个文档片段到知识库。",
                document_count=doc_count
            )
        else:
            return DocumentImportOutput(
                import_success=False,
                import_message=f"文档导入失败：{response.msg}",
                document_count=0
            )
        
    except Exception as e:
        return DocumentImportOutput(
            import_success=False,
            import_message=f"文档导入过程中发生错误：{str(e)}",
            document_count=0
        )


def document_import_response_node(
    state: DocumentImportResponseInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DocumentImportResponseOutput:
    """
    title: 文档导入响应
    desc: 生成文档导入的格式化响应
    """
    ctx = runtime.context
    
    if state.import_success:
        response = f"""文档导入成功！✓

导入详情：
- 导入状态：成功
- 文档片段数量：{state.document_count}
- 消息：{state.import_message}

现在您可以向知识库提问了！例如："学术不端有哪些类型？"
"""
    else:
        response = f"""文档导入失败 ✗

导入详情：
- 导入状态：失败
- 错误信息：{state.import_message}

请检查文件格式是否正确（支持TXT、PDF、DOCX等），或稍后重试。"""
    
    return DocumentImportResponseOutput(
        formatted_response=response
    )


