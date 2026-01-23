from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class GlobalState(BaseModel):
    """全局状态定义"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(default="", description="识别到的意图类型：咨询类/行为判断类/混合类")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    
    # 查询复杂度和检索策略（新增）
    query_complexity: str = Field(default="standard", description="查询复杂度：simple/standard/complex")
    retrieval_strategy: dict = Field(default={}, description="检索策略配置（由查询优化节点设置）")
    
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果（行为判断类使用）")
    can_judge: Optional[bool] = Field(default=True, description="是否能够判断（行为判断类使用）")

    # 术语预处理节点输出字段
    standard_terms: List[str] = Field(default=[], description="识别到的标准化术语列表")
    expanded_terms: List[str] = Field(default=[], description="关联拓展后的术语列表")
    action_elements: List[str] = Field(default=[], description="提取的行为要素")
    object_elements: List[str] = Field(default=[], description="提取的对象要素")
    enhanced_query: str = Field(default="", description="语义增强后的查询字符串")
    term_confidence: float = Field(default=0.0, description="术语识别置信度 (0-1)")

    # 意图处理节点输出字段
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点（咨询类使用）")
    behavior_subject: str = Field(default="", description="行为主体（行为判断类使用）")
    behavior_action: str = Field(default="", description="行为动作（行为判断类使用）")
    behavior_object: str = Field(default="", description="涉及对象（行为判断类使用）")
    needs_clarification: bool = Field(default=False, description="是否需要补充提问（行为判断类使用）")
    clarification_questions: List[str] = Field(default=[], description="需要补充的问题列表（行为判断类使用）")
    consult_query: str = Field(default="", description="咨询部分的查询语句（混合类使用）")
    consult_keywords: List[str] = Field(default=[], description="咨询部分的关键词（混合类使用）")
    judge_query: str = Field(default="", description="判断部分的查询语句（混合类使用）")
    judge_keywords: List[str] = Field(default=[], description="判断部分的关键词（混合类使用）")

    # 后续节点输出字段
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果")
    formatted_response: str = Field(default="", description="格式化后的响应内容")


class GraphInput(BaseModel):
    """工作流的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")


class GraphOutput(BaseModel):
    """工作流的输出"""
    formatted_response: str = Field(..., description="格式化后的响应内容")


# ==================== 意图识别节点 ====================
class IntentRecognitionInput(BaseModel):
    """意图识别节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")


class IntentRecognitionOutput(BaseModel):
    """意图识别节点的输出"""
    intent_type: str = Field(..., description="识别到的意图类型：咨询类/行为判断类/混合类")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果（行为判断类或混合类使用）")


# ==================== 术语预处理节点 ====================
class TermPreprocessingInput(BaseModel):
    """术语预处理节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(default="", description="识别到的意图类型")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")


class TermPreprocessingOutput(BaseModel):
    """术语预处理节点的输出"""
    standard_terms: List[str] = Field(..., description="识别到的标准化术语列表")
    expanded_terms: List[str] = Field(..., description="关联拓展后的术语列表")
    action_elements: List[str] = Field(default=[], description="提取的行为要素")
    object_elements: List[str] = Field(default=[], description="提取的对象要素")
    enhanced_query: str = Field(..., description="语义增强后的查询字符串")
    term_confidence: float = Field(..., description="术语识别置信度 (0-1)")


# ==================== 咨询类知识库检索节点 ====================
class ConsultRetrievalInput(BaseModel):
    """咨询类知识库检索节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点")


class ConsultRetrievalOutput(BaseModel):
    """咨询类知识库检索节点的输出"""
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果（咨询类）")


# ==================== 行为判断类知识库检索节点 ====================
class JudgeRetrievalInput(BaseModel):
    """行为判断类知识库检索节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    behavior_subject: str = Field(default="", description="行为主体")
    behavior_action: str = Field(default="", description="行为动作")
    behavior_object: str = Field(default="", description="涉及对象")


class JudgeRetrievalOutput(BaseModel):
    """行为判断类知识库检索节点的输出"""
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果（行为判断类）")
    can_judge: bool = Field(default=True, description="是否能够判断（高分>=0.65时为True）")


# ==================== 混合类知识库检索节点 ====================
class MixedRetrievalInput(BaseModel):
    """混合类知识库检索节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")
    consult_query: str = Field(default="", description="咨询部分的查询语句")
    consult_keywords: List[str] = Field(default=[], description="咨询部分的关键词")
    consult_focus: str = Field(default="", description="咨询焦点")
    judge_query: str = Field(default="", description="判断部分的查询语句")
    judge_keywords: List[str] = Field(default=[], description="判断部分的关键词")
    behavior_subject: str = Field(default="", description="行为主体")
    behavior_action: str = Field(default="", description="行为动作")
    behavior_object: str = Field(default="", description="涉及对象")


class MixedRetrievalOutput(BaseModel):
    """混合类知识库检索节点的输出"""
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果（混合类）")


# ==================== 知识库检索节点（保留兼容） ====================
class KnowledgeRetrievalInput(BaseModel):
    """知识库检索节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(..., description="识别到的意图类型")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")


class KnowledgeRetrievalOutput(BaseModel):
    """知识库检索节点的输出"""
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果，包含相关规范内容")


# ==================== 响应生成节点 ====================
class ResponseGenerationInput(BaseModel):
    """响应生成节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(..., description="识别到的意图类型")
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")
    can_judge: Optional[bool] = Field(default=True, description="是否能够判断（仅行为判断类）")


class ResponseGenerationOutput(BaseModel):
    """响应生成节点的输出"""
    formatted_response: str = Field(..., description="格式化后的响应内容")


# ==================== 意图处理节点 ====================
class ConsultProcessInput(BaseModel):
    """咨询类意图处理节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    # 术语预处理节点输出字段
    standard_terms: List[str] = Field(default=[], description="识别到的标准化术语列表")
    expanded_terms: List[str] = Field(default=[], description="关联拓展后的术语列表")
    action_elements: List[str] = Field(default=[], description="提取的行为要素")
    object_elements: List[str] = Field(default=[], description="提取的对象要素")
    enhanced_query: str = Field(default="", description="语义增强后的查询字符串")
    term_confidence: float = Field(default=0.0, description="术语识别置信度 (0-1)")


class ConsultProcessOutput(BaseModel):
    """咨询类意图处理节点的输出"""
    refined_query: str = Field(..., description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(..., description="咨询焦点：定义/类型/要求/规范等")


class JudgeProcessInput(BaseModel):
    """行为判断类意图处理节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")
    # 术语预处理节点输出字段
    standard_terms: List[str] = Field(default=[], description="识别到的标准化术语列表")
    expanded_terms: List[str] = Field(default=[], description="关联拓展后的术语列表")
    action_elements: List[str] = Field(default=[], description="提取的行为要素")
    object_elements: List[str] = Field(default=[], description="提取的对象要素")
    enhanced_query: str = Field(default="", description="语义增强后的查询字符串")
    term_confidence: float = Field(default=0.0, description="术语识别置信度 (0-1)")


class JudgeProcessOutput(BaseModel):
    """行为判断类意图处理节点的输出"""
    refined_query: str = Field(..., description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    behavior_subject: str = Field(..., description="行为主体")
    behavior_action: str = Field(..., description="行为动作")
    behavior_object: str = Field(..., description="涉及对象")
    needs_clarification: bool = Field(default=False, description="是否需要补充提问")
    clarification_questions: List[str] = Field(default=[], description="需要补充的问题列表")


class MixedProcessInput(BaseModel):
    """混合类意图处理节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果")
    # 术语预处理节点输出字段
    standard_terms: List[str] = Field(default=[], description="识别到的标准化术语列表")
    expanded_terms: List[str] = Field(default=[], description="关联拓展后的术语列表")
    action_elements: List[str] = Field(default=[], description="提取的行为要素")
    object_elements: List[str] = Field(default=[], description="提取的对象要素")
    enhanced_query: str = Field(default="", description="语义增强后的查询字符串")
    term_confidence: float = Field(default=0.0, description="术语识别置信度 (0-1)")


class MixedProcessOutput(BaseModel):
    """混合类意图处理节点的输出"""
    consult_query: str = Field(..., description="咨询部分的查询语句")
    consult_keywords: List[str] = Field(default=[], description="咨询部分的关键词")
    consult_focus: str = Field(..., description="咨询焦点")
    judge_query: str = Field(..., description="判断部分的查询语句")
    judge_keywords: List[str] = Field(default=[], description="判断部分的关键词")
    behavior_subject: str = Field(..., description="行为主体")
    behavior_action: str = Field(..., description="行为动作")
    behavior_object: str = Field(..., description="涉及对象")


# ==================== 咨询类扩展节点 ====================
class ConsultContextExpandInput(BaseModel):
    """咨询类扩展节点的输入"""
    retrieval_results: List[dict] = Field(..., description="知识库检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class ConsultContextExpandOutput(BaseModel):
    """咨询类扩展节点的输出"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果（500-800字）")


# ==================== 咨询类重排序节点 ====================
class ConsultRerankInput(BaseModel):
    """咨询类重排序节点的输入"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class ConsultRerankOutput(BaseModel):
    """咨询类重排序节点的输出"""
    retrieval_results: List[dict] = Field(..., description="重排序后的检索结果（top 5）")


# ==================== 行为判断类扩展节点 ====================
class JudgeContextExpandInput(BaseModel):
    """行为判断类扩展节点的输入"""
    retrieval_results: List[dict] = Field(..., description="知识库检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class JudgeContextExpandOutput(BaseModel):
    """行为判断类扩展节点的输出"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果（300-500字）")


# ==================== 行为判断类重排序节点 ====================
class JudgeRerankInput(BaseModel):
    """行为判断类重排序节点的输入"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class JudgeRerankOutput(BaseModel):
    """行为判断类重排序节点的输出"""
    retrieval_results: List[dict] = Field(..., description="重排序后的检索结果（top 3）")
    can_judge: bool = Field(default=True, description="是否能够判断")


# ==================== 混合类扩展节点 ====================
class MixedContextExpandInput(BaseModel):
    """混合类扩展节点的输入"""
    retrieval_results: List[dict] = Field(..., description="知识库检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class MixedContextExpandOutput(BaseModel):
    """混合类扩展节点的输出"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果（咨询500-800字，判断300-500字）")


# ==================== 混合类重排序节点 ====================
class MixedRerankInput(BaseModel):
    """混合类重排序节点的输入"""
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果")
    user_query: str = Field(..., description="用户输入的查询问题")


class MixedRerankOutput(BaseModel):
    """混合类重排序节点的输出"""
    retrieval_results: List[dict] = Field(..., description="重排序后的检索结果（top 5）")


# ==================== 咨询类循环检索 ====================
class ConsultRetrievalLoopState(BaseModel):
    """咨询类循环检索状态（优化版）"""
    
    # 固定输入（每轮保持不变）
    user_query: str = Field(default="", description="用户原始问题")
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点")
    
    # 新增：接收父图的检索策略和复杂度
    retrieval_strategy: dict = Field(default={}, description="检索策略配置")
    query_complexity: str = Field(default="standard", description="查询复杂度")

    # 循环控制参数
    max_rounds: int = Field(default=2, description="最大循环轮次")
    target_score: float = Field(default=0.8, description="目标分数（达到即退出）")
    min_score_threshold: float = Field(default=0.65, description="最低阈值（达到最大轮次后判断）")
    
    # 新增：从retrieval_strategy中提取的动态参数
    top_k_first_round: int = Field(default=15, description="第一轮检索数量")
    top_k_second_round: int = Field(default=10, description="第二轮检索数量")
    top_k_third_round: int = Field(default=8, description="第三轮检索数量")
    min_score_first_round: float = Field(default=0.3, description="第一轮最低分数")
    min_score_second_round: float = Field(default=0.6, description="第二轮最低分数")
    min_score_third_round: float = Field(default=0.7, description="第三轮最低分数")

    # 循环状态（每轮更新）
    current_round: int = Field(default=0, description="当前轮次")
    previous_score: float = Field(default=0.0, description="上一轮分数")
    previous_prev_score: float = Field(default=0.0, description="上两轮分数")
    current_score: float = Field(default=0.0, description="当前分数（加权求和）")
    score_history: List[float] = Field(default=[], description="历史分数列表")
    retrieval_results: List[dict] = Field(default=[], description="当前轮的检索结果")
    
    # 新增：rerank节点输出
    ranked_results: List[dict] = Field(default=[], description="排序后的结果")
    top_score: float = Field(default=0.0, description="最高分")
    top_3_avg: float = Field(default=0.0, description="top-3平均分")
    average_confidence: float = Field(default=0.0, description="平均置信度")
    
    # 新增：结构化上下文
    structured_context: dict = Field(default={}, description="结构化上下文")
    key_concepts: List[str] = Field(default=[], description="关键概念")
    relation_map: dict = Field(default={}, description="关系映射")
    missing_aspects: List[str] = Field(default=[], description="缺失方面")
    context_summary: str = Field(default="", description="上下文摘要")
    
    # 新增：改善分析输出
    improvement_potential: str = Field(default="", description="改善潜力")
    predicted_next_score: float = Field(default=0.0, description="预测下一轮分数")
    score_change_analysis: dict = Field(default={}, description="分数变化分析")
    recommendation: str = Field(default="", description="检索建议")
    
    # 新增：历史上下文
    previous_context: dict = Field(default={}, description="上一轮结构化上下文")
    
    high_score_chunks: List[str] = Field(default=[], description="top-3高分内容（用于下一轮上下文）")
    should_continue: bool = Field(default=True, description="是否继续循环")
    exit_reason: str = Field(default="", description="退出原因：success/target_score_reached/score_decreased/max_rounds_reached/fallback")
    previous_retrieval_results: List[dict] = Field(default=[], description="上一轮的检索结果（用于分数下降时回退）")
    consecutive_declines: int = Field(default=0, description="连续下降次数")
    start_time: float = Field(default=0.0, description="开始时间戳")


class ConsultRetrievalLoopStartInput(BaseModel):
    """咨询类循环检索入口节点的输入"""
    user_query: str = Field(..., description="用户原始问题")
    refined_query: str = Field(..., description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点")


class ConsultRetrievalLoopStartOutput(BaseModel):
    """咨询类循环检索入口节点的输出"""
    loop_state: ConsultRetrievalLoopState = Field(..., description="初始化的循环状态")


class ConsultRetrievalLoopEndInput(BaseModel):
    """咨询类循环检索出口节点的输入"""
    loop_state: ConsultRetrievalLoopState = Field(..., description="循环检索的最终状态")


class ConsultRetrievalLoopEndOutput(BaseModel):
    """咨询类循环检索出口节点的输出"""
    retrieval_results: List[dict] = Field(default=[], description="最终检索结果")
    is_fallback: bool = Field(default=False, description="是否使用兜底回答")
    fallback_message: str = Field(default="", description="兜底回答消息（仅is_fallback=True时）")


# ==================== 查询复杂度判断节点 ====================
class ComplexityInput(BaseModel):
    """查询复杂度判断节点的输入"""
    user_query: str = Field(..., description="用户输入的查询问题")


class ComplexityOutput(BaseModel):
    """查询复杂度判断节点的输出"""
    query_complexity: str = Field(..., description="查询复杂度：simple/standard/complex")
    complexity_reason: str = Field(..., description="复杂度判断理由")


# ==================== 咨询查询优化节点 ====================
class ConsultQueryOptimizeInput(BaseModel):
    """咨询查询优化节点的输入"""
    user_query: str = Field(..., description="用户原始问题")
    query_complexity: str = Field(..., description="查询复杂度")
    refined_query: str = Field(default="", description="优化后的查询语句")
    refined_keywords: List[str] = Field(default=[], description="优化后的关键词列表")
    consult_focus: str = Field(default="", description="咨询焦点")
    standard_terms: List[str] = Field(default=[], description="标准化术语")
    expanded_terms: List[str] = Field(default=[], description="扩展术语")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词（从GlobalState中获取）")


class ConsultQueryOptimizeOutput(BaseModel):
    """咨询查询优化节点的输出"""
    optimized_query: str = Field(..., description="优化后的查询语句")
    optimized_keywords: List[str] = Field(..., description="优化后的关键词")
    retrieval_strategy: dict = Field(..., description="检索策略配置")
    optimization_reason: str = Field(..., description="优化理由")


# ==================== 重排序节点（咨询类） ====================
class RerankInput(BaseModel):
    """重排序节点的输入"""
    user_query: str = Field(..., description="用户查询")
    expanded_results: List[dict] = Field(..., description="扩展后的检索结果")


class RerankOutput(BaseModel):
    """重排序节点的输出"""
    ranked_results: List[dict] = Field(..., description="排序后的结果")
    weighted_score: float = Field(..., description="加权平均分")
    top_score: float = Field(..., description="最高分")
    top_3_avg: float = Field(..., description="top-3平均分")
    average_confidence: float = Field(..., description="平均置信度")


# ==================== 上下文提取节点 ====================
class ContextExtractInput(BaseModel):
    """上下文提取节点的输入"""
    user_query: str = Field(..., description="用户查询")
    top_3_results: List[dict] = Field(..., description="top-3检索结果")


class ContextExtractOutput(BaseModel):
    """上下文提取节点的输出"""
    key_concepts: List[str] = Field(..., description="关键概念")
    relation_map: dict = Field(..., description="关系映射")
    missing_aspects: List[str] = Field(..., description="缺失方面")
    summary: str = Field(..., description="摘要")


# ==================== 改善分析节点 ====================
class ImprovementAnalysisInput(BaseModel):
    """改善分析节点的输入"""
    user_query: str = Field(..., description="用户查询")
    current_round: int = Field(..., description="当前轮次")
    previous_prev_score: float = Field(default=0.0, description="上两轮分数")
    previous_score: float = Field(default=0.0, description="上一轮分数")
    current_score: float = Field(..., description="当前分数")
    current_retrieval_results: List[dict] = Field(..., description="当前检索结果")
    structured_context: dict = Field(default={}, description="当前结构化上下文")
    previous_context: dict = Field(default={}, description="上一轮结构化上下文")


class ImprovementAnalysisOutput(BaseModel):
    """改善分析节点的输出"""
    improvement_potential: str = Field(..., description="改善潜力")
    predicted_next_score: float = Field(..., description="预测下一轮分数")
    score_change_analysis: dict = Field(..., description="分数变化分析")
    recommendation: str = Field(..., description="检索建议")
    recommendation_reason: str = Field(..., description="建议理由")


# ==================== 循环内部节点 ====================
class ConsultRetrievalLoopNodeInput(BaseModel):
    """循环检索内部节点的输入"""
    loop_state: ConsultRetrievalLoopState = Field(..., description="当前循环状态")


class ConsultRetrievalLoopNodeOutput(BaseModel):
    """循环检索内部节点的输出"""
    loop_state: ConsultRetrievalLoopState = Field(..., description="更新后的循环状态")

