import os
import json
import logging
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

logger = logging.getLogger(__name__)

from graphs.state import (
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)
from graphs.nodes.common import (
    extract_file_name_from_content,
    expand_content_around_chunk,
    calculate_weighted_score,
    extract_top_k_chunks
)

def judge_context_expand_enhanced_node(
    state: JudgeContextExpandEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeContextExpandEnhancedOutput:
    """
    title: 行为判断类拓宽上下文
    desc: 从检索结果中提取完整段落，理解规则全貌
    integrations: 知识库, 大语言模型
    """
    ctx = runtime.context
    
    logger.info("=== 行为判断类拓宽上下文开始 ===")
    logger.info(f"输入结果数: {len(state.retrieval_results)}")
    
    try:
        # 提取top-5结果的完整段落
        full_context_paragraphs = []
        related_rules = []
        
        for result in state.retrieval_results[:5]:
            original_content = result.get("content", "")
            
            # 扩展内容到完整段落（300-500字）
            expanded_content = expand_content_around_chunk(original_content, target_length=400)
            full_context_paragraphs.append(expanded_content)
            
            # 提取规则引用
            if "《" in expanded_content and "》" in expanded_content:
                import re as re_module
                rules = re_module.findall(r'《([^》]+)》', expanded_content)
                related_rules.extend(rules)
        
        # 去重规则引用
        related_rules = list(set(related_rules))
        
        # 生成判断依据摘要
        if full_context_paragraphs:
            decision_basis = "基于检索到的相关规范条款，对用户行为进行判断。"
        else:
            decision_basis = "未检索到相关规范内容，无法进行判断。"
        
        logger.info(f"提取完整段落: {len(full_context_paragraphs)}个")
        logger.info(f"关联规则: {len(related_rules)}个")
        
        return JudgeContextExpandEnhancedOutput(
            full_context_paragraphs=full_context_paragraphs,
            related_rules=related_rules,
            decision_basis=decision_basis
        )
        
    except Exception as e:
        logger.error(f"拓宽上下文发生异常: {str(e)}", exc_info=True)
        return JudgeContextExpandEnhancedOutput(
            full_context_paragraphs=[],
            related_rules=[],
            decision_basis="处理异常，无法进行判断"
        )


# ==================== 行为判断类违规判断节点 ====================
