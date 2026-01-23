from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class GlobalState(BaseModel):
    """全局状态定义"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(default="", description="识别到的意图类型：咨询类/行为判断类/混合类")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果（行为判断类使用）")
    can_judge: Optional[bool] = Field(default=True, description="是否能够判断（行为判断类使用）")
    
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

