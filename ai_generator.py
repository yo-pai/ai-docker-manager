"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
AI-based Docker Compose generator module
"""
import os
import re
import tempfile
import logging
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

class AIDockerGenerator:
    def __init__(self):
        """初始化AI Docker生成器"""
        # 加载环境变量
        load_dotenv()
        
        # 设置日志
        self.logger = logging.getLogger('ai_docker_generator')
        
        # 设置Anthropic客户端
        self.anthropic_client = Anthropic(
            base_url='https://api.openai-proxy.org/anthropic',
            api_key='sk-wVjmhVkRDWZw52GWj9Ot3opAnbepiGIOUqfPF45982usryd0',
        )
        
        # Docker专家提示词
        self.docker_expert_prompt = """你是一个docker专家，擅长编写docker-compose的yaml文件，可以基于用户给的需求进行docker-compose.yaml格式的文件编写，编写的时候你需要遵守；
1. 根据用户想要部署的容器进行yaml格式的文件构建
2. 如果用户提供了版本和一些默认参数的话，构建yaml格式的时候你需要注意加入
3. 平台使用platform: linux/arm64/v8
4. 如果有一些软件需要依赖，请在用户给出需求后，加入到yaml配置文件，例如kafka需依赖zookepeer
5. 只需要给出yaml格式的文件，不要生成其他任何解释和文字

用户需求:
"""
    
    def generate_docker_compose(self, user_requirement):
        """
        基于用户需求生成docker-compose.yaml配置
        
        Args:
            user_requirement (str): 用户的容器需求描述
            
        Returns:
            tuple: (成功状态, YAML配置或错误信息)
        """
        try:
            self.logger.info(f"正在生成Docker配置，需求: {user_requirement}")
            
            # 组合提示词和用户需求
            combined_content = f"{self.docker_expert_prompt}\n\n{user_requirement}"
            
            # 调用Anthropic API
            message = self.anthropic_client.messages.create(
                max_tokens=4080,
                messages=[
                    {
                        "role": "user",
                        "content": combined_content,
                    }
                ],
                model="claude-3-7-sonnet-20250219"
            )
            
            # 提取响应内容
            response_content = message.content[0].text
            
            # 移除Markdown代码块标记
            response_content = re.sub(r'^```yaml\s*', '', response_content, flags=re.MULTILINE)
            response_content = re.sub(r'^```\s*$', '', response_content, flags=re.MULTILINE)
            response_content = response_content.strip()
            
            self.logger.info("Docker配置生成成功")
            return True, response_content
            
        except Exception as e:
            error_msg = f"生成Docker Compose配置时出错: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def save_to_file(self, yaml_content, deployment_name):
        """
        将YAML内容保存为docker-compose文件
        
        Args:
            yaml_content (str): YAML配置内容
            deployment_name (str): 部署名称
            
        Returns:
            tuple: (成功状态, 文件路径或错误信息)
        """
        try:
            # 获取当前工作目录的绝对路径
            current_dir = os.path.abspath(os.getcwd())
            
            # 创建部署目录（使用绝对路径）
            deploy_dir = os.path.join(current_dir, "deployments", "ai", deployment_name)
            self.logger.info(f"Creating deployment directory: {deploy_dir}")
            os.makedirs(deploy_dir, exist_ok=True)
            
            # 文件路径
            compose_file = os.path.join(deploy_dir, "docker-compose.yaml")
            self.logger.info(f"Saving YAML to file: {compose_file}")
            
            # 写入文件
            with open(compose_file, "w") as f:
                f.write(yaml_content)
                
            self.logger.info(f"配置保存到文件: {compose_file}")
            return True, compose_file
            
        except Exception as e:
            error_msg = f"保存配置文件时出错: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def deploy_container(self, compose_file):
        """
        部署容器
        
        Args:
            compose_file (str): docker-compose文件路径
            
        Returns:
            tuple: (成功状态, 输出或错误信息)
        """
        try:
            # 获取docker-compose文件所在目录
            compose_dir = os.path.dirname(compose_file)
            
            # 执行docker-compose up命令
            process = subprocess.Popen(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=compose_dir,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                output = stdout
                self.logger.info(f"容器部署成功: {compose_file}")
                success = True
            else:
                output = f"错误: {stderr}\n输出: {stdout}"
                self.logger.error(f"容器部署失败: {stderr}")
                success = False
                
            return success, output
            
        except Exception as e:
            error_msg = f"部署容器时出错: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg 