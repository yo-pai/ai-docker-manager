"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
"""
import os
import yaml
import json

class ConfigManager:
    def __init__(self, config_file='config.yaml'):
        """
        初始化配置管理器
        :param config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """
        加载配置文件
        :return: 配置字典
        """
        # 默认配置
        default_config = {
            'check_interval': 60,  # 检查间隔，单位秒
            'restart_stopped': True,  # 是否重启已停止的容器
            'restart_unhealthy': True,  # 是否重启不健康的容器
            'restart_threshold': 5,  # 重启阈值（在冷却期内最多重启次数）
            'cooldown_period': 300,  # 冷却期，单位秒
            'monitor_specific_containers': False,  # 是否只监控特定容器
            'container_list': [],  # 要监控的特定容器名称列表
            'web_port': 5000,  # Web界面端口
        }
        
        # 如果配置文件存在，则加载它
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        # 合并用户配置和默认配置
                        default_config.update(user_config)
                        # 删除旧版本可能存在的用户名和密码字段
                        if 'web_username' in default_config:
                            del default_config['web_username']
                        if 'web_password' in default_config:
                            del default_config['web_password']
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        else:
            # 如果配置文件不存在，创建一个默认配置文件
            self.save_config(default_config)
        
        return default_config
    
    def save_config(self, config=None):
        """
        保存配置到文件
        :param config: 要保存的配置字典
        :return: 是否成功保存
        """
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            self.config = config
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def update_config(self, new_config):
        """
        更新配置
        :param new_config: 新的配置字典
        :return: 是否成功更新
        """
        # 合并新配置
        self.config.update(new_config)
        return self.save_config()
    
    def get_config(self):
        """
        获取当前配置
        :return: 配置字典
        """
        return self.config 