# 配置详细说明

本文档详细说明学术诚信助手工作流的配置文件结构、参数含义和使用方法。

## 目录

- [配置文件结构](#配置文件结构)
- [循环检索配置](#循环检索配置)
- [检索策略配置](#检索策略配置)
- [节点配置示例](#节点配置示例)
- [配置文件最佳实践](#配置文件最佳实践)

---

## 配置文件结构

```
config/
├── intent_recognition_cfg.json        # 意图识别配置
├── consult_process_cfg.json           # 咨询类处理配置
├── response_generation_cfg.json       # 响应生成配置
├── loop/
│   └── consult_loop_config.json       # 循环检索配置
└── nodes/
    ├── complexity_cfg.json            # 复杂度判断配置
    ├── term_preprocessing_cfg.json    # 术语预处理配置
    └── consult/                       # 咨询类节点配置
        ├── consult_query_optimize_cfg.json    # 查询优化配置
        ├── consult_rerank_cfg.json            # 重排序配置
        ├── consult_context_extract_cfg.json   # 上下文提取配置
        └── consult_improvement_analysis_cfg.json # 改善分析配置
```

### 配置文件标准格式

所有配置文件遵循以下标准格式：

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
  "sp": "系统提示词（支持Jinja2模板）",
  "up": "用户提示词（支持Jinja2模板）"
}
```

**字段说明**：

- `config`：模型配置参数
  - `model`：模型ID
  - `temperature`：温度参数（0-1），控制输出的随机性
  - `top_p`：核采样参数（0-1），控制输出的多样性
  - `max_completion_tokens`：最大生成token数
  - `timeout`：超时时间（秒）
  - `thinking`：思维模式（disabled/enabled）

- `sp`：系统提示词（System Prompt），定义AI的角色和规则
- `up`：用户提示词（User Prompt），定义具体的任务

---

## 循环检索配置

### consult_loop_config.json

循环检索配置控制咨询类分支的循环检索行为：

```json
{
  "basic_params": {
    "max_rounds": 3,
    "target_score": 0.8,
    "min_score_threshold": 0.65,
    "time_limit_seconds": 15
  },
  "retrieval_params": {
    "first_round": {
      "top_k": 15,
      "min_score": 0.3
    },
    "second_round": {
      "top_k": 10,
      "min_score": 0.6
    },
    "third_round": {
      "top_k": 8,
      "min_score": 0.7
    }
  },
  "early_exit": {
    "enabled": true,
    "top_score_threshold": 0.85,
    "top_3_avg_threshold": 0.75,
    "min_round_before_early_exit": 1
  }
}
```

### 参数说明

#### basic_params（基础参数）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_rounds` | int | 3 | 最大循环轮次 |
| `target_score` | float | 0.8 | 目标综合分数 |
| `min_score_threshold` | float | 0.65 | 最低分数阈值（低于此值进入降级退出） |
| `time_limit_seconds` | int | 15 | 时间限制（秒） |

#### retrieval_params（检索参数）

每轮检索的参数配置：

| 参数 | 类型 | 说明 |
|------|------|------|
| `top_k` | int | 检索结果数量 |
| `min_score` | float | 最小相关性分数 |

**检索策略**：
- 第1轮：广泛检索（top_k=15, min_score=0.3）
- 第2轮：精准检索（top_k=10, min_score=0.6）
- 第3轮：深度检索（top_k=8, min_score=0.7）

#### early_exit（提前退出）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | true | 是否启用提前退出 |
| `top_score_threshold` | float | 0.85 | 最高分阈值 |
| `top_3_avg_threshold` | float | 0.75 | 前3平均分阈值 |
| `min_round_before_early_exit` | int | 1 | 最小轮次（在此之前不提前退出） |

**退出逻辑**：
- 当 `top_score ≥ top_score_threshold` 或 `top_3_avg ≥ top_3_avg_threshold` 时，提前退出
- 确保至少完成 `min_round_before_early_exit` 轮检索

---

## 检索策略配置

检索策略由 `consult_query_optimize_node` 根据查询复杂度动态生成：

### Simple 查询

```json
{
  "top_k": 10,
  "min_score": 0.4,
  "max_rounds": 1
}
```

**适用场景**：
- 单一概念的问题
- 明确、直接的询问
- 例如："什么是学术不端行为？"

### Standard 查询

```json
{
  "top_k": 15,
  "min_score": 0.3,
  "max_rounds": 2
}
```

**适用场景**：
- 中等复杂度的问题
- 需要综合分析的问题
- 例如："论文引用有哪些规范要求？"

### Complex 查询

```json
{
  "top_k": 20,
  "min_score": 0.25,
  "max_rounds": 3
}
```

**适用场景**：
- 多概念关联的问题
- 需要深入分析的问题
- 例如："请详细说明自我抄袭的定义，以及在不同学术领域的具体表现形式和判定标准"

---

## 节点配置示例

### 1. 意图识别配置

**文件**：`config/intent_recognition_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.1,
    "top_p": 0.7,
    "max_completion_tokens": 500,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是一个学术诚信助手，专门识别用户问题的意图类型。\n\n请将用户问题分类为以下三种类型之一：\n1. 咨询类：询问定义、规范、要求等知识性问题\n2. 行为判断类：判断特定行为是否合规\n3. 混合类：既包含咨询也包含行为判断",
  "up": "请识别以下用户问题的意图类型：\n\n用户问题：{{user_query}}\n\n请直接返回意图类型（咨询类/行为判断类/混合类），不要包含任何其他内容。"
}
```

**配置要点**：
- `temperature: 0.1`：低温度，确保分类的确定性
- `max_completion_tokens: 500`：短输出，只需返回分类结果

### 2. 复杂度判断配置

**文件**：`config/nodes/complexity_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.2,
    "top_p": 0.7,
    "max_completion_tokens": 500,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是一个学术查询复杂度分析专家，专门判断学术问题的复杂程度。\n\n复杂度分为三个等级：\n1. Simple（简单）：单一概念、明确的问题\n2. Standard（标准）：中等复杂度，需要综合分析\n3. Complex（复杂）：多概念关联、需要深入分析",
  "up": "请判断以下用户问题的复杂度：\n\n用户问题：{{user_query}}\n\n请直接返回复杂度等级（simple/standard/complex），不要包含任何其他内容。"
}
```

### 3. 查询优化配置

**文件**：`config/nodes/consult/consult_query_optimize_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.3,
    "top_p": 0.7,
    "max_completion_tokens": 800,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是一个学术查询优化专家，专门优化学术问题的检索查询。\n\n根据查询复杂度，生成相应的检索策略：\n- Simple：聚焦核心，减少噪音，快速检索（top_k=10, min_score=0.4, max_rounds=1）\n- Standard：平衡准确性和全面性（top_k=15, min_score=0.3, max_rounds=2）\n- Complex：扩展范围，保留更多信息，多轮优化（top_k=20, min_score=0.25, max_rounds=3）",
  "up": "请优化以下查询并生成检索策略：\n\n用户问题：{{user_query}}\n优化查询：{{refined_query}}\n关键词：{{refined_keywords}}\n复杂度：{{query_complexity}}\n\n请返回JSON格式：\n{\n  \"optimized_query\": \"优化后的查询\",\n  \"retrieval_strategy\": {\n    \"top_k\": 15,\n    \"min_score\": 0.3,\n    \"max_rounds\": 2\n  }\n}"
}
```

### 4. 重排序配置

**文件**：`config/nodes/consult/consult_rerank_cfg.json`

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
  "sp": "你是一个学术内容评估专家，专门评估知识库检索结果的质量。\n\n请从以下四个维度对每个结果进行评分（0-1分）：\n1. 相关性：与查询的匹配程度\n2. 权威性：来源的可信度\n3. 完整性：信息的完整性\n4. 时效性：信息的新鲜度\n\n综合分数计算：相关性×0.4 + 权威性×0.3 + 完整性×0.2 + 时效性×0.1",
  "up": "请对以下检索结果进行评分和排序：\n\n用户查询：{{user_query}}\n检索结果：\n{% for result in expanded_results %}\n{{ loop.index }}. {{ result.content }}\n{% endfor %}\n\n请返回JSON格式：\n{\n  \"ranked_results\": [排好序的结果索引],\n  \"weighted_scores\": [对应的加权分数],\n  \"top_score\": 最高分数,\n  \"top_3_avg\": 前3平均分\n}"
}
```

### 5. 改善分析配置

**文件**：`config/nodes/consult/consult_improvement_analysis_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.4,
    "top_p": 0.7,
    "max_completion_tokens": 1000,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是一个学术检索优化分析师，专门评估检索结果的改善潜力。\n\n请分析当前检索结果的质量，并预测下一轮检索的改善潜力：\n- 高：有较大改善空间，建议继续检索\n- 中：有一定改善空间，可以继续检索\n- 低：改善空间有限，建议退出\n\n同时提供优化建议。",
  "up": "请分析以下检索结果：\n\n用户查询：{{user_query}}\n当前轮次：{{current_round}}\n综合分数：{{weighted_score}}\n最高分数：{{top_score}}\n前3平均分：{{top_3_avg}}\n关键概念：{{key_concepts}}\n缺失方面：{{missing_aspects}}\n\n请返回JSON格式：\n{\n  \"improvement_potential\": \"高/中/低\",\n  \"recommendation\": \"优化建议\"\n}"
}
```

### 6. 响应生成配置

**文件**：`config/response_generation_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.5,
    "top_p": 0.7,
    "max_completion_tokens": 3000,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是一个学术诚信顾问，专门回答学术道德、学术规范、学术不端行为等相关问题。\n\n请基于提供的知识库检索结果，生成专业、准确、可信的答案。\n\n回答要求：\n1. 采用自然对话风格，去除系统内部信息\n2. 每个观点标注信息来源\n3. 提供可验证的参考文献或来源\n4. 遵循学术严谨性，不编造内容\n5. 如果信息不足，明确说明并建议进一步查询",
  "up": "请基于以下检索结果回答用户问题：\n\n用户问题：{{user_query}}\n意图类型：{{intent_type}}\n\n检索结果：\n{% for result in retrieval_results %}\n{{ loop.index }}. {{ result.content }}\n（来源：{{ result.source }}）\n{% endfor %}\n\n请生成自然对话风格的答案，标注信息来源。"
}
```

**配置要点**：
- `temperature: 0.5`：中等温度，保持专业性的同时有一定的灵活性
- `max_completion_tokens: 3000`：较长输出，支持详细的答案

---

## 配置文件最佳实践

### 1. 提示词设计

**系统提示词（SP）**：
- 清晰定义AI的角色和职责
- 明确任务边界和约束条件
- 提供详细的规则和示例
- 避免过于复杂的指令

**用户提示词（UP）**：
- 使用Jinja2模板支持动态参数
- 明确输入数据的格式和来源
- 明确输出的格式要求
- 提供示例以引导AI理解

### 2. 参数调优

**temperature**：
- 分类任务：0.1-0.2（确定性高）
- 分析任务：0.3-0.4（平衡）
- 生成任务：0.5-0.7（创造性）

**max_completion_tokens**：
- 分类任务：500-800
- 分析任务：1000-2000
- 生成任务：2000-3000

**top_p**：
- 通常设置为0.7，平衡多样性和质量

### 3. 配置文件管理

**版本控制**：
- 所有配置文件应纳入版本控制
- 重要修改应添加注释说明原因
- 建议使用Git的分支策略管理不同环境

**命名规范**：
- 使用下划线分隔单词
- 以 `_cfg.json` 结尾
- 按功能模块组织

**测试验证**：
- 修改配置后应进行充分测试
- 对比不同配置的效果
- 记录最佳实践和经验

### 4. 性能优化

**减少循环轮次**：
- `max_rounds: 3 → 1` 可显著提升响应速度
- 适用于简单问题和快速响应场景

**提前退出**：
- 启用提前退出机制
- 设置合理的阈值
- 平衡响应速度和结果质量

**缓存机制**：
- 对相同查询启用缓存
- 设置合理的缓存过期时间
- 避免重复检索

### 5. 错误处理

**超时设置**：
- 合理设置 `timeout` 参数
- 避免因网络问题导致长时间等待
- 默认值为600秒（10分钟）

**降级策略**：
- 当检索失败时，提供降级方案
- 返回已有结果或建议用户重试
- 记录错误日志供排查

**日志记录**：
- 记录关键配置参数
- 记录检索结果和评分
- 便于问题排查和性能分析

---

## 总结

配置文件是工作流的核心组成部分，通过合理的配置可以实现：

1. **灵活控制**：动态调整检索策略和行为
2. **性能优化**：平衡响应速度和结果质量
3. **可维护性**：集中管理参数和提示词
4. **可扩展性**：易于添加新功能和调整逻辑

相关文档：
- [工作流说明](./workflow.md)
- [开发指南](./development.md)
- [查询示例](./examples.md)
- [技术架构](./architecture.md)
