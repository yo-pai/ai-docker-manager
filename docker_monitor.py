"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
"""
import docker
import time
import logging
import json
from datetime import datetime

class DockerMonitor:
    def __init__(self, config):
        """
        初始化Docker监控器
        :param config: 配置字典，包含监控参数
        """
        self.config = config
        self.client = docker.from_env()
        self.logger = logging.getLogger('docker_monitor')
        self.container_history = {}  # 存储容器历史状态
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志记录"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("docker_monitor.log"),
                logging.StreamHandler()
            ]
        )
    
    def get_container_health(self, container):
        """
        获取容器的健康状态
        :param container: Docker容器对象
        :return: 健康状态字符串
        """
        try:
            container.reload()  # 刷新容器状态
            inspect_data = self.client.api.inspect_container(container.id)
            if 'Health' in inspect_data['State']:
                return inspect_data['State']['Health']['Status']
            return "no_healthcheck"
        except Exception as e:
            self.logger.error(f"获取容器{container.name}健康状态失败: {e}")
            return "unknown"
    
    def restart_container(self, container):
        """
        重启容器
        :param container: Docker容器对象
        :return: 是否成功重启
        """
        try:
            self.logger.info(f"正在重启容器 {container.name}...")
            container.restart()
            self.logger.info(f"容器 {container.name} 重启成功")
            return True
        except Exception as e:
            self.logger.error(f"重启容器 {container.name} 失败: {e}")
            return False
    
    def monitor_containers(self):
        """
        监控所有需要监控的容器，检查健康状态并按需重启
        :return: 容器状态的字典列表
        """
        try:
            containers_data = []
            containers = self.client.containers.list(all=True)
            
            for container in containers:
                # 如果配置了特定容器列表且当前容器不在列表中，则跳过
                if self.config.get('monitor_specific_containers', False) and \
                   container.name not in self.config.get('container_list', []):
                    continue
                
                # 获取容器基本信息
                container_info = {
                    'id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'health': self.get_container_health(container),
                    'created': container.attrs.get('Created', ''),
                    'need_restart': False,
                    'stats': {},
                    'processes': []
                }
                
                # 收集容器统计信息
                try:
                    if container.status == 'running':
                        stats = container.stats(stream=False)
                        # CPU使用统计
                        cpu_stats = stats.get('cpu_stats', {})
                        precpu_stats = stats.get('precpu_stats', {})
                        cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                                   precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                        system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                                      precpu_stats.get('system_cpu_usage', 0)
                        num_cpus = len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', []))
                        
                        cpu_percent = 0.0
                        if system_delta > 0 and cpu_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
                        
                        # 内存使用统计
                        memory_stats = stats.get('memory_stats', {})
                        memory_usage = memory_stats.get('usage', 0)
                        memory_limit = memory_stats.get('limit', 1)
                        memory_percent = (memory_usage / memory_limit) * 100.0
                        
                        container_info['stats'] = {
                            'cpu_percent': round(cpu_percent, 2),
                            'memory_usage': memory_usage,
                            'memory_limit': memory_limit,
                            'memory_percent': round(memory_percent, 2)
                        }
                except Exception as e:
                    self.logger.error(f"获取容器 {container.name} 统计信息失败: {e}")
                
                # 获取容器进程信息
                try:
                    if container.status == 'running':
                        processes = container.top()
                        container_info['processes'] = {
                            'titles': processes.get('Titles', []),
                            'processes': processes.get('Processes', [])
                        }
                except Exception as e:
                    self.logger.error(f"获取容器 {container.name} 进程信息失败: {e}")
                
                # 检查是否需要重启
                need_restart = False
                restart_reason = None
                
                # 检查状态是否为已停止
                if container.status in ['exited', 'dead']:
                    if self.config.get('restart_stopped', True):
                        need_restart = True
                        restart_reason = "容器已停止"
                
                # 检查健康状态是否不健康
                elif container_info['health'] == 'unhealthy':
                    if self.config.get('restart_unhealthy', True):
                        need_restart = True
                        restart_reason = "容器不健康"
                
                # 执行自动重启
                if need_restart:
                    # 检查历史重启记录，避免过于频繁重启
                    container_history = self.container_history.get(container.id, {
                        'restart_count': 0,
                        'last_restart': None
                    })
                    
                    current_time = datetime.now()
                    restart_threshold = self.config.get('restart_threshold', 5)
                    cooldown_period = self.config.get('cooldown_period', 300)  # 默认5分钟冷却期
                    
                    # 如果在冷却期内且已超过重启阈值，则不重启
                    if (container_history['last_restart'] and 
                        (current_time - container_history['last_restart']).total_seconds() < cooldown_period and
                        container_history['restart_count'] >= restart_threshold):
                        self.logger.warning(
                            f"容器 {container.name} 需要重启，但已经达到重启阈值 "
                            f"({container_history['restart_count']}/{restart_threshold})，处于冷却期"
                        )
                    else:
                        # 执行重启
                        restart_success = self.restart_container(container)
                        if restart_success:
                            # 更新重启计数和时间
                            if (container_history['last_restart'] and 
                                (current_time - container_history['last_restart']).total_seconds() > cooldown_period):
                                # 如果已经过了冷却期，重置计数
                                container_history['restart_count'] = 1
                            else:
                                container_history['restart_count'] += 1
                            
                            container_history['last_restart'] = current_time
                            self.container_history[container.id] = container_history
                            
                            # 重启后重新加载容器状态
                            container.reload()
                            container_info['status'] = container.status
                            container_info['health'] = self.get_container_health(container)
                
                container_info['restart_history'] = self.container_history.get(container.id, {
                    'restart_count': 0,
                    'last_restart': None
                })
                
                # 如果存在last_restart时间，确保它是一个字符串以便JSON序列化
                if container_info['restart_history'].get('last_restart'):
                    last_restart = container_info['restart_history']['last_restart']
                    # 只有当它是datetime对象时才调用isoformat()
                    if hasattr(last_restart, 'isoformat'):
                        container_info['restart_history']['last_restart'] = last_restart.isoformat()
                
                containers_data.append(container_info)
            
            return containers_data
        
        except Exception as e:
            self.logger.error(f"监控容器时发生错误: {e}")
            return []
    
    def run_monitoring_cycle(self):
        """
        运行一个完整的监控周期
        :return: 容器状态信息
        """
        containers_data = self.monitor_containers()
        cycle_info = {
            'timestamp': datetime.now().isoformat(),
            'containers': containers_data
        }
        return cycle_info
    
    def start_monitoring(self, single_run=False):
        """
        开始持续监控容器
        :param single_run: 是否只运行一次（用于测试）
        :return: None
        """
        try:
            self.logger.info("开始Docker容器监控服务")
            interval = self.config.get('check_interval', 60)  # 默认60秒
            
            while True:
                cycle_info = self.run_monitoring_cycle()
                
                # 打印监控信息概要
                self.logger.info(f"监控周期完成，检查了 {len(cycle_info['containers'])} 个容器")
                for container in cycle_info['containers']:
                    self.logger.info(
                        f"容器 {container['name']} - 状态: {container['status']}, "
                        f"健康状态: {container['health']}"
                    )
                
                if single_run:
                    return cycle_info
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("监控服务被用户中断")
        except Exception as e:
            self.logger.error(f"监控服务发生错误: {e}") 