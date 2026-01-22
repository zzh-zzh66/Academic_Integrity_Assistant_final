from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from utils.file.file import File


class GlobalState(BaseModel):
    """全局状态定义"""
    user_query: str = Field(default="", description="用户输入的查询问题")
    document_file: Optional[File] = Field(default=None, description="上传的学术文档文件")
    query_type: str = Field(default="", description="查询类型：query（查询）/upload（上传文档）")
    intent_type: str = Field(default="", description="识别到的意图类型：咨询类/行为判断类/混合类")
    extracted_keywords: List[str] = Field(default=[], description="提取的关键词")
    behavior_analysis: Optional[dict] = Field(default=None, description="行为分析结果（行为判断类使用）")
    retrieval_results: List[dict] = Field(default=[], description="知识库检索结果")
    document_import_result: dict = Field(default={}, description="文档导入结果")
    formatted_response: str = Field(default="", description="格式化后的响应内容")


class GraphInput(BaseModel):
    """工作流的输入"""
    user_query: str = Field(default="", description="用户输入的查询问题")
    document_file: Optional[File] = Field(default=None, description="上传的学术文档文件（可选）")


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


# ==================== 查询类型判断节点 ====================
class QueryTypeInput(BaseModel):
    """查询类型判断节点的输入"""
    user_query: str = Field(default="", description="用户输入的查询问题")
    document_file: Optional[File] = Field(default=None, description="上传的文档文件")


class QueryTypeOutput(BaseModel):
    """查询类型判断节点的输出"""
    query_type: str = Field(..., description="查询类型：query（查询）/upload（上传文档）")


# ==================== 文档导入节点 ====================
class DocumentImportInput(BaseModel):
    """文档导入节点的输入"""
    document_file: Optional[File] = Field(..., description="要导入的文档文件")


class DocumentImportOutput(BaseModel):
    """文档导入节点的输出"""
    import_success: bool = Field(..., description="是否导入成功")
    import_message: str = Field(..., description="导入结果消息")
    document_count: int = Field(default=0, description="导入的文档数量")


# ==================== 文档导入响应节点 ====================
class DocumentImportResponseInput(BaseModel):
    """文档导入响应节点的输入"""
    import_success: bool = Field(..., description="是否导入成功")
    import_message: str = Field(..., description="导入结果消息")
    document_count: int = Field(default=0, description="导入的文档数量")


class DocumentImportResponseOutput(BaseModel):
    """文档导入响应节点的输出"""
    formatted_response: str = Field(..., description="格式化后的响应内容")

