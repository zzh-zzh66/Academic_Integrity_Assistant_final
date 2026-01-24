# 工作流详细说明

本文档详细说明学术诚信助手工作流的整体流程和各分支实现细节。

## 目录

- [主图流程](#主图流程)
- [咨询类分支](#咨询类分支)
- [行为判断类分支](#行为判断类分支)
- [混合类分支](#混合类分支)
- [循环检索子图](#循环检索子图)
- [去重算法详解](#去重算法详解)

---

## 主图流程

主图是一个有向无环图（DAG），实现三类意图的分流处理：

```mermaid
graph TD
    Start([开始]) --> Complexity[complexity_node<br/>复杂度判断]
    Complexity --> Intent[intent_recognition_node<br/>意图识别]
    Intent --> Term[term_preprocessing_node<br/>术语预处理]
    
    Term --> Route{意图类型?}
    
    Route -->|咨询类| ConsultProcess[consult_process_node<br/>咨询类处理]
    Route -->|行为判断类| JudgeProcess[judge_process_node<br/>行为判断类处理]
    Route -->|混合类| MixedProcess[mixed_process_node<br/>混合类处理]
    
    ConsultProcess --> ConsultOptimize[consult_query_optimize_node<br/>查询优化]
    ConsultOptimize --> ConsultLoop[consult_retrieval_loop_node<br/>循环检索子图]
    
    ConsultLoop --> Consolidation[consult_results_consolidation_node<br/>结果整合]
    Consolidation --> Response[response_generation_node<br/>响应生成]
    
    JudgeProcess --> JudgeRetrieval[judge_retrieval_node<br/>知识库检索]
    MixedProcess --> MixedRetrieval[mixed_retrieval_node<br/>知识库检索]
    
    JudgeRetrieval --> JudgeExpand[judge_context_expand_node<br/>上下文扩展]
    MixedRetrieval --> MixedExpand[mixed_context_expand_node<br/>上下文扩展]
    
    JudgeExpand --> JudgeRerank[judge_rerank_node<br/>重排序]
    MixedExpand --> MixedRerank[mixed_rerank_node<br/>重排序]
    
    ConsultLoop --> Response[response_generation_node<br/>响应生成]
    JudgeRerank --> Response
    MixedRerank --> Response
    
    Response --> End([结束])
    
    style Complexity fill:#e1f5ff
    style ConsultOptimize fill:#fff4e1
    style ConsultLoop fill:#f3e5f5
    style Response fill:#e8f5e9
```

### 流程说明

1. **开始阶段**
   - 接收用户查询（`user_query`）
   - 传递到复杂度判断节点

2. **预处理阶段**
   - `complexity_node`：判断查询复杂度（simple/standard/complex）
   - `intent_recognition_node`：识别意图类型（咨询类/行为判断类/混合类）
   - `term_preprocessing_node`：术语标准化和要素提取

3. **分流处理阶段**
   - 根据意图类型，路由到不同的分支
   - 每个分支有独立的处理逻辑

4. **响应生成阶段**
   - 所有分支最终汇聚到响应生成节点
   - 生成自然对话风格的答案

---

## 咨询类分支

咨询类分支是当前最完善的分支，包含复杂度判断、查询优化、循环检索和响应生成：

```mermaid
graph TD
    Input[用户查询] --> Complexity[complexity_node<br/>复杂度判断]
    Complexity -->|query_complexity| Intent[intent_recognition_node<br/>意图识别]
    Intent --> Term[term_preprocessing_node<br/>术语预处理]
    Term --> ConsultProcess[consult_process_node<br/>咨询类处理]
    
    ConsultProcess -->|refined_query<br/>refined_keywords| ConsultOptimize[consult_query_optimize_node<br/>查询优化]
    
    ConsultOptimize -->|optimized_query<br/>retrieval_strategy| ConsultLoop[consult_retrieval_loop_node<br/>循环检索子图]
    
    ConsultLoop -->|history_results<br/>current_results| Consolidation[consult_results_consolidation_node<br/>结果整合]
    Consolidation -->|unified_results| Response[response_generation_node<br/>响应生成]
    
    Response --> Output[格式化响应]
    
    style Complexity fill:#e1f5ff
    style ConsultOptimize fill:#fff4e1
    style ConsultLoop fill:#f3e5f5
    style Response fill:#e8f5e9
```

### 关键节点说明

#### 1. complexity_node（复杂度判断）

**输入**：`user_query`（用户原始查询）

**输出**：`query_complexity`（simple/standard/complex）

**作用**：根据问题的复杂度决定后续检索策略

- **Simple**：单一概念、明确的问题
- **Standard**：中等复杂度，需要综合分析
- **Complex**：多概念关联、需要深入分析

#### 2. consult_query_optimize_node（查询优化）

**输入**：
- `refined_query`：优化后的查询
- `refined_keywords`：提取的关键词
- `query_complexity`：查询复杂度

**输出**：
- `optimized_query`：最终优化的查询
- `retrieval_strategy`：检索策略（包含 top_k, min_score, max_rounds）

**作用**：根据复杂度生成动态检索策略

**检索策略示例**：

```python
# Simple 查询
{
  "top_k": 10,
  "min_score": 0.4,
  "max_rounds": 1
}

# Standard 查询
{
  "top_k": 15,
  "min_score": 0.3,
  "max_rounds": 2
}

# Complex 查询
{
  "top_k": 20,
  "min_score": 0.25,
  "max_rounds": 3
}
```

#### 3. consult_retrieval_loop_node（循环检索子图）

**输入**：
- `user_query`：用户原始查询
- `optimized_query`：优化后的查询
- `retrieval_strategy`：检索策略

**输出**：
- `retrieval_results`：最终检索结果

**作用**：通过循环检索和 LLM 增强获取高质量结果

**详细流程**：见[循环检索子图详解](#循环检索子图)

#### 4. consult_results_consolidation_node（结果整合）

**输入**：
- `history_results`：历史检索结果（多轮累积）
- `current_results`：当前轮检索结果
- `user_query`：用户原始查询

**输出**：
- `unified_results`：整合后的统一结果（top-15）
- `total_count`：总片段数
- `avg_score`：平均相关性分数
- `max_score`：最高相关性分数
- `top_3_contents`：top-3内容
- `summary`：检索结果简要总结
- `retrieval_results`：供下游使用的检索结果

**作用**：整合多轮检索结果，执行轮间去重、质量过滤和结果重排序

**处理流程**：
1. **合并结果**：合并历史结果和当前结果
2. **轮间去重**：使用 Jaccard 相似度（threshold=0.75）去除重复片段
3. **质量过滤**：过滤掉分数低于 0.3 的片段
4. **重新排序**：按相关性分数降序排序
5. **Top-K 截断**：保留 top-15 个最相关片段
6. **评估指标计算**：计算总数量、平均分数、最高分数等指标
7. **生成总结**：基于检索结果生成简要总结

**输出示例**：
```json
{
  "unified_results": [
    {
      "content": "学术不端行为是指在学术活动中违反学术规范的行为...",
      "score": 0.92,
      "doc_id": "doc_001",
      "file_name": "学术规范.pdf"
    }
    // ... 最多15个片段
  ],
  "total_count": 12,
  "avg_score": 0.78,
  "max_score": 0.92,
  "top_3_contents": ["片段1", "片段2", "片段3"],
  "summary": "检索到12条相关资料，最高相关性0.92，平均相关性0.78，涵盖定义、类型、判定标准、处理流程等4个方面。"
}
```

---

## 行为判断类分支

行为判断类分支用于判断特定行为是否符合学术规范，采用增强检索和去重优化策略：

```mermaid
graph TD
    Input[用户查询] --> Intent[intent_recognition_node<br/>意图识别]
    Intent --> Term[term_preprocessing_node<br/>术语预处理]
    Term --> JudgeProcess[judge_process_node<br/>行为判断类处理]
    
    JudgeProcess -->|optimized_query<br/>behavior_elements| JudgeQueryOpt[judge_query_optimize_node<br/>查询优化]
    JudgeQueryOpt --> JudgeRetrieval[judge_retrieval_enhanced_node<br/>增强检索+去重]
    
    JudgeRetrieval -->|retrieval_results| JudgeExpand[judge_context_expand_enhanced_node<br/>拓宽上下文+段落去重]
    JudgeExpand --> JudgeDecision[judge_decision_node<br/>违规判断]
    
    JudgeDecision --> Response[response_generation_node<br/>响应生成]
    
    Response --> Output[格式化响应]
    
    style JudgeRetrieval fill:#e1f5ff
    style JudgeExpand fill:#fff4e1
    style JudgeDecision fill:#fce4ec
    style Response fill:#e8f5e9
```

### 关键节点说明

#### 1. judge_query_optimize_node（查询优化）

**输入**：
- `user_query`：用户原始查询
- `refined_query`：优化后的查询
- `refined_keywords`：提取的关键词

**输出**：
- `optimized_query`：最终优化的查询
- `behavior_subject`：行为主体
- `behavior_action`：行为动作
- `behavior_object`：行为对象
- `optimized_keywords`：优化的关键词

**作用**：提取行为要素，构建增强检索查询

#### 2. judge_retrieval_enhanced_node（增强检索+去重）

**输入**：
- `user_query`：用户原始查询
- `optimized_query`：优化后的查询
- `retrieval_strategy`：检索策略（由查询优化节点设置）

**输出**：
- `retrieval_results`：经过去重和重排序的检索结果（top-12）

**作用**：执行2轮循环检索，通过聚类去重和MMR重排序获取高质量结果

**处理流程**：
```
知识库检索（20条）
  → 贪心聚类（Jaccard, threshold=0.70）
  → 每个聚类保留最高分片段（策略A）
  → MMR重排序（lambda=0.88, top_k=12）
  → 输出最终结果
```

**去重优化策略**：

1. **贪心聚类算法**
   - 使用Jaccard相似度计算片段间相似度（threshold=0.70）
   - 按分数降序排序，贪心分配到现有聚类或创建新聚类
   - 目的：识别并分组高度相似的内容

2. **代表片段选择（策略A）**
   - 每个聚类只保留最高分片段
   - 确保每个代表都是高质量
   - 避免引入低相关性内容

3. **MMR重排序**
   - 平衡相关性和多样性（lambda=0.88，偏重相关性）
   - 从代表片段中选择top-12个结果
   - 确保输出的多样性和质量

**检索策略示例**：

```python
# 行为判断类检索策略
{
  "top_k_first_round": 20,      # 第1轮检索20条
  "min_score_first_round": 0.3, # 第1轮最低分数
  "top_k_second_round": 15,     # 第2轮检索15条
  "min_score_second_round": 0.5 # 第2轮最低分数
}
```

#### 3. judge_context_expand_enhanced_node（拓宽上下文+段落去重）

**输入**：
- `retrieval_results`：经过去重和重排序的检索结果（top-12）

**输出**：
- `full_context_paragraphs`：拓宽后的完整段落（已去重）
- `related_rules`：关联的规则引用
- `decision_basis`：判断依据说明

**作用**：将检索片段扩展为完整段落，并进行段落级别去重

**处理流程**：
```
扩展内容到完整段落（300-500字）
  → 按doc_id分组
  → 每个文档内部进行Jaccard去重（threshold=0.75）
  → 保留最高分段落
  → 输出去重后的完整段落
```

**段落去重策略**：

1. **按doc_id分组**
   - 将所有段落按文档ID分组
   - 保证不同文档之间不跨文档去重
   - 避免单一文档内容过度主导

2. **文档内部去重**
   - 使用Jaccard相似度计算段落间相似度（threshold=0.75）
   - 按分数降序排序，贪心保留高分的非重复段落
   - 确保文档来源多样性

3. **拓宽上下文**
   - 每个片段扩展到300-500字的完整段落
   - 理解规则全貌，提供更完整的判断依据

#### 4. judge_decision_node（违规判断）

**输入**：
- `user_query`：用户原始查询
- `full_context_paragraphs`：拓宽后的完整段落（已去重）
- `related_rules`：关联的规则引用
- `decision_basis`：判断依据说明
- `behavior_subject`：行为主体
- `behavior_action`：行为动作
- `behavior_object`：行为对象

**输出**：
- `can_judge`：是否能够判断
- `is_violation`：是否违规（true/false/null）
- `judgment_basis`：判断依据说明（智能聚合相似规则）
- `relevant_rules`：相关规则引用
- `confidence_score`：置信度分数（0-1）
- `confidence_level`：置信度等级（high/medium/low）
- `needs_clarification`：是否需要澄清
- `clarification_questions`：需要澄清的问题列表
- `missing_information`：缺失的信息列表
- `ambiguity_reasons`：模糊的原因
- `suggested_actions`：建议的行动
- `warning_notes`：警告说明

**作用**：基于拓宽的上下文判断是否违规，评估置信度

**判断特点**：
- 智能聚合相似规则，避免重复表述
- 从不同文档和角度提取判断依据
- 评估判断的置信度，识别需要追问的内容
- 提供结构化的判断结果和证据支持

**置信度等级**：
- **High（≥0.8）**：信息充分，规则明确，判断可靠
- **Medium（0.6-0.8）**：信息较充分，规则较明确，判断较可靠
- **Low（<0.6）**：信息不足或规则模糊，判断不可靠

---

## 混合类分支

混合类分支处理同时包含咨询和行为判断的问题：

```mermaid
graph TD
    Input[用户查询] --> Intent[intent_recognition_node<br/>意图识别]
    Intent --> Term[term_preprocessing_node<br/>术语预处理]
    Term --> MixedProcess[mixed_process_node<br/>混合类处理]
    
    MixedProcess --> Split{拆分查询}
    
    Split -->|咨询部分| ConsultSub[consult_subgraph_node<br/>咨询子图]
    Split -->|判断部分| JudgeSub[judge_subgraph_node<br/>判断子图]
    
    ConsultSub -->|consult_results| Integration[integration_node<br/>结果整合]
    JudgeSub -->|judge_results| Integration
    
    Integration --> Response[response_generation_node<br/>响应生成]
    
    Response --> Output[格式化响应]
    
    style Split fill:#fff4e1
    style ConsultSub fill:#e1f5ff
    style JudgeSub fill:#f3e5f5
    style Integration fill:#e8f5e9
```

### 关键节点说明

#### 1. mixed_process_node（混合类处理）

**输入**：
- `refined_query`：优化后的查询
- `refined_keywords`：提取的关键词

**输出**：
- `consult_query`：咨询部分的查询
- `judge_query`：判断部分的查询
- `shared_context`：共享的上下文信息

**作用**：将混合查询拆分为咨询和判断两个部分

#### 2. consult_subgraph_node（咨询子图）

**输入**：
- `consult_query`：咨询部分的查询
- `shared_context`：共享上下文

**输出**：
- `consult_results`：咨询结果

**作用**：调用咨询类子图，复用咨询类分支的逻辑（2轮循环检索）

#### 3. judge_subgraph_node（判断子图）

**输入**：
- `judge_query`：判断部分的查询
- `behavior_elements`：行为要素
- `shared_context`：共享上下文

**输出**：
- `judge_results`：判断结果

**作用**：调用判断类子图，复用判断类分支的逻辑（增强检索）

#### 4. integration_node（结果整合）

**输入**：
- `consult_results`：咨询结果
- `judge_results`：判断结果
- `shared_context`：共享上下文

**输出**：
- `integrated_results`：整合后的结果

**作用**：将咨询和判断结果整合为统一的答案

---

## 循环检索子图

循环检索子图是咨询类分支的核心，通过多轮检索和 LLM 增强持续提升质量：

```mermaid
graph TD
    Start[子图开始] --> Retrieval[consult_retrieval_internal_node<br/>知识库检索]
    Retrieval --> Expand[consult_expand_internal_node<br/>内容扩展]
    Expand --> Rerank[rerank_node<br/>多维度重排序]
    Rerank --> ContextExtract[context_extract_node<br/>上下文提取]
    ContextExtract --> Improvement[improvement_analysis_node<br/>改善分析]
    Improvement --> Condition{循环条件判断}
    
    Condition -->|继续循环| Retrieval
    Condition -->|成功退出| SuccessExit[退出成功]
    Condition -->|降级退出| FallbackExit[退出降级]
    
    SuccessExit --> End[子图结束]
    FallbackExit --> End
    
    style Retrieval fill:#e1f5ff
    style Rerank fill:#fff4e1
    style ContextExtract fill:#f3e5f5
    style Improvement fill:#fce4ec
    style SuccessExit fill:#e8f5e9
    style FallbackExit fill:#ffebee
```

### 子图节点说明

#### 1. consult_retrieval_internal_node（知识库检索）

**输入**：
- `user_query`：用户原始查询
- `refined_query`：优化后的查询
- `refined_keywords`：提取的关键词
- `current_round`：当前轮次

**输出**：
- `retrieval_results`：检索结果片段列表

**作用**：根据动态参数（top_k, min_score）执行知识库检索

**检索参数**：
- 第1轮：top_k=15, min_score=0.3
- 第2轮：top_k=10, min_score=0.6
- 第3轮：top_k=8, min_score=0.7

#### 2. consult_expand_internal_node（内容扩展）

**输入**：
- `retrieval_results`：检索结果片段

**输出**：
- `expanded_results`：扩展后的完整段落

**作用**：将检索结果扩展到完整段落（500-800字），提供更完整的上下文

#### 3. rerank_node（多维度重排序）

**输入**：
- `expanded_results`：扩展后的结果
- `user_query`：用户查询

**输出**：
- `ranked_results`：排序后的结果
- `weighted_score`：加权分数
- `top_score`：最高分数
- `top_3_avg`：前3平均分

**作用**：对结果进行多维度评分和排序

**评分维度**：
- **相关性（40%）**：与查询的匹配程度
- **权威性（30%）**：来源的可信度
- **完整性（20%）**：信息的完整性
- **时效性（10%）**：信息的新鲜度

#### 4. context_extract_node（上下文提取）

**输入**：
- `ranked_results`：排序后的结果（top-3）

**输出**：
- `structured_context`：结构化上下文
  - `key_concepts`：关键概念
  - `relation_map`：关系图谱
  - `missing_aspects`：缺失方面
  - `summary`：总结

**作用**：提取关键信息和上下文，为后续改善分析提供依据

#### 5. improvement_analysis_node（改善分析）

**输入**：
- `ranked_results`：排序后的结果
- `structured_context`：结构化上下文
- `history`：历史轮次信息

**输出**：
- `improvement_potential`：改善潜力（高/中/低）
- `recommendation`：优化建议

**作用**：LLM 分析下一轮的改善潜力，指导循环决策

#### 6. 循环条件判断

**判断条件**：
- 综合分数 ≥ target_score（默认 0.8）
- 轮次 ≥ max_rounds（默认 3）
- LLM 预测改善潜力不足
- 检测到收敛或停滞

**输出**：
- `continue`：继续下一轮
- `exit_success`：成功退出（返回高质量结果）
- `exit_fallback`：降级退出（返回当前最佳结果）

**提前退出条件**：
- top_score ≥ 0.85
- top_3_avg ≥ 0.75
- 至少完成1轮检索

---

## 去重算法详解

本节详细说明咨询类分支的去重算法实现，包括轮内去重和轮间去重两个层级。

### 去重策略概述

咨询类采用**分层去重策略**：
1. **轮内去重**：在每轮检索后立即执行，去除本轮内的重复片段
2. **轮间去重**：在结果整合阶段执行，去除多轮之间的重复片段

### 轮内去重算法

轮内去重在循环检索子图的检索节点中应用，采用**贪心聚类 + MMR重排序**的组合策略。

#### 算法流程

```mermaid
graph TD
    Input[原始检索结果] --> Sort[按分数降序排序]
    Sort --> Cluster[贪心聚类<br/>Jaccard threshold=0.70]
    Cluster --> Rep[选择代表片段<br/>每个聚类取最高分]
    Rep --> MMR[MMR重排序<br/>lambda=0.85, top_k=10]
    MMR --> Output[去重后结果]
    
    style Cluster fill:#e1f5ff
    style MMR fill:#f3e5f5
```

#### 步骤1：贪心聚类（Greedy Clustering）

**算法原理**：
- 基于文本的 Jaccard 相似度进行聚类
- 按分数降序遍历结果，将相似片段归入同一聚类
- 使用贪心策略，确保每个聚类内的片段高度相似

**Jaccard 相似度计算**：
```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

其中 A 和 B 是文本的词集合。

**聚类参数**：
- `similarity_threshold`：0.70
- 相似度 ≥ 0.70 的片段归入同一聚类

**聚类效果示例**：
```
输入片段: 15个
聚类结果: 5个聚类
  - 聚类0: 4个片段（关于定义）
  - 聚类1: 3个片段（关于类型）
  - 聚类2: 3个片段（关于判定标准）
  - 聚类3: 3个片段（关于处理流程）
  - 聚类4: 2个片段（关于案例）
```

#### 步骤2：选择代表片段（Representative Selection）

**策略**：每个聚类保留最高分片段

**选择逻辑**：
```python
for cluster in clusters:
    representative = max(cluster, key=lambda x: x["score"])
    representatives.append(representative)
```

**优势**：
- 确保质量：每个聚类保留最相关的片段
- 减少冗余：避免重复相似内容
- 保持多样性：不同聚类代表不同主题

#### 步骤3：MMR 重排序（Maximal Marginal Relevance）

**算法原理**：
- 平衡相关性（Relevance）和多样性（Diversity）
- 使用贪心迭代选择，每次选择边际相关性最高的片段

**MMR 公式**：
```
MMR = λ * Sim(D, Q) - (1 - λ) * max_{Di∈S} Sim(D, Di)
```

其中：
- `D`：候选片段
- `Q`：查询
- `S`：已选片段集合
- `λ`：相关性权重（0-1）
- `Sim`：相似度函数（使用 Jaccard）

**MMR 参数**：
- `lambda`：0.85（比行为判断类稍低，保留更多多样性）
- `top_k`：10

**重排序效果**：
```
输入: 5个代表片段
输出: 10个高质量、多样化片段
  - 片段1: 定义 (score=0.95)
  - 片段2: 类型A (score=0.88)
  - 片段3: 类型B (score=0.85)
  - 片段4: 判定标准 (score=0.82)
  - 片段5: 处理流程 (score=0.80)
  - ...（最多10个）
```

#### 轮内去重效果

**数据对比**：
```
第1轮：
  - 原始结果: 15个片段
  - 去重后: 8个片段
  - 去重率: 46.7%

第2轮：
  - 原始结果: 12个片段
  - 去重后: 7个片段
  - 去重率: 41.7%
```

### 轮间去重算法

轮间去重在结果整合节点中执行，采用**基于 Jaccard 相似度的简单去重**策略。

#### 算法流程

```mermaid
graph TD
    Input1[历史结果<br/>history_results] --> Merge[合并所有结果]
    Input2[当前结果<br/>current_results] --> Merge
    Merge --> Dedup[Jaccard去重<br/>threshold=0.75]
    Dedup --> Filter[质量过滤<br/>score >= 0.3]
    Filter --> Sort[按分数排序]
    Sort --> TopK[保留top-15]
    TopK --> Output[统一结果]
    
    style Dedup fill:#e1f5ff
    style Filter fill:#fff4e1
    style Output fill:#e8f5e9
```

#### 去重逻辑

**合并所有结果**：
```python
all_results = history_results + current_results
```

**去重策略**：
1. 按分数降序排序结果
2. 遍历结果，使用 Jaccard 相似度判断重复
3. 如果与已选片段的相似度 ≥ 0.75，则跳过
4. 否则，加入结果列表

**去重参数**：
- `similarity_threshold`：0.75（比轮内稍高，减少误删）

**伪代码**：
```python
def merge_and_dedup(history, current, threshold=0.75):
    all_results = history + current
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    deduped = []
    for result in all_results:
        is_duplicate = False
        for selected in deduped:
            similarity = jaccard(result["content"], selected["content"])
            if similarity >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            deduped.append(result)
    
    return deduped
```

### 质量过滤与重排序

去重后，还需要进行质量过滤和重排序：

#### 1. 质量过滤

**过滤条件**：`score >= 0.3`

**作用**：去除低相关性的片段，确保结果质量

**示例**：
```
去重后: 20个片段
过滤后: 15个片段（过滤掉5个低分片段）
```

#### 2. 按分数排序

**排序方式**：按相关性分数降序排序

**作用**：将最相关的片段放在前面

#### 3. Top-K 截断

**保留数量**：top-15

**作用**：控制输出规模，避免过多信息

### 评估指标计算

结果整合节点还会计算以下评估指标：

| 指标 | 说明 | 示例值 |
|------|------|--------|
| `total_count` | 总片段数 | 12 |
| `avg_score` | 平均分数 | 0.78 |
| `max_score` | 最高分数 | 0.92 |

这些指标可以帮助：
- 评估检索质量
- 判断是否需要调整检索策略
- 提供检索过程的透明度

### 去重参数对比

咨询类与行为判断类的去重参数对比：

| 参数 | 咨询类 | 行为判断类 | 说明 |
|------|--------|-----------|------|
| **轮内 Jaccard** | 0.70 | 0.70 | 相同 |
| **轮间 Jaccard** | 0.75 | - | 行为判断类无轮间去重 |
| **MMR lambda** | 0.85 | 0.88 | 咨询类更重视多样性 |
| **MMR top_k** | 10 | 12 | 咨询类保留更少 |
| **质量过滤阈值** | 0.3 | 0.3 | 相同 |
| **最终 top_k** | 15 | 12 | 咨询类保留更多 |

**设计理由**：
- 咨询类需要覆盖多个方面，因此更重视多样性
- 行为判断类需要精确匹配，因此更重视相关性
- 咨询类的轮间去重避免了多轮检索的重复

### 去重效果总结

**整体去重率**：
- 轮内去重：~45%
- 轮间去重：~15%
- **总去重率**：~60%

**质量提升**：
- 去除了大量重复内容
- 保留了高质量、多样化的片段
- 提升了检索结果的实用性

**性能影响**：
- 去重开销：~50ms
- 对整体响应时间影响：< 5%
- 性价比高

---

## 总结

学术诚信助手工作流通过以下设计实现高质量问答：

1. **意图分流**：根据问题类型路由到不同的处理分支
2. **复杂度感知**：根据问题复杂度动态调整检索策略
3. **循环优化**：通过多轮检索和 LLM 增强持续提升质量
4. **多维评估**：采用多维度评分体系确保结果质量
5. **智能退出**：基于分数、轮次和收敛检测智能退出循环

相关文档：
- [配置说明](./configuration.md)
- [开发指南](./development.md)
- [查询示例](./examples.md)
- [技术架构](./architecture.md)
