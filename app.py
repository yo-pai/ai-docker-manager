"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
Docker容器健康检查与自动恢复系统
"""
import os
import sys
import argparse
import threading
import logging
from config_manager import ConfigManager
from docker_monitor import DockerMonitor
from container_deployer import ContainerDeployer
from web_app import WebApp

def create_directories():
    """创建必要的目录"""
    os.makedirs('web/templates', exist_ok=True)
    os.makedirs('web/static', exist_ok=True)
    os.makedirs('deployments/ai', exist_ok=True)

def start_monitoring_thread(docker_monitor):
    """启动监控线程"""
    logging.info("启动监控线程")
    docker_monitor.start_monitoring()

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description='Docker容器健康检查与自动恢复系统')
    parser.add_argument('--config', type=str, default='config.yaml', help='配置文件路径')
    parser.add_argument('--no-web', action='store_true', help='不启动Web界面')
    args = parser.parse_args()
    
    # 创建必要的目录
    create_directories()
    
    # 初始化配置管理器
    config_manager = ConfigManager(args.config)
    config = config_manager.get_config()
    
    # 初始化Docker监控器
    docker_monitor = DockerMonitor(config)
    
    # 初始化容器部署管理器
    container_deployer = ContainerDeployer()
    
    # 如果不启动Web界面，直接开始监控
    if args.no_web:
        docker_monitor.start_monitoring()
    else:
        # 初始化Web应用
        web_app = WebApp(config_manager, docker_monitor, container_deployer)
        
        # 在单独的线程中启动监控
        monitor_thread = threading.Thread(target=start_monitoring_thread, args=(docker_monitor,))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 启动Web应用
        try:
            print(f"Web界面已启动，访问 http://localhost:{config['web_port']} 查看")
            web_app.run()
        except KeyboardInterrupt:
            print("程序被用户中断")
        except Exception as e:
            print(f"程序运行出错: {e}")

if __name__ == '__main__':
    main() 