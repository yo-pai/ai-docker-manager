"""
@Author  : yo-pai
@GitHub  : https://github.com/yo-pai
容器部署管理器 - 自动构建和部署常用容器
"""
import os
import yaml
import docker
import logging
import subprocess
from pathlib import Path

class ContainerDeployer:
    def __init__(self):
        """
        初始化容器部署管理器
        """
        self.client = docker.from_env()
        self.logger = logging.getLogger('container_deployer')
        # 使用绝对路径避免路径混淆
        self.deploy_dir = os.path.abspath("deployments")
        self.setup_deploy_directory()
        
        # 预设容器列表和配置 - 更新支持 ARM64 的版本
        self.presets = {
            'redis': {
                'name': 'Redis',
                'description': '高性能的键值数据库',
                'versions': ['6.0', '6.2', '7.0', '7.2'],  # Redis 原生支持 ARM64
                'default_port': 6379,
                'default_volume': '/data',
                'icon': 'fa-database',
                'color': 'danger',
                'options': {
                    'password': {
                        'type': 'password',
                        'label': '密码',
                        'required': False,
                        'default': ''
                    },
                    'persistence': {
                        'type': 'checkbox',
                        'label': '开启持久化',
                        'default': True
                    },
                    'maxmemory': {
                        'type': 'select',
                        'label': '最大内存',
                        'default': '256mb',
                        'options': ['128mb', '256mb', '512mb', '1gb', '2gb', '4gb']
                    }
                }
            },
            'mysql': {
                'name': 'MySQL',
                'description': '流行的关系型数据库',
                'versions': ['8.0', '8.1'],  # 只使用支持 ARM64 的版本
                'default_port': 3306,
                'default_volume': '/var/lib/mysql',
                'icon': 'fa-database',
                'color': 'primary',
                'options': {
                    'root_password': {
                        'type': 'password',
                        'label': 'Root密码',
                        'required': True,
                        'default': ''
                    },
                    'database': {
                        'type': 'text',
                        'label': '初始数据库',
                        'required': False,
                        'default': ''
                    },
                    'user': {
                        'type': 'text',
                        'label': '用户名',
                        'required': False,
                        'default': ''
                    },
                    'password': {
                        'type': 'password',
                        'label': '用户密码',
                        'required': False,
                        'default': ''
                    },
                    'character_set': {
                        'type': 'select',
                        'label': '字符集',
                        'default': 'utf8mb4',
                        'options': ['utf8', 'utf8mb4', 'latin1']
                    }
                }
            },
            'kafka': {
                'name': 'Kafka',
                'description': '分布式流处理平台',
                'versions': ['7.2.1', '7.1.9', '7.0.9', '6.2.13'],
                'default_port': 9092,
                'default_volume': '/var/lib/kafka/data',
                'icon': 'fa-exchange',
                'color': 'success',
                'options': {
                    'zookeeper': {
                        'type': 'checkbox',
                        'label': '包含Zookeeper',
                        'default': True
                    },
                    'partitions': {
                        'type': 'number',
                        'label': '默认分区数',
                        'min': 1,
                        'max': 100,
                        'default': 3
                    },
                    'replication_factor': {
                        'type': 'number',
                        'label': '复制因子',
                        'min': 1,
                        'max': 3,
                        'default': 1
                    },
                    'heap_size': {
                        'type': 'select',
                        'label': 'JVM堆大小',
                        'default': '1g',
                        'options': ['512m', '1g', '2g', '4g']
                    }
                }
            },
            'nginx': {
                'name': 'Nginx',
                'description': '高性能Web服务器',
                'versions': ['1.21', '1.22', '1.23', '1.24'],
                'default_port': 80,
                'default_volume': '/usr/share/nginx/html',
                'icon': 'fa-server',
                'color': 'info',
                'options': {
                    'https': {
                        'type': 'checkbox',
                        'label': '开启HTTPS',
                        'default': False
                    },
                    'cache': {
                        'type': 'checkbox',
                        'label': '开启缓存',
                        'default': False
                    },
                    'worker_processes': {
                        'type': 'select',
                        'label': '工作进程数',
                        'default': 'auto',
                        'options': ['auto', '1', '2', '4', '8']
                    }
                }
            },
            'mongodb': {
                'name': 'MongoDB',
                'description': '文档型NoSQL数据库',
                'versions': ['4.4', '5.0', '6.0', '7.0'],
                'default_port': 27017,
                'default_volume': '/data/db',
                'icon': 'fa-database',
                'color': 'success',
                'options': {
                    'auth': {
                        'type': 'checkbox',
                        'label': '开启认证',
                        'default': True
                    },
                    'root_username': {
                        'type': 'text',
                        'label': '管理员用户名',
                        'required': False,
                        'default': 'admin'
                    },
                    'root_password': {
                        'type': 'password',
                        'label': '管理员密码',
                        'required': False,
                        'default': ''
                    },
                    'wiredtiger_cache': {
                        'type': 'select',
                        'label': '缓存大小',
                        'default': '0.5',
                        'options': ['0.25', '0.5', '1.0', '2.0']
                    }
                }
            }
        }
    
    def setup_deploy_directory(self):
        """创建部署文件存放目录"""
        os.makedirs(self.deploy_dir, exist_ok=True)
        # 确保数据卷目录存在
        volumes_dir = os.path.join(self.deploy_dir, "volumes")
        os.makedirs(volumes_dir, exist_ok=True)
    
    def get_presets(self):
        """
        获取预设容器列表
        :return: 所有预设容器的信息
        """
        return self.presets
    
    def get_preset_details(self, preset_id):
        """
        获取特定预设容器的详细信息
        :param preset_id: 预设ID
        :return: 预设详细信息或None
        """
        return self.presets.get(preset_id)
    
    def generate_compose_file(self, preset_id, config):
        """
        生成docker-compose.yml文件
        :param preset_id: 预设ID
        :param config: 用户配置
        :return: (compose文件路径, 是否成功)
        """
        try:
            # 获取预设信息
            preset = self.presets.get(preset_id)
            if not preset:
                self.logger.error(f"预设 {preset_id} 不存在")
                return None, False
            
            # 准备compose配置
            compose_config = {
                'version': '3',
                'services': {},
                'volumes': {}
            }
            
            # 容器名称
            container_name = config.get('container_name', preset_id)
            
            # 选择版本
            version = config.get('version', preset['versions'][0])
            
            # 端口映射
            port = config.get('port', preset['default_port'])
            
            # 数据卷
            if config.get('use_volume', True):
                volume_name = f"{container_name}_data"
                compose_config['volumes'][volume_name] = {'driver': 'local'}
            
            # 添加平台配置
            platform = 'linux/arm64/v8'  # 对于 M1/M2 MacBook
            
            # 根据不同的服务类型，生成不同的配置
            if preset_id == 'redis':
                compose_config['services'][container_name] = {
                    'image': f'redis:{version}',
                    'platform': platform,  # 指定平台
                    'container_name': container_name,
                    'restart': 'always',
                    'ports': [f"{port}:6379"],
                    'command': []
                }
                
                # Redis密码
                if config.get('password'):
                    compose_config['services'][container_name]['command'].append(f"--requirepass {config['password']}")
                
                # 持久化
                if config.get('persistence', True):
                    compose_config['services'][container_name]['command'].append("--appendonly yes")
                
                # 最大内存
                if config.get('maxmemory'):
                    compose_config['services'][container_name]['command'].append(f"--maxmemory {config['maxmemory']}")
                
                # 如果命令列表不为空，将其转换为字符串
                if compose_config['services'][container_name]['command']:
                    compose_config['services'][container_name]['command'] = ' '.join(compose_config['services'][container_name]['command'])
                else:
                    del compose_config['services'][container_name]['command']
                
                # 添加数据卷
                if config.get('use_volume', True):
                    compose_config['services'][container_name]['volumes'] = [f"{volume_name}:/data"]
            
            elif preset_id == 'mysql':
                compose_config['services'][container_name] = {
                    'image': f'mysql:{version}',
                    'platform': platform,  # 指定平台
                    'container_name': container_name,
                    'restart': 'always',
                    'ports': [f"{port}:3306"],
                    'environment': {
                        'MYSQL_ROOT_PASSWORD': config.get('root_password', 'mysql')
                    }
                }
                
                # 其他可选环境变量
                if config.get('database'):
                    compose_config['services'][container_name]['environment']['MYSQL_DATABASE'] = config.get('database')
                
                if config.get('user') and config.get('password'):
                    compose_config['services'][container_name]['environment']['MYSQL_USER'] = config.get('user')
                    compose_config['services'][container_name]['environment']['MYSQL_PASSWORD'] = config.get('password')
                
                # 字符集
                if config.get('character_set'):
                    char_set = config.get('character_set')
                    compose_config['services'][container_name]['command'] = f"--character-set-server={char_set} --collation-server={char_set}_unicode_ci"
                
                # 添加数据卷
                if config.get('use_volume', True):
                    compose_config['services'][container_name]['volumes'] = [f"{volume_name}:/var/lib/mysql"]
            
            elif preset_id == 'kafka':
                zk_name = f"{container_name}_zookeeper"
                
                # 如果需要Zookeeper
                if config.get('zookeeper', True):
                    compose_config['services'][zk_name] = {
                        'image': 'bitnami/zookeeper:latest',
                        'platform': platform,
                        'container_name': zk_name,
                        'restart': 'always',
                        'ports': ['2181:2181'],
                        'environment': {
                            'ALLOW_ANONYMOUS_LOGIN': 'yes'
                        }
                    }
                
                # Kafka配置，使用 bitnami 的 kafka 镜像
                compose_config['services'][container_name] = {
                    'image': f'bitnami/kafka:{version}',
                    'platform': platform,
                    'container_name': container_name,
                    'restart': 'always',
                    'ports': [
                        f"{port}:9092",
                        f"{int(port)+1}:9093"
                    ],
                    'environment': {
                        'KAFKA_CFG_NODE_ID': '1',
                        'KAFKA_CFG_LISTENERS': 'PLAINTEXT://:9092,CONTROLLER://:9093',
                        'KAFKA_CFG_ADVERTISED_LISTENERS': f'PLAINTEXT://localhost:{port}',
                        'KAFKA_CFG_CONTROLLER_LISTENER_NAMES': 'CONTROLLER',
                        'KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE': 'true',
                        'KAFKA_CFG_NUM_PARTITIONS': str(config.get('partitions', 3)),
                        'KAFKA_HEAP_OPTS': f"-Xmx{config.get('heap_size', '1g')} -Xms{config.get('heap_size', '1g')}"
                    }
                }
                
                # 如果使用Zookeeper
                if config.get('zookeeper', True):
                    compose_config['services'][container_name]['depends_on'] = [zk_name]
                    compose_config['services'][container_name]['environment'].update({
                        'KAFKA_CFG_ZOOKEEPER_CONNECT': f"{zk_name}:2181"
                    })
                else:
                    # 如果不使用Zookeeper，使用KRaft模式
                    compose_config['services'][container_name]['environment'].update({
                        'KAFKA_KRAFT_CLUSTER_ID': 'abcdefghijklmnopqrstuv',
                        'KAFKA_CFG_PROCESS_ROLES': 'broker,controller',
                        'KAFKA_CFG_CONTROLLER_QUORUM_VOTERS': '1@localhost:9093'
                    })
                
                # 添加数据卷
                if config.get('use_volume', True):
                    compose_config['services'][container_name]['volumes'] = [f"{volume_name}:/bitnami/kafka"]
                    if config.get('zookeeper', True):
                        zk_volume = f"{container_name}_zookeeper_data"
                        compose_config['volumes'][zk_volume] = {'driver': 'local'}
                        compose_config['services'][zk_name]['volumes'] = [f"{zk_volume}:/bitnami/zookeeper"]
            
            elif preset_id == 'nginx':
                compose_config['services'][container_name] = {
                    'image': f'nginx:{version}',
                    'platform': platform,
                    'container_name': container_name,
                    'restart': 'always',
                    'ports': [f"{port}:80"]
                }
                
                # HTTPS支持
                if config.get('https', False):
                    compose_config['services'][container_name]['ports'].append('443:443')
                
                # 工作进程
                if config.get('worker_processes'):
                    if not 'environment' in compose_config['services'][container_name]:
                        compose_config['services'][container_name]['environment'] = {}
                    compose_config['services'][container_name]['environment']['NGINX_WORKER_PROCESSES'] = config.get('worker_processes')
                
                # 添加数据卷
                if config.get('use_volume', True):
                    # 网站数据
                    compose_config['services'][container_name]['volumes'] = [f"{volume_name}:/usr/share/nginx/html"]
                    # 配置文件
                    config_volume = f"{container_name}_config"
                    compose_config['volumes'][config_volume] = {'driver': 'local'}
                    compose_config['services'][container_name]['volumes'].append(f"{config_volume}:/etc/nginx/conf.d")
            
            elif preset_id == 'mongodb':
                compose_config['services'][container_name] = {
                    'image': f'mongo:{version}',
                    'platform': platform,
                    'container_name': container_name,
                    'restart': 'always',
                    'ports': [f"{port}:27017"]
                }
                
                # 认证
                if config.get('auth', True) and config.get('root_username') and config.get('root_password'):
                    compose_config['services'][container_name]['environment'] = {
                        'MONGO_INITDB_ROOT_USERNAME': config.get('root_username'),
                        'MONGO_INITDB_ROOT_PASSWORD': config.get('root_password')
                    }
                
                # WiredTiger缓存大小
                if config.get('wiredtiger_cache'):
                    if 'environment' not in compose_config['services'][container_name]:
                        compose_config['services'][container_name]['environment'] = {}
                    compose_config['services'][container_name]['environment']['MONGO_WIREDTIGER_CACHE_SIZE_GB'] = config.get('wiredtiger_cache')
                
                # 添加数据卷
                if config.get('use_volume', True):
                    compose_config['services'][container_name]['volumes'] = [f"{volume_name}:/data/db"]
            
            # 移除 version 字段，因为它已经过时
            if 'version' in compose_config:
                del compose_config['version']
            
            # 保存docker-compose.yml文件 - 修复路径问题
            deploy_path = os.path.join(self.deploy_dir, container_name)
            
            # 清理旧目录，确保路径干净
            if os.path.exists(deploy_path):
                import shutil
                try:
                    shutil.rmtree(deploy_path)
                except Exception as e:
                    self.logger.warning(f"清理旧部署目录失败: {e}")
            
            # 重新创建目录
            try:
                os.makedirs(deploy_path, exist_ok=True)
            except Exception as e:
                self.logger.error(f"创建部署目录失败: {e}")
                return None, False
            
            compose_file = os.path.join(deploy_path, 'docker-compose.yml')
            self.logger.info(f"保存部署文件到: {compose_file}")
            
            with open(compose_file, 'w', encoding='utf-8') as f:
                yaml.dump(compose_config, f, default_flow_style=False)
            
            return compose_file, True
        
        except Exception as e:
            self.logger.error(f"生成Compose文件失败: {e}")
            return None, False
    
    def deploy_container(self, compose_file):
        """
        使用docker-compose部署容器
        :param compose_file: docker-compose.yml文件路径
        :return: (是否成功部署, 输出信息)
        """
        try:
            # 验证文件存在
            if not os.path.exists(compose_file):
                error_msg = f"Compose文件不存在: {compose_file}"
                self.logger.error(error_msg)
                return False, error_msg
            
            compose_dir = os.path.dirname(compose_file)
            self.logger.info(f"在目录 {compose_dir} 中执行docker-compose up -d")
            
            # 使用subprocess调用docker-compose
            process = subprocess.Popen(
                ['docker-compose', '-f', compose_file, 'up', '-d'], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=compose_dir
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"容器部署成功: {compose_file}")
                return True, stdout.decode()
            else:
                error_msg = stderr.decode()
                self.logger.error(f"容器部署失败: {error_msg}")
                return False, error_msg
        
        except Exception as e:
            self.logger.error(f"部署容器时发生错误: {e}")
            return False, str(e)
    
    def get_deployments(self):
        """
        获取已部署的容器列表
        :return: 部署信息列表
        """
        deployments = []
        try:
            # 遍历部署目录
            for item in os.listdir(self.deploy_dir):
                deployment_dir = os.path.join(self.deploy_dir, item)
                compose_file = os.path.join(deployment_dir, 'docker-compose.yml')
                
                # 如果存在docker-compose.yml文件，则认为是有效部署
                if os.path.isdir(deployment_dir) and os.path.exists(compose_file):
                    # 读取compose文件内容
                    with open(compose_file, 'r', encoding='utf-8') as f:
                        compose_data = yaml.safe_load(f)
                    
                    # 提取关键信息
                    if compose_data and 'services' in compose_data:
                        for service_name, service_config in compose_data['services'].items():
                            # 跳过辅助服务如zookeeper
                            if '_zookeeper' in service_name:
                                continue
                                
                            deployments.append({
                                'name': service_name,
                                'image': service_config.get('image', 'unknown'),
                                'ports': service_config.get('ports', []),
                                'volumes': service_config.get('volumes', []),
                                'compose_file': compose_file,
                                'status': self._get_container_status(service_name)
                            })
            
            return deployments
        
        except Exception as e:
            self.logger.error(f"获取部署列表失败: {e}")
            return []
    
    def _get_container_status(self, container_name):
        """
        获取容器状态
        :param container_name: 容器名称
        :return: 容器状态
        """
        try:
            container = self.client.containers.get(container_name)
            return container.status
        except:
            return "not_found"
    
    def remove_deployment(self, deployment_name):
        """
        移除部署
        :param deployment_name: 部署名称
        :return: (是否成功, 输出信息)
        """
        try:
            deploy_path = os.path.join(self.deploy_dir, deployment_name)
            compose_file = os.path.join(deploy_path, 'docker-compose.yml')
            
            if not os.path.exists(compose_file):
                return False, f"找不到部署 {deployment_name} 的compose文件"
            
            # 使用docker-compose down命令
            process = subprocess.Popen(
                ['docker-compose', '-f', compose_file, 'down', '-v'], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=deploy_path
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # 可以选择是否删除部署文件
                return True, stdout.decode()
            else:
                return False, stderr.decode()
        
        except Exception as e:
            self.logger.error(f"移除部署时发生错误: {e}")
            return False, str(e) 