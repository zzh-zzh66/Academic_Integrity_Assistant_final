# 开发详细指南

本文档提供学术诚信助手工作流的开发指南，包括代码结构、节点开发、配置管理和测试方法。

## 目录

- [代码结构](#代码结构)
- [节点开发](#节点开发)
- [状态定义](#状态定义)
- [图编排](#图编排)
- [如何添加新节点](#如何添加新节点)
- [如何修改检索策略](#如何修改检索策略)
- [测试方法](#测试方法)
- [调试技巧](#调试技巧)

---

## 代码结构

### 目录结构

```
src/
├── agents/                # Agent代码（预留）
├── graphs/                # 工作流编排
│   ├── nodes/             # 节点实现
│   │   ├── common.py      # 通用节点
│   │   ├── consult.py     # 咨询类节点
│   │   ├── consult_loop.py # 咨询类循环检索节点（调用子图）
│   │   ├── judge.py       # 行为判断类节点
│   │   └── mixed.py       # 混合类节点
│   ├── graph.py           # 主图编排
│   ├── loop_graph.py      # 循环检索子图
│   ├── state.py           # 状态定义
│   └── loop_config_loader.py # 配置加载器
├── storage/               # 存储层
├── tools/                 # 工具定义
└── utils/                 # 工具类
```

### 模块说明

#### graphs/

工作流编排的核心模块：

- **state.py**：定义全局状态、图输入输出、节点输入输出
- **graph.py**：主图的编排和编译
- **loop_graph.py**：循环检索子图的编排和编译
- **loop_config_loader.py**：加载循环检索配置

#### graphs/nodes/

节点实现模块，按功能分类：

- **common.py**：通用节点（意图识别、术语预处理、响应生成）
- **consult.py**：咨询类分支节点（查询优化）
- **consult_loop.py**：咨询类循环检索节点（调用子图）
- **judge.py**：行为判断类节点
- **mixed.py**：混合类节点

---

## 节点开发

### 节点函数签名

所有节点必须遵循以下签名格式：

```python
from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableConfig
from coze_coding_utils.runtime_ctx.context import Context

def node_name(
    state: NodeInput,           # 节点专用输入
    config: RunnableConfig,     # 运行时配置
    runtime: Runtime[Context]   # 运行时上下文
) -> NodeOutput:                # 节点专用输出
    """
    title: 节点标题
    desc: 节点描述
    integrations: 使用的集成服务
    """
    ctx = runtime.context
    
    # 业务逻辑
    
    return NodeOutput(...)
```

### 节点类型

#### 1. 普通节点

不涉及大模型调用的节点：

```python
def preprocess_node(
    state: PreprocessInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> PreprocessOutput:
    """
    title: 预处理节点
    desc: 对用户查询进行预处理
    integrations: 
    """
    ctx = runtime.context
    
    # 业务逻辑
    processed_query = state.user_query.strip().lower()
    
    return PreprocessOutput(
        processed_query=processed_query
    )
```

#### 2. Agent节点（大模型节点）

调用大语言模型的节点：

```python
import os
import json
from jinja2 import Template

def llm_node(
    state: LLMNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> LLMNodeOutput:
    """
    title: 大模型节点
    desc: 调用大语言模型进行处理
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config['metadata']['llm_cfg']
    )
    with open(cfg_file, 'r') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    
    # 渲染用户提示词
    up_tpl = Template(up)
    user_prompt = up_tpl.render({
        "user_query": state.user_query
    })
    
    # 调用大模型
    # llm = get_llm(llm_config)
    # response = llm.invoke([
    #     {"role": "system", "content": sp},
    #     {"role": "user", "content": user_prompt}
    # ])
    
    # 解析结果
    # result = parse_response(response.content)
    
    return LLMNodeOutput(
        result="result"
    )
```

#### 3. 循环节点

调用子图的节点：

```python
from graphs.loop_graph import subgraph

def loop_node(
    state: LoopNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> LoopNodeOutput:
    """
    title: 循环节点
    desc: 调用循环检索子图
    integrations: 知识库
    """
    ctx = runtime.context
    
    # 调用子图
    result = subgraph.invoke({
        "user_query": state.user_query,
        "optimized_query": state.optimized_query,
        "retrieval_strategy": state.retrieval_strategy
    })
    
    return LoopNodeOutput(
        retrieval_results=result.get("retrieval_results", [])
    )
```

### 节点文档字符串

每个节点必须包含标准的文档字符串：

```python
"""
title: 节点标题
desc: 节点功能描述，尽量通俗易懂
integrations: 使用的集成服务名（如：大语言模型、知识库、邮件）
"""
```

**注意事项**：
- `title`：简洁明了的节点名称
- `desc`：详细描述节点的功能、输入输出、处理逻辑
- `integrations`：仅列出使用的集成服务名，不包含外部三方服务（如 OpenCV、pip 等）

---

## 状态定义

### 状态类规范

所有状态类必须继承 `pydantic.BaseModel`：

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class NodeInput(BaseModel):
    """节点输入"""
    user_query: str = Field(..., description="用户查询")
    refined_query: str = Field(..., description="优化后的查询")
    
class NodeOutput(BaseModel):
    """节点输出"""
    result: str = Field(..., description="处理结果")
    confidence: float = Field(default=0.0, description="置信度")
```

### 字段规范

1. **必填字段**：使用 `...` 标记
```python
user_query: str = Field(..., description="用户查询")
```

2. **可选字段**：使用 `Optional` 类型并提供默认值
```python
optional_field: Optional[str] = Field(default=None, description="可选字段")
```

3. **列表字段**：必须指定元素类型
```python
results: List[str] = Field(default=[], description="结果列表")
```

4. **字典字段**：建议使用 `dict` 类型
```python
metadata: dict = Field(default={}, description="元数据")
```

5. **复杂类型**：支持嵌套的 BaseModel
```python
class ResultItem(BaseModel):
    content: str = Field(..., description="内容")
    score: float = Field(..., description="分数")

class NodeOutput(BaseModel):
    items: List[ResultItem] = Field(default=[], description="结果项列表")
```

### 全局状态

全局状态包含工作流的所有共享数据：

```python
class GlobalState(BaseModel):
    """全局状态定义"""
    user_query: str = Field(..., description="用户原始查询")
    intent_type: str = Field(default="", description="意图类型")
    query_complexity: str = Field(default="", description="查询复杂度")
    refined_query: str = Field(default="", description="优化后的查询")
    retrieval_results: List[dict] = Field(default=[], description="检索结果")
    formatted_response: str = Field(default="", description="格式化响应")
```

### 图输入输出

```python
class GraphInput(BaseModel):
    """工作流的输入"""
    user_query: str = Field(..., description="用户查询")

class GraphOutput(BaseModel):
    """工作流的输出"""
    formatted_response: str = Field(..., description="格式化响应")
```

---

## 图编排

### 主图编排

主图必须是有向无环图（DAG）：

```python
from langgraph.graph import StateGraph, END

# 创建状态图
builder = StateGraph(
    GlobalState,
    input_schema=GraphInput,
    output_schema=GraphOutput
)

# 添加节点
builder.add_node("node1", node1)
builder.add_node("node2", node2)
builder.add_node("node3", node3)

# 设置入口点
builder.set_entry_point("node1")

# 添加边
builder.add_edge("node1", "node2")
builder.add_edge("node2", "node3")
builder.add_edge("node3", END)

# 编译图
main_graph = builder.compile()
```

### 条件分支

使用 `add_conditional_edges` 添加条件分支：

```python
def should_route(state: ShouldRouteInput) -> str:
    """条件判断函数"""
    if state.intent_type == "咨询类":
        return "咨询类分支"
    elif state.intent_type == "行为判断类":
        return "行为判断类分支"
    else:
        return "混合类分支"

# 添加条件分支
builder.add_conditional_edges(
    source="intent_recognition",  # 源节点名（字符串）
    path=should_route,            # 路径决策函数（函数对象）
    path_map={
        "咨询类分支": "consult_process",  # 目标节点名（字符串）
        "行为判断类分支": "judge_process",
        "混合类分支": "mixed_process"
    }
)
```

### 并行处理

使用列表参数实现并行：

```python
# 并行分支
builder.add_edge("node1", "node2")
builder.add_edge("node1", "node3")

# 汇聚节点（等待所有并行分支完成）
builder.add_edge(["node2", "node3"], "merge_node")
```

### 循环实现

循环必须实现为子图，在主图中调用：

```python
# 添加循环节点（调用子图）
builder.add_node(
    "retrieval_loop",
    retrieval_loop_node,
    metadata={"type": "looparray"}  # 标记为循环节点
)

# 添加边
builder.add_edge("query_optimize", "retrieval_loop")
builder.add_edge("retrieval_loop", "response_generation")
```

### 子图编排

子图的编排方式与主图相同：

```python
from graphs.state import LoopState

# 创建子图
loop_builder = StateGraph(
    LoopState,
    input_schema=LoopInput,
    output_schema=LoopOutput
)

# 添加节点
loop_builder.add_node("retrieval", retrieval_internal)
loop_builder.add_node("expand", expand_internal)
loop_builder.add_node("rerank", rerank_internal)

# 添加边
loop_builder.set_entry_point("retrieval")
loop_builder.add_edge("retrieval", "expand")
loop_builder.add_edge("expand", "rerank")

# 编译子图
subgraph = loop_builder.compile()
```

---

## 如何添加新节点

### 步骤1：定义状态

在 `src/graphs/state.py` 中定义节点的输入输出：

```python
class NewNodeInput(BaseModel):
    """新节点输入"""
    user_query: str = Field(..., description="用户查询")
    refined_query: str = Field(..., description="优化后的查询")

class NewNodeOutput(BaseModel):
    """新节点输出"""
    result: str = Field(..., description="处理结果")
    confidence: float = Field(default=0.0, description="置信度")
```

### 步骤2：实现节点

在 `src/graphs/nodes/xxx.py` 中实现节点：

```python
import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import NewNodeInput, NewNodeOutput

def new_node(
    state: NewNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> NewNodeOutput:
    """
    title: 新节点
    desc: 节点功能描述
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config['metadata']['llm_cfg']
    )
    with open(cfg_file, 'r') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    
    # 渲染用户提示词
    up_tpl = Template(up)
    user_prompt = up_tpl.render({
        "user_query": state.user_query,
        "refined_query": state.refined_query
    })
    
    # 调用大模型
    # llm = get_llm(llm_config)
    # response = llm.invoke([
    #     {"role": "system", "content": sp},
    #     {"role": "user", "content": user_prompt}
    # ])
    
    # 解析结果
    result = "处理结果"
    confidence = 0.85
    
    return NewNodeOutput(
        result=result,
        confidence=confidence
    )
```

### 步骤3：创建配置文件

在 `config/nodes/` 目录下创建配置文件：

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.3,
    "top_p": 0.7,
    "max_completion_tokens": 2000,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "系统提示词",
  "up": "用户提示词：{{user_query}}"
}
```

### 步骤4：添加到主图

在 `src/graphs/graph.py` 中添加节点：

```python
from graphs.nodes.xxx import new_node

# 添加节点
builder.add_node("new_node", new_node,
                metadata={"type": "agent",
                         "llm_cfg": "config/nodes/new_node_cfg.json"})

# 添加边
builder.add_edge("previous_node", "new_node")
builder.add_edge("new_node", "next_node")
```

### 步骤5：导出节点

在 `src/graphs/nodes/__init__.py` 中导出节点：

```python
from graphs.nodes.xxx import new_node

__all__ = ["new_node"]
```

---

## 如何修改检索策略

### 修改循环配置

编辑 `config/loop/consult_loop_config.json`：

```json
{
  "basic_params": {
    "max_rounds": 2,  // 修改为2轮
    "target_score": 0.75,
    "min_score_threshold": 0.6
  },
  "retrieval_params": {
    "first_round": {
      "top_k": 12,
      "min_score": 0.35
    },
    "second_round": {
      "top_k": 8,
      "min_score": 0.65
    }
  }
}
```

### 修改查询优化节点

编辑 `config/nodes/consult/consult_query_optimize_cfg.json`：

```json
{
  "sp": "你是一个学术查询优化专家。\n\n根据查询复杂度，生成相应的检索策略：\n- Simple：top_k=10, min_score=0.4, max_rounds=1\n- Standard：top_k=15, min_score=0.3, max_rounds=2\n- Complex：top_k=20, min_score=0.25, max_rounds=3",
  "up": "请优化以下查询：{{user_query}}"
}
```

### 测试验证

```python
from graphs.graph import main_graph

# 测试简单查询
result = main_graph.invoke({
    "user_query": "什么是抄袭？"
})
print(result["formatted_response"])

# 测试复杂查询
result = main_graph.invoke({
    "user_query": "请详细说明自我抄袭的定义"
})
print(result["formatted_response"])
```

---

## 测试方法

### 单元测试

为每个节点编写单元测试：

```python
import pytest
from graphs.nodes.common import intent_recognition_node
from graphs.state import IntentInput, IntentOutput

def test_intent_recognition():
    """测试意图识别节点"""
    state = IntentInput(
        user_query="什么是学术不端行为？"
    )
    
    output = intent_recognition_node(state, {}, None)
    
    assert isinstance(output, IntentOutput)
    assert output.intent_type in ["咨询类", "行为判断类", "混合类"]
```

### 集成测试

测试整个工作流：

```python
from graphs.graph import main_graph

def test_consult_query():
    """测试咨询类查询"""
    result = main_graph.invoke({
        "user_query": "什么是学术不端行为？"
    })
    
    assert "formatted_response" in result
    assert len(result["formatted_response"]) > 0

def test_judge_query():
    """测试行为判断类查询"""
    result = main_graph.invoke({
        "user_query": "我能否在论文中重复使用自己已发表的内容？"
    })
    
    assert "formatted_response" in result
    assert "合规" in result["formatted_response"] or "不合规" in result["formatted_response"]
```

### 运行测试

```bash
# 运行所有测试
pytest src/tests/

# 运行特定测试文件
pytest src/tests/test_nodes.py

# 运行特定测试函数
pytest src/tests/test_nodes.py::test_intent_recognition
```

---

## 调试技巧

### 查看中间结果

在节点中添加日志：

```python
import logging

logger = logging.getLogger(__name__)

def some_node(state: SomeInput, config: RunnableConfig, runtime: Runtime[Context]) -> SomeOutput:
    """
    title: 某个节点
    desc: 节点描述
    integrations: 
    """
    ctx = runtime.context
    
    logger.info(f"输入: {state}")
    logger.info(f"配置: {config}")
    
    # 业务逻辑
    
    logger.info(f"输出: {output}")
    return output
```

### 查看日志

```bash
# 查看最新日志
tail -n 20 /app/work/logs/bypass/app.log

# 搜索错误
grep -n "Error\|Exception" /app/work/logs/bypass/app.log | tail -n 20
```

### 使用断言检查

```python
def some_node(state: SomeInput, config: RunnableConfig, runtime: Runtime[Context]) -> SomeOutput:
    """
    title: 某个节点
    desc: 节点描述
    integrations: 
    """
    ctx = runtime.context
    
    # 断言检查
    assert state.user_query is not None, "user_query 不能为空"
    assert len(state.user_query) > 0, "user_query 不能为空字符串"
    
    # 业务逻辑
    
    return output
```

### 调试子图

```python
from graphs.loop_graph import subgraph

# 直接调用子图进行调试
result = subgraph.invoke({
    "user_query": "测试查询",
    "optimized_query": "优化后的查询",
    "retrieval_strategy": {
        "top_k": 15,
        "min_score": 0.3
    }
})

print(result)
```

---

## 总结

开发学术诚信助手工作流需要遵循以下原则：

1. **单一职责原则**：每个节点只负责一个功能
2. **高内聚低耦合**：节点之间通过状态对象传递数据
3. **配置驱动**：所有提示词和参数通过 JSON 配置文件管理
4. **类型安全**：使用 Pydantic 确保类型安全
5. **模块化设计**：按功能组织节点和配置文件

相关文档：
- [工作流说明](./workflow.md)
- [配置说明](./configuration.md)
- [查询示例](./examples.md)
- [技术架构](./architecture.md)
