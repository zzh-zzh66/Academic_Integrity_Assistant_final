# 学术诚信助手工作流 (Academic Integrity Assistant workflow)

> 基于 LangGraph 的智能学术诚信问答系统，支持三类意图识别、自适应检索策略和多轮循环优化

---

## 📖 项目简介

学术诚信助手是一个基于 LangGraph 框架开发的工作流问答系统，专门用于回答学术道德、学术规范、学术不端行为等相关问题。系统通过意图识别、术语预处理、复杂度判断、动态检索和循环优化等技术，为用户提供准确、可信、可验证的答案。

### 核心价值

- **智能意图识别**：自动识别用户问题的类型（咨询类/行为判断类/混合类）
- **自适应检索**：根据查询复杂度动态调整检索策略
- **循环优化**：通过多轮检索和 LLM 增强持续提升答案质量
- **可信度保障**：每个观点标注来源，提供可验证方式

---

## ✨ 功能特性

### 意图识别与分类

- **咨询类**：询问定义、规范、要求等知识性问题
- **行为判断类**：判断特定行为是否合规
- **混合类**：既包含咨询也包含行为判断

### 查询复杂度判断

- **Simple（简单）**：单一概念、明确的问题
- **Standard（标准）**：中等复杂度，需要综合分析
- **Complex（复杂）**：多概念关联、需要深入分析

### 动态检索策略

根据查询复杂度和优化节点输出的检索策略，动态调整：
- 每轮的检索数量（top_k）
- 最小相关性阈值（min_score）
- 最大检索轮次（max_rounds）
- 提前退出条件

### 术语预处理与语义增强

- **术语标准化**：识别非标准术语并映射到标准术语
- **术语扩展**：基于领域知识扩展相关术语
- **要素提取**：提取行为要素、对象要素
- **语义增强**：构建语义增强查询

### 循环检索与智能优化

- **多轮检索**：最多3轮循环，逐步提升检索质量
- **内容扩展**：扩展检索结果到完整段落（500-800字）
- **多维度重排序**：相关性、权威性、完整性、时效性加权评分
- **上下文提取**：提取关键概念、关系图谱、缺失方面、总结
- **改善分析**：LLM 预测下一轮的改善潜力，指导循环决策
- **智能退出**：基于分数阈值、轮次限制、收敛检测决定退出时机

### 自然对话风格响应

- 去除系统内部信息（意图类型、咨询问题标题等）
- 采用专业顾问的对话语气
- 每个观点标注信息来源
- 提供可验证的参考文献或来源

---

## 🎯 项目亮点

### 1. 基于复杂度的自适应检索

首次在学术问答系统中引入查询复杂度判断，根据问题复杂度动态调整检索策略，避免简单问题过度检索，复杂问题检索不足。

### 2. LLM 增强的循环优化

不仅依赖传统的检索分数优化，还引入 LLM 进行改善分析，预测下一轮的检索潜力，实现智能化循环决策。

### 3. 多维度评分体系

重排序采用加权评分模型（相关性40%、权威性30%、完整性20%、时效性10%），确保返回结果的质量和可信度。

### 4. 模块化架构设计

- 单一职责原则：每个节点只负责一个功能
- 高内聚低耦合：节点之间通过状态对象传递数据
- 配置驱动：所有提示词和参数通过 JSON 配置文件管理

### 5. 子图化循环实现

将复杂的循环逻辑封装为子图（`loop_graph.py`），主图保持 DAG 结构，易于理解和维护。

---

## 🏗️ 技术架构

### 技术栈

- **工作流框架**：LangGraph 1.0
- **大语言模型**：豆包 Seed (doubao-seed-1-8-251228)
- **知识库**：向量检索服务
- **语言**：Python 3.8+
- **状态管理**：Pydantic BaseModel
- **模板引擎**：Jinja2

### 目录结构

```
├── config/                    # 配置文件目录
│   ├── loop/                  # 循环检索配置
│   │   └── consult_loop_config.json
│   └── nodes/                 # 节点配置
│       ├── complexity_cfg.json
│       └── consult/           # 咨询类节点配置
│           ├── consult_context_extract_cfg.json
│           ├── consult_improvement_analysis_cfg.json
│           ├── consult_query_optimize_cfg.json
│           └── consult_rerank_cfg.json
├── docs/                      # 详细文档目录
│   ├── workflow.md            # 工作流详细说明
│   ├── configuration.md       # 配置详细说明
│   ├── development.md         # 开发详细指南
│   ├── examples.md            # 查询详细示例
│   └── architecture.md        # 技术架构说明
├── src/                       # 源代码目录
│   ├── agents/                # Agent代码
│   ├── graphs/                # 工作流编排
│   │   ├── nodes/             # 节点实现
│   │   │   ├── common.py      # 通用节点
│   │   │   ├── consult.py     # 咨询类节点
│   │   │   ├── consult_loop.py# 咨询类循环检索节点（调用子图）
│   │   │   ├── judge.py       # 行为判断类节点
│   │   │   └── mixed.py       # 混合类节点
│   │   ├── graph.py           # 主图编排
│   │   ├── loop_graph.py      # 循环检索子图
│   │   ├── state.py           # 状态定义
│   │   └── loop_config_loader.py # 配置加载器
│   ├── storage/               # 存储层
│   ├── tools/                 # 工具定义
│   └── utils/                 # 工具类
├── scripts/                   # 脚本目录
│   ├── import_knowledge.py    # 知识库导入
│   └── test_knowledge_search.py
├── assets/                    # 资源目录
│   └── knowledge/             # 知识库文件
├── README.md
└── requirements.txt
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 已配置知识库服务
- 已配置大语言模型服务

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/zzh-zzh66/Academic_Integrity_Assistant_final.git
cd Academic_Integrity_Assistant_final

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必要的配置

# 4. 导入知识库（可选）
python scripts/import_knowledge.py
```

### 运行方式

#### 方式一：本地运行工作流

```bash
bash scripts/local_run.sh -m flow
```

#### 方式二：运行单个节点

```bash
bash scripts/local_run.sh -m node -n complexity_node
```

#### 方式三：启动HTTP服务

```bash
bash scripts/http_run.sh -m http -p 5000
```

### 测试查询

```python
from graphs.graph import main_graph

# 测试咨询类问题
result = main_graph.invoke({
    "user_query": "什么是学术不端行为？"
})
print(result["formatted_response"])

# 测试行为判断类问题
result = main_graph.invoke({
    "user_query": "我能否在论文中重复使用自己已发表的内容？"
})
print(result["formatted_response"])
```

---

## 📚 详细文档

### 工作流说明
详细的工作流流程、各分支实现细节和子图说明：
- [工作流详细说明](./docs/workflow.md)

### 配置说明
配置文件结构、参数含义和使用方法：
- [配置详细说明](./docs/configuration.md)

### 开发指南
代码结构、节点开发、配置管理和测试方法：
- [开发详细指南](./docs/development.md)

### 查询示例
不同类型问题的处理流程和响应格式：
- [查询详细示例](./docs/examples.md)

### 技术架构
系统架构、数据流、模块设计和性能优化：
- [技术架构说明](./docs/architecture.md)

---

## 📋 待办事项

### 功能优化

- [ ] 完善行为判断类分支（参考咨询类分支架构）
- [ ] 完善混合类分支（参考咨询类分支架构）
- [ ] 增加更多查询示例和测试用例
- [ ] 支持多语言查询（英语等）

### 性能优化

- [ ] 减少循环轮次（max_rounds: 3→1）以提升响应速度
- [ ] 移除不必要的 LLM 节点（如 improvement_analysis_node）
- [ ] 实现并行处理（意图识别 + 术语预处理）
- [ ] 增加查询结果缓存机制
- [ ] 支持流式响应

### 用户体验

- [ ] 提供详细的参考文献链接
- [ ] 支持相关问题推荐
- [ ] 支持查询历史记录
- [ ] 提供可下载的PDF版本答案

### 工程优化

- [ ] 添加单元测试覆盖
- [ ] 完善错误处理和日志
- [ ] 优化配置文件结构
- [ ] 增加性能监控指标

---

## 👨‍💻 开发者

- **主要开发者**：zzh-zzh66 (zihuazhou02@gmail.com)
- **开发平台**：[Coze Coding](https://www.coze.cn/) - 智能AI编程平台
  - 本项目基于 Coze Coding 平台开发，利用其强大的 LangGraph 工作流编排能力和 AI 辅助编码功能
  - 平台提供了一体化的开发环境，包括代码生成、调试、测试和部署等功能

## 📞 联系方式

- 项目主页：[GitHub Repository](https://github.com/zzh-zzh66/Academic_Integrity_Assistant_final)
- 开发者邮箱：zihuazhou02@gmail.com
- 问题反馈：[Issues](https://github.com/zzh-zzh66/Academic_Integrity_Assistant_final/issues)

---

**⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！**
