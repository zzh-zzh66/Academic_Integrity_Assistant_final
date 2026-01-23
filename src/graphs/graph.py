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
    response_generation_node,
    complexity_node,
    consult_query_optimize_node,
    judge_query_optimize_node,
    judge_retrieval_enhanced_node,
    judge_context_expand_enhanced_node,
    judge_decision_node
)
from graphs.nodes.consult_loop import consult_retrieval_loop_node


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
# 第一步：查询复杂度判断（在意图识别之前）
builder.add_node("complexity", complexity_node,
                metadata={"type": "agent", "llm_cfg": "config/nodes/complexity_cfg.json"})

# 第二步：意图识别
builder.add_node("intent_recognition", intent_recognition_node,
                metadata={"type": "agent", "llm_cfg": "config/intent_recognition_cfg.json"})

# 第三步：术语预处理
builder.add_node("term_preprocessing", term_preprocessing_node)

# 意图处理节点
builder.add_node("consult_process", consult_process_node,
                metadata={"type": "agent", "llm_cfg": "config/consult_process_cfg.json"})
builder.add_node("judge_process", judge_process_node,
                metadata={"type": "agent", "llm_cfg": "config/judge_process_cfg.json"})
builder.add_node("mixed_process", mixed_process_node,
                metadata={"type": "agent", "llm_cfg": "config/mixed_process_cfg.json"})

# 咨询查询优化节点（在consult_process和consult_retrieval_loop之间）
builder.add_node("consult_query_optimize", consult_query_optimize_node,
                metadata={"type": "agent", "llm_cfg": "config/nodes/consult/consult_query_optimize_cfg.json"})

# 咨询类循环检索节点（通过调用子图实现）
builder.add_node("consult_retrieval_loop", consult_retrieval_loop_node,
                metadata={"type": "looparray"})

# 🆕 行为判断类增强节点
builder.add_node("judge_query_optimize", judge_query_optimize_node,
                metadata={"type": "agent", "llm_cfg": "config/nodes/judge/judge_query_optimize_cfg.json"})
builder.add_node("judge_retrieval_enhanced", judge_retrieval_enhanced_node)
builder.add_node("judge_context_expand_enhanced", judge_context_expand_enhanced_node)
builder.add_node("judge_decision", judge_decision_node,
                metadata={"type": "agent", "llm_cfg": "config/nodes/judge/judge_decision_cfg.json"})

# 响应生成节点
builder.add_node("response_generation", response_generation_node,
                metadata={"type": "agent", "llm_cfg": "config/response_generation_cfg.json"})

# 设置入口点
builder.set_entry_point("complexity")

# 添加边：查询复杂度判断 → 意图识别 → 术语预处理
builder.add_edge("complexity", "intent_recognition")
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

# 三个处理分支分别路由到对应的处理节点
builder.add_edge("consult_process", "consult_query_optimize")  # 咨询类：先优化查询，再循环检索
builder.add_edge("consult_query_optimize", "consult_retrieval_loop")  # 优化后进入循环检索

# 🆕 行为判断类分支：增强版本
builder.add_edge("judge_process", "judge_query_optimize")  # 查询优化
builder.add_edge("judge_query_optimize", "judge_retrieval_enhanced")  # 增强检索
builder.add_edge("judge_retrieval_enhanced", "judge_context_expand_enhanced")  # 拓宽上下文
builder.add_edge("judge_context_expand_enhanced", "judge_decision")  # 违规判断

# 🚫 混合类分支：暂时跳过，直接到响应生成（待后续实现并行架构）
builder.add_edge("mixed_process", "response_generation")

# 咨询类、行为判断类的检索结果都汇聚到响应生成
builder.add_edge("consult_retrieval_loop", "response_generation")
builder.add_edge("judge_decision", "response_generation")  # 行为判断类：判断结果 → 响应生成

# 响应生成 → END
builder.add_edge("response_generation", END)

# 编译图
main_graph = builder.compile()
