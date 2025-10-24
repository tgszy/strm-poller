#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证STRM Poller的本地IP识别和桥接模式功能

此脚本用于测试用户是否可以通过本地IP地址（如192.168.0.111:35455）访问WebUI，
并验证桥接模式配置是否正确工作。
"""

import os
import sys
import socket
import subprocess
import time
import platform
import re
from datetime import datetime

# 默认配置
DEFAULT_PORT = 35455
TARGET_IP = "192.168.0.111"
DOCKER_COMPOSE_FILE = "docker-compose.yml"

# 颜色和格式化
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# 打印带颜色的消息
def print_color(message, color):
    if platform.system() == 'Windows':
        # Windows命令行不支持ANSI颜色，直接打印
        print(message)
    else:
        print(f"{color}{message}{Colors.ENDC}")

# 打印标题
def print_title(title):
    print_color(f"\n{'=' * 60}", Colors.BLUE)
    print_color(f"{Colors.BOLD}{title}{Colors.ENDC}", Colors.BLUE)
    print_color(f"{'=' * 60}", Colors.BLUE)

# 打印测试结果
def print_result(success, message):
    status = f"{Colors.GREEN}{Colors.BOLD}✓ 成功{Colors.ENDC}" if success else f"{Colors.RED}{Colors.BOLD}✗ 失败{Colors.ENDC}"
    print(f"{status} {message}")

# 获取本地网络IP地址
def get_local_network_ips():
    """获取所有本地网络(192.168.x.x)的IP地址"""
    local_ips = []
    try:
        # 获取所有网络接口的IP地址
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
        
        # 过滤出192.168开头的IP地址
        for ip in ip_addresses:
            if ip.startswith('192.168.') and not ip.startswith('192.168.0.0'):
                local_ips.append(ip)
        
        # 如果没找到，尝试其他方法
        if not local_ips:
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and ip.startswith('192.168.'):
                                local_ips.append(ip)
            except ImportError:
                pass
    except Exception as e:
        print_color(f"获取本地网络IP时出错: {e}", Colors.RED)
    
    # 去重并返回
    return list(set(local_ips))

# 检查端口是否被占用
def check_port_usage(port):
    """检查指定端口是否被占用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0  # 0表示端口被占用（有服务在监听）
    except Exception as e:
        print_color(f"检查端口占用时出错: {e}", Colors.RED)
        return False

# 检查Docker是否运行
def is_docker_running():
    """检查Docker是否正在运行"""
    try:
        if platform.system() == 'Windows':
            subprocess.run(['docker', 'ps'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            subprocess.run(['docker', 'ps'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

# 检查Docker Compose配置
def check_docker_compose_config():
    """检查docker-compose.yml配置是否正确"""
    if not os.path.exists(DOCKER_COMPOSE_FILE):
        return False, f"找不到配置文件: {DOCKER_COMPOSE_FILE}"
    
    try:
        with open(DOCKER_COMPOSE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查是否启用了桥接模式
        has_bridge_mode = 'BRIDGE_MODE=true' in content
        # 检查端口映射是否正确
        has_port_mapping = 'ports:' in content and '35455:35455' in content
        # 检查是否使用了bridge网络（而不是host网络）
        using_bridge = 'network_mode: "host"' not in content or '# network_mode: "host"' in content
        
        issues = []
        if not has_bridge_mode:
            issues.append("未启用桥接模式 (BRIDGE_MODE=true)")
        if not has_port_mapping:
            issues.append("未找到正确的端口映射 (35455:35455)")
        if not using_bridge:
            issues.append("仍在使用host网络模式，请注释掉network_mode: \"host\"")
        
        if issues:
            return False, "配置问题: " + ", ".join(issues)
        
        return True, "Docker Compose配置正确"
    except Exception as e:
        return False, f"读取配置文件时出错: {e}"

# 尝试访问WebUI
def test_webui_access(ip, port):
    """尝试访问WebUI并返回结果"""
    try:
        url = f"http://{ip}:{port}"
        if platform.system() == 'Windows':
            # Windows使用curl或PowerShell
            try:
                # 尝试使用curl
                result = subprocess.run(['curl', '-s', '-o', 'nul', '-w', '%{http_code}', url], 
                                      check=True, capture_output=True, text=True, timeout=5)
                return result.stdout.strip() == '200'
            except (subprocess.CalledProcessError, FileNotFoundError):
                # 尝试使用PowerShell
                ps_command = f"Invoke-WebRequest -Uri {url} -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop"
                result = subprocess.run(['powershell', '-Command', ps_command], 
                                      capture_output=True, text=True, timeout=5)
                return result.returncode == 0
        else:
            # Linux/macOS使用curl
            result = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', url], 
                                  check=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == '200'
    except Exception as e:
        print_color(f"访问{ip}:{port}时出错: {e}", Colors.RED)
        return False

# 检查防火墙设置
def check_firewall_status(port):
    """检查Windows防火墙是否开放指定端口"""
    if platform.system() != 'Windows':
        return True, "请手动检查Linux/macOS防火墙设置"
    
    try:
        # 检查Windows防火墙规则
        command = f"netsh advfirewall firewall show rule name=all | findstr \"{port}\""
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        if str(port) in result.stdout:
            return True, f"端口{port}已在防火墙中配置"
        else:
            return False, f"端口{port}未在防火墙中找到，请添加防火墙规则"
    except Exception as e:
        return False, f"检查防火墙时出错: {e}"

# 获取网络接口信息
def get_network_interface_info():
    """获取网络接口信息"""
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        else:
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"获取网络接口信息时出错: {e}"

# 主要测试函数
def run_tests():
    print_title("STRM Poller 桥接模式和本地IP访问测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试目标IP: {TARGET_IP}")
    print(f"测试端口: {DEFAULT_PORT}")
    print()
    
    # 测试1: 获取本地网络IP
    print_color("\n1. 本地网络IP检测:", Colors.BOLD)
    local_ips = get_local_network_ips()
    if local_ips:
        print_result(True, f"发现{len(local_ips)}个本地网络IP地址")
        for ip in local_ips:
            print(f"   - {ip}")
        # 检查目标IP是否在本地IP列表中
        if TARGET_IP in local_ips:
            print_color(f"✓ 目标IP {TARGET_IP} 是本机的有效IP地址", Colors.GREEN)
        else:
            print_color(f"⚠️  目标IP {TARGET_IP} 不是本机的有效IP地址，将使用检测到的本地IP进行测试", Colors.YELLOW)
    else:
        print_result(False, "未检测到本地网络(192.168.x.x)IP地址")
    
    # 测试2: 检查Docker状态
    print_color("\n2. Docker环境检测:", Colors.BOLD)
    if is_docker_running():
        print_result(True, "Docker服务正在运行")
    else:
        print_result(False, "Docker服务未运行，请先启动Docker")
    
    # 测试3: 检查Docker Compose配置
    print_color("\n3. Docker Compose配置检查:", Colors.BOLD)
    success, message = check_docker_compose_config()
    print_result(success, message)
    if not success:
        print_color(f"\n建议的修复方法:", Colors.YELLOW)
        print(f"1. 编辑 {DOCKER_COMPOSE_FILE} 文件")
        print(f"2. 取消注释 ports: 配置并设置为 - \"35455:35455\"")
        print(f"3. 注释掉 network_mode: \"host\" 行")
        print(f"4. 在 environment 部分添加: - BRIDGE_MODE=true")
    
    # 测试4: 检查端口占用
    print_color("\n4. 端口占用检查:", Colors.BOLD)
    port_used = check_port_usage(DEFAULT_PORT)
    if port_used:
        print_result(True, f"端口 {DEFAULT_PORT} 已被占用（服务可能正在运行）")
    else:
        print_result(False, f"端口 {DEFAULT_PORT} 未被占用，请确保服务正在运行")
    
    # 测试5: 防火墙检查
    print_color("\n5. 防火墙状态检查:", Colors.BOLD)
    success, message = check_firewall_status(DEFAULT_PORT)
    print_result(success, message)
    if not success and platform.system() == 'Windows':
        print_color(f"\n添加防火墙规则的命令:", Colors.YELLOW)
        print(f"netsh advfirewall firewall add rule name=\"STRM Poller\" dir=in action=allow protocol=TCP localport={DEFAULT_PORT} remoteip=any profile=any")
        print(f"请以管理员权限运行命令提示符并执行上述命令")
    
    # 测试6: WebUI访问测试
    print_color("\n6. WebUI访问测试:", Colors.BOLD)
    test_ips = []
    if TARGET_IP in local_ips:
        test_ips.append(TARGET_IP)
    test_ips.extend(local_ips[:3])  # 最多测试3个IP
    test_ips = list(set(test_ips))  # 去重
    
    if test_ips:
        for ip in test_ips:
            url = f"http://{ip}:{DEFAULT_PORT}"
            print(f"正在测试: {url}")
            if test_webui_access(ip, DEFAULT_PORT):
                print_result(True, f"成功访问 {url}")
                print_color(f"\n🎉 可以通过以下地址访问WebUI:", Colors.GREEN)
                print_color(f"   {url}", Colors.GREEN)
            else:
                print_result(False, f"无法访问 {url}")
    else:
        print("没有可用的本地IP进行测试")
    
    # 显示网络诊断信息
    print_color("\n7. 网络诊断信息:", Colors.BOLD)
    print_color("网络接口信息:", Colors.YELLOW)
    print(get_network_interface_info())
    
    # 显示使用说明
    print_title("使用说明")
    print_color("1. 启动STRM Poller服务:", Colors.BOLD)
    print(f"   docker-compose up -d")
    print()
    print_color("2. 启用桥接模式:", Colors.BOLD)
    print(f"   - 确保docker-compose.yml中设置了 BRIDGE_MODE=true")
    print(f"   - 确保端口映射正确: ports: - \"35455:35455\"")
    print()
    print_color("3. 访问WebUI:", Colors.BOLD)
    print(f"   - 使用检测到的本地IP: http://[本地IP]:35455")
    print(f"   - 例如: http://{TARGET_IP}:35455")
    print()
    print_color("4. 故障排除:", Colors.BOLD)
    print(f"   - 检查防火墙是否已开放35455端口")
    print(f"   - 确保Docker服务正在运行")
    print(f"   - 查看容器日志: docker-compose logs -f")
    print(f"   - 检查网络连接: ping {TARGET_IP}")
    
    print_title("测试完成")

if __name__ == "__main__":
    run_tests()