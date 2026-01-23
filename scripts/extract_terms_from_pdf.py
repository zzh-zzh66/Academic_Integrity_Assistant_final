#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从科研诚信建设部分文件汇编.pdf 中提取专业术语
"""

import os
import sys
import json

# 添加项目路径到 PYTHONPATH
project_root = os.getenv("COZE_WORKSPACE_PATH", ".")
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from utils.file.file import File, FileOps
from coze_coding_dev_sdk import LLMClient

def extract_pdf_content():
    """提取 PDF 文件内容"""
    pdf_path = "assets/test/科研诚信建设部分文件汇编.pdf"
    
    print(f"正在读取文件: {pdf_path}")
    
    # 创建 File 对象
    pdf_file = File(url=pdf_path, file_type="document")
    
    # 提取文本内容
    content = FileOps.extract_text(pdf_file)
    
    print(f"文件内容长度: {len(content)} 字符")
    print("\n" + "="*80)
    print("文件内容前 500 字符:")
    print("="*80)
    print(content[:500])
    print("="*80 + "\n")
    
    return content

def analyze_terms_with_llm(content: str):
    """使用大模型分析文件，提取专业术语"""
    
    print("正在使用大模型分析文件内容，提取专业术语...")
    
    # 创建 LLM 客户端（不使用 Context）
    client = LLMClient()
    
    # 构建提示词
    system_prompt = """你是一位学术诚信领域的术语提取专家，擅长从政策文件中提取专业术语并构建术语映射表。

你的任务是：
1. 仔细阅读提供的科研诚信建设政策文件内容
2. 识别所有与学术诚信相关的专业术语
3. 为每个术语提取：定义、同义词、口语化表述、行为要素、相关术语
4. 返回结构化的术语映射表

术语映射表的格式要求：
{
  "术语名": {
    "standard_term": "标准术语",
    "definitions": ["定义1", "定义2"],
    "synonyms": ["同义词1", "同义词2"],
    "colloquial_terms": ["口语化表述1", "口语化表述2"],
    "action_elements": ["行为动作1", "行为动作2"],
    "object_elements": ["行为对象1", "行为对象2"],
    "related_terms": ["相关术语1", "相关术语2"]
  }
}

注意：
- standard_term: 政策文件中的标准术语名称
- definitions: 官方定义，可以有多条
- synonyms: 同义词或近义词（学术规范中的表述）
- colloquial_terms: 常见的口语化表述（用户可能使用的表达）
- action_elements: 该术语涉及的行为动作
- object_elements: 该术语涉及的行为对象
- related_terms: 相关的学术术语

请只返回 JSON 格式的术语映射表，不要包含任何其他说明文字。
"""

    user_prompt = f"""请分析以下科研诚信建设政策文件内容，提取所有专业术语并构建术语映射表。

文件内容（前 5000 字）：
{content[:5000]}

文件内容（5000-10000 字）：
{content[5000:10000] if len(content) > 5000 else ""}

文件内容（10000-15000 字）：
{content[10000:15000] if len(content) > 10000 else ""}

请仔细分析文件内容，提取所有与学术诚信相关的专业术语，包括但不限于：
- 学术不端行为类型（抄袭、剽窃、伪造、篡改等）
- 处分和处罚相关术语
- 调查和认定相关术语
- 责任主体相关术语
- 档案记录相关术语
等等。

返回完整的 JSON 格式术语映射表。"""

    # 调用大模型
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    response = client.invoke(
        messages=messages,
        model="doubao-seed-1-8-251228",
        temperature=0.1,
        top_p=0.9,
        max_completion_tokens=8000,
        thinking="disabled"
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
    
    print("\n" + "="*80)
    print("大模型返回的内容（前 1000 字符）:")
    print("="*80)
    print(response_text[:1000])
    print("="*80 + "\n")
    
    # 解析 JSON
    try:
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            term_mapping = json.loads(json_str)
            print(f"成功解析术语映射表，共提取 {len(term_mapping)} 个术语")
            return term_mapping
        else:
            print("警告：无法在响应中找到有效的 JSON 格式")
            return None
    except Exception as e:
        print(f"错误：解析 JSON 失败: {e}")
        return None

def save_term_mapping(term_mapping: dict):
    """保存术语映射表到文件"""
    output_path = "config/academic_integrity_term_mapping.json"
    
    print(f"\n正在保存术语映射表到: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(term_mapping, f, ensure_ascii=False, indent=2)
    
    print(f"术语映射表已成功保存！共 {len(term_mapping)} 个术语")

def main():
    """主函数"""
    print("="*80)
    print("科研诚信建设专业术语映射表生成工具")
    print("="*80 + "\n")
    
    # 第一步：提取 PDF 内容
    content = extract_pdf_content()
    
    if not content or len(content) < 100:
        print("错误：无法读取 PDF 文件内容或内容过短")
        return
    
    # 第二步：使用大模型分析术语
    term_mapping = analyze_terms_with_llm(content)
    
    if not term_mapping:
        print("错误：无法从大模型响应中提取术语映射表")
        return
    
    # 第三步：保存术语映射表
    save_term_mapping(term_mapping)
    
    print("\n" + "="*80)
    print("术语映射表生成完成！")
    print("="*80)

if __name__ == "__main__":
    main()
