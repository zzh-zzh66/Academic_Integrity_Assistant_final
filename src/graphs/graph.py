from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput
)
from graphs.node import (
    intent_recognition_node,
    knowledge_retrieval_node,
    response_generation_node,
    query_type_node,
    document_import_node,
    document_import_response_node
)


def route_query_type(state: GlobalState) -> str:
    """
    title: 路由判断
    desc: 根据查询类型路由到不同的处理流程
    """
    if state.query_type == "upload":
        return "文档导入"
    else:
        return "学术诚信查询"


# 创建状态图，指定工作流的入参和出参
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("query_type", query_type_node)
builder.add_node("document_import", document_import_node)
builder.add_node("document_import_response", document_import_response_node)
builder.add_node("intent_recognition", intent_recognition_node, 
                metadata={"type": "agent", "llm_cfg": "config/intent_recognition_cfg.json"})
builder.add_node("knowledge_retrieval", knowledge_retrieval_node)
builder.add_node("response_generation", response_generation_node,
                metadata={"type": "agent", "llm_cfg": "config/response_generation_cfg.json"})

# 设置入口点
builder.set_entry_point("query_type")

# 添加条件分支
builder.add_conditional_edges(
    source="query_type",
    path=route_query_type,
    path_map={
        "文档导入": "document_import",
        "学术诚信查询": "intent_recognition"
    }
)

# 添加边（查询流程）
builder.add_edge("intent_recognition", "knowledge_retrieval")
builder.add_edge("knowledge_retrieval", "response_generation")

# 查询流程最后结束
builder.add_edge("response_generation", END)

# 文档导入流程
builder.add_edge("document_import", "document_import_response")
builder.add_edge("document_import_response", END)

# 编译图
main_graph = builder.compile()
