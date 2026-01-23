# 工作流详细说明

本文档详细说明学术诚信助手工作流的整体流程和各分支实现细节。

## 目录

- [主图流程](#主图流程)
- [咨询类分支](#咨询类分支)
- [行为判断类分支](#行为判断类分支)
- [混合类分支](#混合类分支)
- [循环检索子图](#循环检索子图)

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
    
    ConsultLoop -->|retrieval_results| Response[response_generation_node<br/>响应生成]
    
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

---

## 行为判断类分支

行为判断类分支用于判断特定行为是否符合学术规范：

```mermaid
graph TD
    Input[用户查询] --> Intent[intent_recognition_node<br/>意图识别]
    Intent --> Term[term_preprocessing_node<br/>术语预处理]
    Term --> JudgeProcess[judge_process_node<br/>行为判断类处理]
    
    JudgeProcess -->|enhanced_query<br/>behavior_elements| JudgeRetrieval[judge_retrieval_node<br/>知识库检索]
    
    JudgeRetrieval --> JudgeExpand[judge_context_expand_node<br/>上下文扩展]
    JudgeExpand --> JudgeRerank[judge_rerank_node<br/>重排序]
    
    JudgeRerank --> Confidence[confidence_evaluation_node<br/>置信度评估]
    
    Confidence --> Response[response_generation_node<br/>响应生成]
    
    Response --> Output[格式化响应]
    
    style JudgeRetrieval fill:#e1f5ff
    style JudgeExpand fill:#fff4e1
    style JudgeRerank fill:#f3e5f5
    style Confidence fill:#fce4ec
    style Response fill:#e8f5e9
```

### 关键节点说明

#### 1. judge_process_node（行为判断处理）

**输入**：
- `refined_query`：优化后的查询
- `refined_keywords`：提取的关键词
- `behavior_elements`：提取的行为要素（行为类型、对象、条件）

**输出**：
- `enhanced_query`：增强的查询
- `behavior_elements`：结构化的行为要素

**作用**：提取行为要素，构建增强检索查询

#### 2. judge_retrieval_node（知识库检索）

**输入**：
- `user_query`：用户原始查询
- `enhanced_query`：增强的查询
- `behavior_elements`：行为要素

**输出**：
- `retrieval_results`：检索结果片段

**作用**：检索相关知识库内容（15-25个片段）

#### 3. judge_context_expand_node（上下文扩展）

**输入**：
- `retrieval_results`：检索结果片段

**输出**：
- `expanded_context`：扩展后的上下文（3-10个完整段落）

**作用**：将检索片段扩展为完整段落，拓宽上下文

#### 4. judge_rerank_node（重排序）

**输入**：
- `expanded_context`：扩展的上下文
- `user_query`：用户查询
- `behavior_elements`：行为要素

**输出**：
- `ranked_results`：排序后的结果
- `relevance_scores`：相关性分数

**作用**：基于相关性、权威性、完整性进行重排序

#### 5. confidence_evaluation_node（置信度评估）

**输入**：
- `ranked_results`：排序后的结果
- `behavior_elements`：行为要素

**输出**：
- `confidence_score`：置信度分数（0-1）
- `judgment_result`：判断结果（合规/不合规/不确定）
- `supporting_evidence`：支持证据

**作用**：评估判断结果的置信度，提供证据支持

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
