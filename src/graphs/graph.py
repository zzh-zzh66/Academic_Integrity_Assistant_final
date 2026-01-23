from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput
)
from graphs.nodes import (
    intent_recognition_node,
    term_preprocessing_node,
    consult_process_node,
    judge_process_node,
    mixed_process_node,
    judge_retrieval_node,
    mixed_retrieval_node,
    judge_context_expand_node,
    judge_rerank_node,
    mixed_context_expand_node,
    mixed_rerank_node,
    response_generation_node
)
from graphs.nodes.consult import consult_retrieval_loop_node


def route_intent_type(state: GlobalState) -> str:
    """
    title: 意图类型路由
    desc: 根据意图类型路由到不同的处理节点
    """
    intent_type = state.intent_type
    if intent_type == "咨询类":
        return "咨询类处理"
    elif intent_type == "行为判断类":
        return "行为判断类处理"
    elif intent_type == "混合类":
        return "混合类处理"
    else:
        # 默认路由到咨询类处理
        return "咨询类处理"


# 创建状态图，指定工作流的入参和出参
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("intent_recognition", intent_recognition_node,
                metadata={"type": "agent", "llm_cfg": "config/intent_recognition_cfg.json"})
builder.add_node("term_preprocessing", term_preprocessing_node)

# 咨询类意图处理节点
builder.add_node("consult_process", consult_process_node,
                metadata={"type": "agent", "llm_cfg": "config/consult_process_cfg.json"})

# 咨询类循环检索节点（通过调用子图实现，封装了consult_retrieval、consult_context_expand、consult_rerank三个节点）
builder.add_node("consult_retrieval_loop", consult_retrieval_loop_node,
                metadata={"type": "looparray"})

builder.add_node("judge_process", judge_process_node,
                metadata={"type": "agent", "llm_cfg": "config/judge_process_cfg.json"})
builder.add_node("mixed_process", mixed_process_node,
                metadata={"type": "agent", "llm_cfg": "config/mixed_process_cfg.json"})

# 行为判断类和混合类的知识库检索节点（暂时保留，后续优化）
builder.add_node("judge_retrieval", judge_retrieval_node)
builder.add_node("mixed_retrieval", mixed_retrieval_node)

# 行为判断类和混合类的上下文扩展节点（暂时保留）
builder.add_node("judge_context_expand", judge_context_expand_node)
builder.add_node("mixed_context_expand", mixed_context_expand_node)

# 行为判断类和混合类的重排序节点（暂时保留）
builder.add_node("judge_rerank", judge_rerank_node,
                metadata={"type": "agent", "llm_cfg": "config/judge_rerank_cfg.json"})
builder.add_node("mixed_rerank", mixed_rerank_node,
                metadata={"type": "agent", "llm_cfg": "config/mixed_rerank_cfg.json"})

builder.add_node("response_generation", response_generation_node,
                metadata={"type": "agent", "llm_cfg": "config/response_generation_cfg.json"})

# 设置入口点
builder.set_entry_point("intent_recognition")

# 添加边：意图识别 → 术语预处理
builder.add_edge("intent_recognition", "term_preprocessing")

# 添加条件分支：根据意图类型路由到不同的处理节点
builder.add_conditional_edges(
    source="term_preprocessing",
    path=route_intent_type,
    path_map={
        "咨询类处理": "consult_process",
        "行为判断类处理": "judge_process",
        "混合类处理": "mixed_process"
    }
)

# 三个处理分支分别路由到对应的检索节点
builder.add_edge("consult_process", "consult_retrieval_loop")  # 咨询类使用循环检索
builder.add_edge("judge_process", "judge_retrieval")
builder.add_edge("mixed_process", "mixed_retrieval")

# 行为判断类和混合类的检索节点 → 扩展节点
builder.add_edge("judge_retrieval", "judge_context_expand")
builder.add_edge("mixed_retrieval", "mixed_context_expand")

# 咨询类、行为判断类、混合类的检索结果都汇聚到响应生成
builder.add_edge("consult_retrieval_loop", "response_generation")
builder.add_edge("judge_rerank", "response_generation")
builder.add_edge("mixed_rerank", "response_generation")

# 响应生成 → END
builder.add_edge("response_generation", END)

# 编译图
main_graph = builder.compile()
