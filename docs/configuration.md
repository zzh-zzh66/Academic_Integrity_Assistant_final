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

### 7. 行为判断类查询优化配置

**文件**：`config/nodes/judge/judge_query_optimize_cfg.json`

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
  "sp": "你是一个学术行为分析专家，专门优化学术行为判断的检索查询。\n\n请从用户问题中提取行为要素（主体、动作、对象），并构建增强的检索查询。\n\n行为要素说明：\n- 主体：执行行为的人或机构\n- 动作：具体的行为描述\n- 对象：行为所涉及的事物\n\n检索策略：行为判断类需要高精度匹配，因此采用2轮增强检索策略，确保检索到相关的规范条款。",
  "up": "请优化以下查询并提取行为要素：\n\n用户问题：{{user_query}}\n优化查询：{{refined_query}}\n关键词：{{refined_keywords}}\n\n请返回JSON格式：\n{\n  \"optimized_query\": \"优化后的查询\",\n  \"behavior_subject\": \"行为主体\",\n  \"behavior_action\": \"行为动作\",\n  \"behavior_object\": \"行为对象\",\n  \"optimized_keywords\": [\"关键词列表\"],\n  \"retrieval_strategy\": {\n    \"top_k_first_round\": 20,\n    \"min_score_first_round\": 0.3,\n    \"top_k_second_round\": 15,\n    \"min_score_second_round\": 0.5\n  }\n}"
}
```

### 8. 行为判断类违规判断配置

**文件**：`config/nodes/judge/judge_decision_cfg.json`

```json
{
  "config": {
    "model": "doubao-seed-1-8-251228",
    "temperature": 0.1,
    "top_p": 0.9,
    "max_completion_tokens": 2000,
    "timeout": 600,
    "thinking": "disabled"
  },
  "sp": "你是学术规范判断专家，负责基于拓宽的上下文判断用户行为是否违规。输入的上下文已经过聚类去重和MMR重排序优化，确保了质量和多样性。在判断时，你需要评估判断的置信度，并在信息不足时识别需要追问的内容。注意：输出时要智能聚合相似规则，避免重复表述；从不同文档和角度提取判断依据，提升判断的全面性和准确性。",
  "up": "## 任务\n\n基于以下信息判断用户行为是否违规（输入已优化，避免重复内容）：\n\n## 用户问题\n{{user_query}}\n\n## 拓宽的上下文（完整段落，已去重和优化）\n{% for paragraph in full_context_paragraphs %}\n- {{paragraph}}\n{% endfor %}\n\n## 关联规则\n{% for rule in related_rules %}\n- {{rule}}\n{% endfor %}\n\n## 判断依据\n{{decision_basis}}\n\n## 行为要素\n{% if behavior_subject %}主体：{{behavior_subject}}{% endif %}\n{% if behavior_action %}动作：{{behavior_action}}{% endif %}\n{% if behavior_object %}对象：{{behavior_object}}{% endif %}\n\n## 要求\n\n1. **判断是否违规**：基于规则和上下文，判断行为是否违规\n2. **智能聚合规则**：不要简单罗列相似规则，要将内容相近的规则合并表述，避免重复\n3. **多样化判断依据**：从不同文档、不同角度提取判断依据，确保判断的全面性\n4. **评估置信度**：评估判断的置信度（0-1），判断等级（high/medium/low）\n   - high（≥0.8）：信息充分，规则明确，判断可靠\n   - medium（0.6-0.8）：信息较充分，规则较明确，判断较可靠\n   - low（<0.6）：信息不足或规则模糊，判断不可靠\n5. **识别追问需求**：如果置信度较低或信息不足，列出需要追问的问题\n6. **列出缺失信息**：如果无法判断，列出缺失的关键信息\n\n返回JSON格式：\n{\n  \"can_judge\": true/false,\n  \"is_violation\": true/false,\n  \"judgment_basis\": \"判断依据说明（合并相似规则，从多角度阐述）\",\n  \"relevant_rules\": [\"规则1\", \"规则2\"],\n  \"confidence_score\": 0.85,\n  \"confidence_level\": \"high\",\n  \"needs_clarification\": false,\n  \"clarification_questions\": [],\n  \"missing_information\": [],\n  \"ambiguity_reasons\": [],\n  \"suggested_actions\": [],\n  \"warning_notes\": []\n}"
}
```

**配置要点**：
- `temperature: 0.1`：低温度，确保判断的确定性
- 系统提示词强调智能聚合和多样化依据提取
- 明确置信度等级的划分标准
- 支持追问和缺失信息识别

---

## 去重优化配置说明

行为判断类分支采用多级去重策略，确保检索结果的质量和多样性。相关配置已集成在节点实现中，无需额外配置文件。

### 去重策略参数

#### 1. 贪心聚类参数

**位置**：`judge_retrieval_enhanced_node`

**参数**：
```python
similarity_threshold = 0.70  # Jaccard相似度阈值
```

**说明**：
- 相似度 ≥ 0.70 的片段归为同一聚类
- 按分数降序排序，贪心分配到现有聚类或创建新聚类

#### 2. MMR重排序参数

**位置**：`judge_retrieval_enhanced_node`

**参数**：
```python
lambda_param = 0.88  # 相关性权重
top_k = 12  # 返回的top-k结果数量
```

**说明**：
- `lambda_param = 0.88`：偏重相关性（0-1之间，越高越重视相关性）
- `top_k = 12`：从聚类代表片段中选择12个结果
- MMR公式：`MMR = lambda * Rel - (1-lambda) * MaxSim`

#### 3. 段落级别去重参数

**位置**：`judge_context_expand_enhanced_node`

**参数**：
```python
similarity_threshold = 0.75  # Jaccard相似度阈值
```

**说明**：
- 相似度 ≥ 0.75 的段落视为重复
- 按doc_id分组，文档内部去重，文档之间不跨文档去重
- 保留高分段落，确保文档来源多样性

### 参数调优建议

| 参数 | 当前值 | 建议范围 | 效果 |
|------|--------|----------|------|
| 聚类threshold | 0.70 | 0.65-0.75 | 降低阈值增加聚类数量，提高阈值减少聚类 |
| MMR lambda | 0.88 | 0.85-0.90 | 提高lambda增加相关性，降低lambda增加多样性 |
| MMR top_k | 12 | 10-15 | 增加top_k保留更多结果，减少top_k提高精度 |
| 段落去重threshold | 0.75 | 0.70-0.80 | 降低阈值增加去重力度，提高阈值减少去重 |

**调优建议**：
- 如果检索结果重复严重：降低聚类threshold和段落去重threshold
- 如果检索结果多样性不足：降低MMR lambda
- 如果检索结果精度不足：提高MMR lambda，减少MMR top_k

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
