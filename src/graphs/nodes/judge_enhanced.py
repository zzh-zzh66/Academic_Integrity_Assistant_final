"""
行为判断类增强检索节点
支持2轮循环检索、拓宽上下文、置信度评估
"""

import os
import json
import re
import logging
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient

from graphs.state import (
    JudgeRetrievalEnhancedInput,
    JudgeRetrievalEnhancedOutput,
    JudgeContextExpandEnhancedInput,
    JudgeContextExpandEnhancedOutput,
    JudgeDecisionInput,
    JudgeDecisionOutput
)
from graphs.nodes.common import extract_file_name_from_content, expand_content_around_chunk

# 配置日志
logger = logging.getLogger("judge_enhanced")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler("/app/work/logs/bypass/app.log")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==================== 行为判断类增强检索节点 ====================

def judge_retrieval_enhanced_node(
    state: JudgeRetrievalEnhancedInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeRetrievalEnhancedOutput:
    """
    title: 行为判断类增强检索
    desc: 执行2轮循环检索，扩大检索范围，获取更多规则片段
    integrations: 知识库, 大语言模型（重排序）
    """
    ctx = runtime.context
    
    logger.info("=== 行为判断类增强检索开始 ===")
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"优化查询: {state.optimized_query}")
    logger.info(f"查询复杂度: {state.query_complexity}")
    logger.info(f"检索策略: {state.retrieval_strategy}")
    
    try:
        client = KnowledgeClient(ctx=ctx)
        
        # 从检索策略中获取参数
        retrieval_strategy = state.retrieval_strategy
        
        # 第1轮：扩大检索
        top_k_first = retrieval_strategy.get("top_k_first_round", 20)
        min_score_first = retrieval_strategy.get("min_score_first_round", 0.3)
        
        query_first = state.optimized_query if state.optimized_query else state.user_query
        
        # 添加行为分析信息
        if state.behavior_subject or state.behavior_action or state.behavior_object:
            behavior_parts = []
            if state.behavior_subject:
                behavior_parts.append(f"主体:{state.behavior_subject}")
            if state.behavior_action:
                behavior_parts.append(f"动作:{state.behavior_action}")
            if state.behavior_object:
                behavior_parts.append(f"对象:{state.behavior_object}")
            query_first = f"{query_first} {' '.join(behavior_parts)}"
        
        # 添加关键词
        if state.optimized_keywords:
            keywords_str = " ".join(state.optimized_keywords)
            query_first = f"{query_first} {keywords_str}"
        
        logger.info(f"第1轮检索: top_k={top_k_first}, min_score={min_score_first}")
        logger.info(f"查询语句: {query_first}")
        
        response_first = client.search(query=query_first, top_k=top_k_first, min_score=min_score_first)
        
        # 处理第1轮结果
        first_round_results = []
        if response_first.code == 0 and response_first.chunks:
            for chunk in response_first.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                first_round_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        logger.info(f"第1轮检索结果: {len(first_round_results)}个片段")
        
        # 第2轮：精准检索
        top_k_second = retrieval_strategy.get("top_k_second_round", 15)
        min_score_second = retrieval_strategy.get("min_score_second_round", 0.5)
        
        # 构建第2轮查询（基于第1轮的高分结果）
        if first_round_results:
            top_3_contents = [r["content"][:200] for r in first_round_results[:3]]
            query_second = f"{query_first} 相关规则 禁止 要求"
            logger.info(f"第2轮检索: top_k={top_k_second}, min_score={min_score_second}")
        else:
            query_second = query_first
            logger.info(f"第1轮无结果，使用相同查询进行第2轮")
        
        response_second = client.search(query=query_second, top_k=top_k_second, min_score=min_score_second)
        
        # 处理第2轮结果
        second_round_results = []
        if response_second.code == 0 and response_second.chunks:
            for chunk in response_second.chunks:
                file_name = extract_file_name_from_content(chunk.content)
                second_round_results.append({
                    "content": chunk.content,
                    "score": chunk.score,
                    "doc_id": chunk.doc_id,
                    "file_name": file_name
                })
        
        logger.info(f"第2轮检索结果: {len(second_round_results)}个片段")
        
        # 合并两轮结果，去重（按doc_id）
        all_results_dict = {}
        for result in first_round_results + second_round_results:
            doc_id = result["doc_id"]
            if doc_id not in all_results_dict:
                all_results_dict[doc_id] = result
            else:
                # 保留分数更高的结果
                if result["score"] > all_results_dict[doc_id]["score"]:
                    all_results_dict[doc_id] = result
        
        # 按分数排序，取top-10
        ranked_results = sorted(all_results_dict.values(), key=lambda x: x["score"], reverse=True)[:10]
        
        logger.info(f"=== 最终结果 ===")
        logger.info(f"结果数量: {len(ranked_results)}")
        if ranked_results:
            logger.info(f"最高分: {ranked_results[0]['score']:.4f}")
            logger.info(f"最低分: {ranked_results[-1]['score']:.4f}")
        
        return JudgeRetrievalEnhancedOutput(retrieval_results=ranked_results)
        
    except Exception as e:
        logger.error(f"增强检索发生异常: {str(e)}", exc_info=True)
        return JudgeRetrievalEnhancedOutput(retrieval_results=[])


# ==================== 行为判断类拓宽上下文节点 ====================

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

def judge_decision_node(
    state: JudgeDecisionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JudgeDecisionOutput:
    """
    title: 行为判断类违规判断
    desc: 基于拓宽的上下文判断是否违规，并评估置信度
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_tpl = Template(_cfg.get("up", ""))
    
    logger.info("=== 行为判断类违规判断开始 ===")
    logger.info(f"用户查询: {state.user_query}")
    logger.info(f"完整段落数: {len(state.full_context_paragraphs)}")
    
    # 渲染用户提示词
    user_prompt_content = up_tpl.render({
        "user_query": state.user_query,
        "full_context_paragraphs": state.full_context_paragraphs,
        "related_rules": state.related_rules,
        "decision_basis": state.decision_basis,
        "behavior_subject": state.behavior_subject,
        "behavior_action": state.behavior_action,
        "behavior_object": state.behavior_object
    })
    
    # 调用大语言模型
    client = LLMClient(ctx=ctx)
    
    messages = [
        {"role": "system", "content": sp},
        {"role": "user", "content": user_prompt_content}
    ]
    
    try:
        response = client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-1-8-251228"),
            temperature=llm_config.get("temperature", 0.1),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
            thinking=llm_config.get("thinking", "disabled")
        )
        
        # 提取响应内容
        response_text = ""
        if isinstance(response.content, str):
            response_text = response.content
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    response_text += item.get("text", "")
                elif isinstance(item, str):
                    response_text += item
        
        response_text = response_text.strip()
        
        # 解析JSON响应
        result = {
            "can_judge": True,
            "is_violation": False,
            "judgment_basis": state.decision_basis,
            "relevant_rules": state.related_rules,
            "confidence_score": 0.7,
            "confidence_level": "medium",
            "needs_clarification": False,
            "clarification_questions": [],
            "missing_information": [],
            "ambiguity_reasons": [],
            "suggested_actions": [],
            "warning_notes": []
        }
        
        # 尝试提取JSON内容
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                if "can_judge" in parsed_result:
                    result["can_judge"] = parsed_result["can_judge"]
                if "is_violation" in parsed_result:
                    result["is_violation"] = parsed_result["is_violation"]
                if "judgment_basis" in parsed_result:
                    result["judgment_basis"] = parsed_result["judgment_basis"]
                if "relevant_rules" in parsed_result:
                    result["relevant_rules"] = parsed_result["relevant_rules"]
                if "confidence_score" in parsed_result:
                    result["confidence_score"] = parsed_result["confidence_score"]
                if "confidence_level" in parsed_result:
                    result["confidence_level"] = parsed_result["confidence_level"]
                if "needs_clarification" in parsed_result:
                    result["needs_clarification"] = parsed_result["needs_clarification"]
                if "clarification_questions" in parsed_result:
                    result["clarification_questions"] = parsed_result["clarification_questions"]
                if "missing_information" in parsed_result:
                    result["missing_information"] = parsed_result["missing_information"]
                if "ambiguity_reasons" in parsed_result:
                    result["ambiguity_reasons"] = parsed_result["ambiguity_reasons"]
                if "suggested_actions" in parsed_result:
                    result["suggested_actions"] = parsed_result["suggested_actions"]
                if "warning_notes" in parsed_result:
                    result["warning_notes"] = parsed_result["warning_notes"]
            except json.JSONDecodeError:
                pass
        
        logger.info(f"判断结果: can_judge={result['can_judge']}, is_violation={result.get('is_violation', None)}")
        logger.info(f"置信度: {result['confidence_score']:.2f} ({result['confidence_level']})")
        
        return JudgeDecisionOutput(**result)
        
    except Exception as e:
        logger.error(f"违规判断发生异常: {str(e)}", exc_info=True)
        return JudgeDecisionOutput(
            can_judge=False,
            is_violation=None,
            judgment_basis="处理异常，无法进行判断",
            relevant_rules=[],
            confidence_score=0.0,
            confidence_level="low",
            needs_clarification=False,
            clarification_questions=[],
            missing_information=[],
            ambiguity_reasons=[],
            suggested_actions=[],
            warning_notes=[]
        )
