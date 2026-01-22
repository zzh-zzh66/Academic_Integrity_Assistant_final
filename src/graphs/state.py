from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class GlobalState(BaseModel):
    """全局状态定义"""
    user_query: str = Field(..., description="用户输入的查询问题")
    intent_type: str = Field(default="", description="识别到的意图类型：咨询类/行为判断类/混合类")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果（行为判断类使用）")
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


# ==================== 知识库检索节点 ====================
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


class ResponseGenerationOutput(BaseModel):
    """响应生成节点的输出"""
    formatted_response: str = Field(..., description="格式化后的响应内容")
