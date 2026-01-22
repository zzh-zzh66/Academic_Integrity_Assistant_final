from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput
)
from graphs.node import (
    intent_recognition_node,
    knowledge_retrieval_node,
    response_generation_node
)

# 创建状态图，指定工作流的入参和出参
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("intent_recognition", intent_recognition_node, 
                metadata={"type": "agent", "llm_cfg": "config/intent_recognition_cfg.json"})
builder.add_node("knowledge_retrieval", knowledge_retrieval_node)
builder.add_node("response_generation", response_generation_node,
                metadata={"type": "agent", "llm_cfg": "config/response_generation_cfg.json"})

# 设置入口点
builder.set_entry_point("intent_recognition")

# 添加边（线性流程）
builder.add_edge("intent_recognition", "knowledge_retrieval")
builder.add_edge("knowledge_retrieval", "response_generation")
builder.add_edge("response_generation", END)

# 编译图
main_graph = builder.compile()
