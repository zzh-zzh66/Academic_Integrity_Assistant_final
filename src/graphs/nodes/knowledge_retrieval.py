from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import KnowledgeClient

from graphs.state import (
    KnowledgeRetrievalInput,
    KnowledgeRetrievalOutput
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

        # 执行检索（优化：增加 top_k 获取更多相关片段）
        response = client.search(
            query=query,
            top_k=10,
            min_score=0.6
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
