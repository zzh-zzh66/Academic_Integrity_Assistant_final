import os
import json
import logging
from typing import List, Dict, Set
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


# ==================== 段落去重工具函数 ====================

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的Jaccard相似度
    
    Args:
        text1: 文本1
        text2: 文本2
    
    Returns:
        Jaccard相似度（0-1之间）
    """
    # 将文本分词（按空格和标点符号）
    set1 = set(text1.split())
    set2 = set(text2.split())
    
    # 计算交集和并集
    intersection = set1 & set2
    union = set1 | set2
    
    # 避免除以0
    if len(union) == 0:
        return 0.0
    
    return len(intersection) / len(union)


def deduplicate_paragraphs_by_doc(
    paragraphs: List[Dict],
    similarity_threshold: float = 0.75
) -> List[Dict]:
    """
    按文档ID分组进行段落级别去重
    
    Args:
        paragraphs: 段落列表，每个元素包含content、doc_id、score等字段
        similarity_threshold: 相似度阈值，高于此值视为重复
    
    Returns:
        去重后的段落列表
    """
    if not paragraphs:
        return []
    
    # 按doc_id分组
    doc_paragraphs: Dict[str, List[Dict]] = {}
    for para in paragraphs:
        doc_id = para.get("doc_id", "")
        if doc_id not in doc_paragraphs:
            doc_paragraphs[doc_id] = []
        doc_paragraphs[doc_id].append(para)
    
    # 对每个文档内部进行去重
    deduplicated_paragraphs = []
    for doc_id, doc_para_list in doc_paragraphs.items():
        # 按分数降序排序
        sorted_para_list = sorted(
            doc_para_list,
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        # 贪心去重：保留最高分段落，去除与其相似的段落
        selected_paras = []
        for para in sorted_para_list:
            is_duplicate = False
            for selected in selected_paras:
                similarity = calculate_jaccard_similarity(
                    para["content"],
                    selected["content"]
                )
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    logger.info(f"  段落去重: doc_id={doc_id}, 相似度={similarity:.3f}, 跳过低分段落")
                    break
            
            if not is_duplicate:
                selected_paras.append(para)
        
        deduplicated_paragraphs.extend(selected_paras)
        logger.info(f"文档 {doc_id}: 原始{len(doc_para_list)}个段落 -> 去重后{len(selected_paras)}个段落")
    
    logger.info(f"段落去重完成: 总共{len(paragraphs)}个段落 -> 去重后{len(deduplicated_paragraphs)}个段落")
    return deduplicated_paragraphs

def judge_context_expand_enhanced_node(
    state: JudgeContextExpandEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeContextExpandEnhancedOutput:
    """
    title: 行为判断类拓宽上下文
    desc: 从检索结果中提取完整段落，理解规则全貌，并进行段落级别去重
    integrations: 知识库, 大语言模型
    """
    ctx = runtime.context
    
    logger.info("=== 行为判断类拓宽上下文开始 ===")
    logger.info(f"输入结果数: {len(state.retrieval_results)}")
    
    try:
        # 提取top-12结果的完整段落（对应MMR重排序后的12个结果）
        expanded_paragraphs = []
        related_rules = []
        
        for result in state.retrieval_results[:12]:
            original_content = result.get("content", "")
            doc_id = result.get("doc_id", "")
            score = result.get("score", 0)
            
            # 扩展内容到完整段落（300-500字）
            expanded_content = expand_content_around_chunk(original_content, target_length=400)
            
            expanded_paragraphs.append({
                "content": expanded_content,
                "doc_id": doc_id,
                "score": score
            })
            
            # 提取规则引用
            if "《" in expanded_content and "》" in expanded_content:
                import re as re_module
                rules = re_module.findall(r'《([^》]+)》', expanded_content)
                related_rules.extend(rules)
        
        logger.info(f"扩展完整段落: {len(expanded_paragraphs)}个")
        
        # 段落级别去重（按doc_id分组，Jaccard, threshold=0.75）
        logger.info("开始段落级别去重...")
        deduplicated_paragraphs = deduplicate_paragraphs_by_doc(
            expanded_paragraphs,
            similarity_threshold=0.75
        )
        
        # 提取去重后的段落内容和doc_id
        full_context_paragraphs = [p["content"] for p in deduplicated_paragraphs]
        
        # 去重规则引用
        related_rules = list(set(related_rules))
        
        # 生成判断依据摘要
        if full_context_paragraphs:
            decision_basis = f"基于检索到的{len(full_context_paragraphs)}个相关规范条款，对用户行为进行判断。"
        else:
            decision_basis = "未检索到相关规范内容，无法进行判断。"
        
        logger.info(f"最终段落: {len(full_context_paragraphs)}个")
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
