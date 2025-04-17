"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
"""
import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from functools import wraps
from ai_generator import AIDockerGenerator

class WebApp:
    def __init__(self, config_manager, docker_monitor, container_deployer):
        """
        初始化Web应用
        :param config_manager: 配置管理器实例
        :param docker_monitor: Docker监控器实例
        :param container_deployer: 容器部署管理器实例
        """
        self.config_manager = config_manager
        self.docker_monitor = docker_monitor
        self.container_deployer = container_deployer
        self.ai_generator = AIDockerGenerator()
        self.app = Flask(__name__, 
                         static_folder='web/static',
                         template_folder='web/templates')
        self.app.secret_key = os.urandom(24)
        self.setup_routes()
        self.logger = logging.getLogger('web_app')
    
    def setup_routes(self):
        """
        设置Web应用路由
        """
        # 主页和数据接口
        @self.app.route('/')
        def index():
            config = self.config_manager.get_config()
            return render_template('index.html', config=config)
        
        @self.app.route('/api/containers')
        def api_containers():
            try:
                cycle_info = self.docker_monitor.run_monitoring_cycle()
                return jsonify(cycle_info)
            except Exception as e:
                self.logger.error(f"获取容器信息失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/container/<container_id>/restart', methods=['POST'])
        def api_restart_container(container_id):
            try:
                container = self.docker_monitor.client.containers.get(container_id)
                success = self.docker_monitor.restart_container(container)
                return jsonify({'success': success})
            except Exception as e:
                self.logger.error(f"重启容器 {container_id} 失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/container/<container_id>/start', methods=['POST'])
        def api_start_container(container_id):
            try:
                container = self.docker_monitor.client.containers.get(container_id)
                container.start()
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"启动容器 {container_id} 失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/container/<container_id>/stop', methods=['POST'])
        def api_stop_container(container_id):
            try:
                container = self.docker_monitor.client.containers.get(container_id)
                container.stop()
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"停止容器 {container_id} 失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        # 配置管理接口
        @self.app.route('/config')
        def config_page():
            config = self.config_manager.get_config()
            return render_template('config.html', config=config)
        
        @self.app.route('/api/config', methods=['GET', 'POST'])
        def api_config():
            if request.method == 'GET':
                return jsonify(self.config_manager.get_config())
            else:  # POST
                try:
                    new_config = request.json
                    success = self.config_manager.update_config(new_config)
                    # 更新监控器的配置
                    self.docker_monitor.config = self.config_manager.get_config()
                    return jsonify({'success': success})
                except Exception as e:
                    self.logger.error(f"更新配置失败: {e}")
                    return jsonify({'error': str(e)}), 500
        
        # 日志查看接口
        @self.app.route('/logs')
        def logs_page():
            return render_template('logs.html')
        
        @self.app.route('/api/logs')
        def api_logs():
            try:
                log_file = "docker_monitor.log"
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        logs = f.readlines()
                    # 返回最后1000行日志
                    return jsonify({'logs': logs[-1000:]})
                else:
                    return jsonify({'logs': ['日志文件不存在']})
            except Exception as e:
                self.logger.error(f"读取日志失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        # 容器部署接口
        @self.app.route('/deploy')
        def deploy_page():
            return render_template('deploy.html')
        
        @self.app.route('/api/deploy/presets')
        def api_deploy_presets():
            try:
                presets = self.container_deployer.get_presets()
                return jsonify({'presets': presets})
            except Exception as e:
                self.logger.error(f"获取预设容器列表失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deploy/presets/<preset_id>')
        def api_deploy_preset_details(preset_id):
            try:
                preset = self.container_deployer.get_preset_details(preset_id)
                if not preset:
                    return jsonify({'error': f"预设 {preset_id} 不存在"}), 404
                return jsonify({'preset': preset})
            except Exception as e:
                self.logger.error(f"获取预设容器详情失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deploy/generate', methods=['POST'])
        def api_deploy_generate():
            try:
                config = request.json
                preset_id = config.get('preset_id')
                
                if not preset_id:
                    return jsonify({'success': False, 'error': '缺少预设ID'}), 400
                
                # 记录日志，帮助调试
                self.logger.info(f"生成部署配置: 预设={preset_id}, 容器名={config.get('container_name')}")
                
                compose_file, success = self.container_deployer.generate_compose_file(preset_id, config)
                
                if success and compose_file:
                    self.logger.info(f"配置文件生成成功: {compose_file}")
                    return jsonify({
                        'success': True,
                        'compose_file': compose_file
                    })
                else:
                    self.logger.error(f"生成配置文件失败: preset_id={preset_id}")
                    return jsonify({
                        'success': False,
                        'error': f"生成配置文件失败，请检查日志"
                    }), 500
            except Exception as e:
                self.logger.error(f"生成部署配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/deploy/start', methods=['POST'])
        def api_deploy_start():
            try:
                data = request.json
                compose_file = data.get('compose_file')
                
                self.logger.info(f"开始部署容器: {compose_file}")
                
                if not compose_file:
                    error_msg = "缺少compose文件路径"
                    self.logger.error(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 400
                
                # 确保路径是绝对路径
                compose_file = os.path.abspath(compose_file)
                
                if not os.path.exists(compose_file):
                    error_msg = f"找不到配置文件: {compose_file}"
                    self.logger.error(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 400
                
                success, output = self.container_deployer.deploy_container(compose_file)
                
                return jsonify({
                    'success': success,
                    'output': output
                })
            except Exception as e:
                self.logger.error(f"部署容器失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/deploy/deployments')
        def api_deploy_deployments():
            try:
                deployments = self.container_deployer.get_deployments()
                return jsonify({'deployments': deployments})
            except Exception as e:
                self.logger.error(f"获取部署列表失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/deploy/remove', methods=['POST'])
        def api_deploy_remove():
            try:
                data = request.json
                deployment_name = data.get('deployment_name')
                
                if not deployment_name:
                    return jsonify({'success': False, 'error': '缺少部署名称'}), 400
                
                success, output = self.container_deployer.remove_deployment(deployment_name)
                
                return jsonify({
                    'success': success,
                    'output': output
                })
            except Exception as e:
                self.logger.error(f"移除部署失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # AI容器部署接口
        @self.app.route('/ai-deploy')
        def ai_deploy_page():
            return render_template('ai_deploy.html')
        
        @self.app.route('/api/ai/generate', methods=['POST'])
        def api_ai_generate():
            try:
                data = request.json
                requirement = data.get('requirement')
                
                if not requirement:
                    return jsonify({'success': False, 'error': '缺少容器需求描述'}), 400
                
                # 使用AI生成docker-compose配置
                success, result = self.ai_generator.generate_docker_compose(requirement)
                
                if success:
                    return jsonify({
                        'success': True,
                        'yaml': result
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': result
                    }), 500
            except Exception as e:
                self.logger.error(f"AI生成容器配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/ai/deploy', methods=['POST'])
        def api_ai_deploy():
            try:
                data = request.json
                yaml_content = data.get('yaml')
                deployment_name = data.get('deployment_name', f'ai-deployment-{int(datetime.now().timestamp())}')
                
                if not yaml_content:
                    return jsonify({'success': False, 'error': '缺少YAML配置内容'}), 400
                
                # 保存YAML到文件
                save_success, file_path = self.ai_generator.save_to_file(yaml_content, deployment_name)
                
                if not save_success:
                    return jsonify({
                        'success': False,
                        'error': f'保存配置文件失败: {file_path}'
                    }), 500
                
                # 部署容器
                deploy_success, output = self.ai_generator.deploy_container(file_path)
                
                return jsonify({
                    'success': deploy_success,
                    'output': output,
                    'compose_file': file_path if deploy_success else None
                })
            except Exception as e:
                self.logger.error(f"部署AI生成的容器失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # 容器健康监控接口
        @self.app.route('/health')
        def health_page():
            config = self.config_manager.get_config()
            return render_template('health.html', config=config)
        
        @self.app.route('/api/container/<container_id>/stats')
        def api_container_stats(container_id):
            try:
                container = self.docker_monitor.client.containers.get(container_id)
                if container.status != 'running':
                    return jsonify({
                        'success': False,
                        'error': '容器未运行，无法获取统计信息'
                    }), 400
                
                # 获取详细的容器统计信息
                stats = container.stats(stream=False)
                
                # 容器基础信息
                inspect_data = self.docker_monitor.client.api.inspect_container(container.id)
                
                # 获取网络IO统计
                network_stats = {}
                if 'networks' in stats:
                    for interface, data in stats['networks'].items():
                        network_stats[interface] = {
                            'rx_bytes': data.get('rx_bytes', 0),
                            'tx_bytes': data.get('tx_bytes', 0),
                            'rx_packets': data.get('rx_packets', 0),
                            'tx_packets': data.get('tx_packets', 0),
                            'rx_errors': data.get('rx_errors', 0),
                            'tx_errors': data.get('tx_errors', 0),
                            'rx_dropped': data.get('rx_dropped', 0),
                            'tx_dropped': data.get('tx_dropped', 0)
                        }
                
                # 获取块IO统计
                blkio_stats = {}
                if 'blkio_stats' in stats and 'io_service_bytes_recursive' in stats['blkio_stats']:
                    for data in stats['blkio_stats']['io_service_bytes_recursive']:
                        op = data.get('op', '').lower()
                        if op in ['read', 'write']:
                            blkio_stats[op] = data.get('value', 0)
                
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
                
                # 格式化数据大小为可读格式
                def format_bytes(bytes_value):
                    units = ['B', 'KB', 'MB', 'GB', 'TB']
                    size = float(bytes_value)
                    unit_index = 0
                    while size >= 1024 and unit_index < len(units) - 1:
                        size /= 1024
                        unit_index += 1
                    return f"{size:.2f} {units[unit_index]}"
                
                # 构建响应数据
                container_stats = {
                    'id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'health': self.docker_monitor.get_container_health(container),
                    'created': inspect_data.get('Created', ''),
                    'base_info': {
                        'image': inspect_data.get('Config', {}).get('Image', ''),
                        'command': inspect_data.get('Config', {}).get('Cmd', []),
                        'env': inspect_data.get('Config', {}).get('Env', []),
                        'ports': inspect_data.get('NetworkSettings', {}).get('Ports', {}),
                        'volumes': inspect_data.get('Mounts', [])
                    },
                    'cpu': {
                        'percent': round(cpu_percent, 2),
                        'online_cpus': cpu_stats.get('online_cpus', num_cpus),
                        'system_cpu_usage': cpu_stats.get('system_cpu_usage', 0),
                        'throttling_data': cpu_stats.get('throttling_data', {})
                    },
                    'memory': {
                        'usage': memory_usage,
                        'usage_formatted': format_bytes(memory_usage),
                        'limit': memory_limit,
                        'limit_formatted': format_bytes(memory_limit),
                        'percent': round(memory_percent, 2),
                        'stats': {k: v for k, v in memory_stats.get('stats', {}).items()}
                    },
                    'network': network_stats,
                    'io': blkio_stats,
                    'pids': stats.get('pids_stats', {}).get('current', 0)
                }
                
                # 获取容器进程信息
                try:
                    processes = container.top()
                    container_stats['processes'] = {
                        'titles': processes.get('Titles', []),
                        'processes': processes.get('Processes', [])
                    }
                except Exception as e:
                    self.logger.error(f"获取容器 {container.name} 进程信息失败: {e}")
                    container_stats['processes'] = {'titles': [], 'processes': []}
                
                return jsonify({
                    'success': True,
                    'timestamp': stats.get('read', ''),
                    'stats': container_stats
                })
            except Exception as e:
                self.logger.error(f"获取容器 {container_id} 统计信息失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/health/metrics')
        def api_health_metrics():
            try:
                # 获取主机资源使用情况
                import psutil
                
                # 系统CPU使用率
                cpu_percent = psutil.cpu_percent(interval=0.5)
                cpu_count = psutil.cpu_count()
                
                # 系统内存使用率
                mem = psutil.virtual_memory()
                
                # 系统磁盘使用率
                disk = psutil.disk_usage('/')
                
                # 容器数量统计
                containers = self.docker_monitor.client.containers.list(all=True)
                running_count = len([c for c in containers if c.status == 'running'])
                
                # 构建返回数据
                metrics = {
                    'timestamp': datetime.now().isoformat(),
                    'host': {
                        'cpu': {
                            'percent': cpu_percent,
                            'count': cpu_count
                        },
                        'memory': {
                            'total': mem.total,
                            'available': mem.available,
                            'used': mem.used,
                            'percent': mem.percent
                        },
                        'disk': {
                            'total': disk.total,
                            'used': disk.used,
                            'free': disk.free,
                            'percent': disk.percent
                        }
                    },
                    'containers': {
                        'total': len(containers),
                        'running': running_count,
                        'stopped': len(containers) - running_count
                    }
                }
                
                return jsonify({
                    'success': True,
                    'metrics': metrics
                })
            except Exception as e:
                self.logger.error(f"获取系统健康指标失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def run(self):
        """
        运行Web应用
        """
        config = self.config_manager.get_config()
        port = config.get('web_port', 5000)
        self.app.run(host='0.0.0.0', port=port, debug=False) 