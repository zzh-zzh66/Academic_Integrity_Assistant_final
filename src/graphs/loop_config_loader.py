"""
循环检索配置加载器

实现高内聚低耦合的配置管理，支持：
- 按意图类型加载循环配置
- 节点级别的配置获取
- 单例模式确保配置一致性
"""

import json
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class LoopConfig(BaseModel):
    """循环配置（Pydantic模型）"""
    basic_params: Dict[str, Any] = Field(default_factory=dict, description="基础参数")
    context_management: Dict[str, Any] = Field(default_factory=dict, description="上下文管理")
    retrieval_params: Dict[str, Any] = Field(default_factory=dict, description="检索参数")
    early_exit: Dict[str, Any] = Field(default_factory=dict, description="提前退出")
    decline_tolerance: Dict[str, Any] = Field(default_factory=dict, description="下降容忍度")
    improvement_detection: Dict[str, Any] = Field(default_factory=dict, description="改善检测")
    llm_enhancement: Dict[str, Any] = Field(default_factory=dict, description="大模型增强")
    node_configs: Dict[str, Any] = Field(default_factory=dict, description="节点配置")


class LoopConfigLoader:
    """循环配置加载器（单例模式）"""
    
    _instance = None
    _configs: Dict[str, LoopConfig] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_config(self, intent_type: str) -> LoopConfig:
        """
        加载指定意图类型的循环配置
        
        Args:
            intent_type: 意图类型（consult/judge/mixed）
        
        Returns:
            LoopConfig对象
        """
        if intent_type in self._configs:
            return self._configs[intent_type]
        
        config_file = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH"),
            f"config/loop/{intent_type}_loop_config.json"
        )
        
        # 如果配置文件不存在，使用默认配置
        if not os.path.exists(config_file):
            self._configs[intent_type] = LoopConfig()
            return self._configs[intent_type]
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        self._configs[intent_type] = LoopConfig(**config_data)
        return self._configs[intent_type]
    
    def get_node_config_path(self, intent_type: str, node_name: str) -> Optional[str]:
        """
        获取节点配置文件路径
        
        Args:
            intent_type: 意图类型
            node_name: 节点名称（rerank/complexity/context_extract/improvement_analysis等）
        
        Returns:
            配置文件路径，如果节点未启用则返回None
        """
        config = self.load_config(intent_type)
        node_configs = config.node_configs if isinstance(config.node_configs, dict) else {}
        node_config = node_configs.get(node_name, {})
        
        if not node_config.get("enabled", False):
            return None
        
        config_file = node_config.get("config_file", "")
        if not config_file:
            return None
        
        return os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config_file)
    
    def should_execute_node(self, intent_type: str, node_name: str, current_round: int) -> bool:
        """
        判断是否应该执行某个节点
        
        Args:
            intent_type: 意图类型
            node_name: 节点名称
            current_round: 当前轮次
        
        Returns:
            是否执行
        """
        config = self.load_config(intent_type)
        node_configs = config.node_configs if isinstance(config.node_configs, dict) else {}
        node_config = node_configs.get(node_name, {})
        
        if not node_config.get("enabled", False):
            return False
        
        execute_rounds = node_config.get("execute_rounds", [])
        if execute_rounds:
            return current_round in execute_rounds
        
        return True
    
    def get_retrieval_params(self, intent_type: str) -> Dict[str, Any]:
        """
        获取检索参数
        
        Args:
            intent_type: 意图类型
        
        Returns:
            检索参数字典
        """
        config = self.load_config(intent_type)
        return config.retrieval_params


# 单例实例
config_loader = LoopConfigLoader()
