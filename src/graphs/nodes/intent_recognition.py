import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import (
    IntentRecognitionInput,
    IntentRecognitionOutput
)


def intent_recognition_node(
    state: IntentRecognitionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> IntentRecognitionOutput:
    """
    title: 意图识别
    desc: 识别用户输入的意图类型（咨询类/行为判断类/混合类），并提取关键词和行为分析信息
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

    # 渲染用户提示词
    user_prompt_content = up_tpl.render({"user_query": state.user_query})

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
            temperature=llm_config.get("temperature", 0.0),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 1500),
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

        # 解析响应（使用直接文本匹配，而不是JSON解析）
        intent_type = "咨询类"  # 默认值
        extracted_keywords = []
        behavior_analysis = None

        # 解析意图类型
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()

            # 解析意图类型
            if line.startswith("意图类型："):
                type_text = line.replace("意图类型：", "").strip()
                if "行为判断" in type_text or "判断" in type_text:
                    intent_type = "行为判断类"
                elif "混合" in type_text:
                    intent_type = "混合类"
                else:
                    intent_type = "咨询类"

            # 解析关键词
            elif line.startswith("关键词："):
                keywords_text = line.replace("关键词：", "").strip()
                if keywords_text:
                    # 按逗号分隔关键词
                    extracted_keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]

            # 解析行为分析
            elif line.startswith("主体："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["主体"] = line.replace("主体：", "").strip()
            elif line.startswith("动作："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["动作"] = line.replace("动作：", "").strip()
            elif line.startswith("对象："):
                if behavior_analysis is None:
                    behavior_analysis = {"主体": "", "动作": "", "对象": ""}
                behavior_analysis["对象"] = line.replace("对象：", "").strip()

        # 如果没有成功解析，使用关键词匹配进行辅助判断
        if intent_type == "咨询类" and len(extracted_keywords) == 0:
            query_lower = state.user_query.lower()
            if any(word in query_lower for word in ["是否", "违规", "合规", "允许", "可以吗", "违法", "违反"]):
                intent_type = "行为判断类"

        return IntentRecognitionOutput(
            intent_type=intent_type,
            extracted_keywords=extracted_keywords,
            behavior_analysis=behavior_analysis
        )

    except Exception as e:
        # 发生错误时返回默认值
        return IntentRecognitionOutput(
            intent_type="咨询类",
            extracted_keywords=[],
            behavior_analysis=None
        )
