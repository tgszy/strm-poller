#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebUI访问测试脚本

这个脚本用于测试STRM Poller的WebUI是否可以被正常访问。
它会执行以下测试：
1. 检查35455端口是否正在监听
2. 尝试从本地访问WebUI
3. 显示系统网络配置信息
4. 提供Docker运行测试命令

使用方法：
    python test_webui_access.py
"""

import os
import sys
import socket
import subprocess
import platform
import time
from datetime import datetime

# 配置信息
PORT = 35455
DEFAULT_HOST = "0.0.0.0"
LOCALHOST = "127.0.0.1"


def print_header():
    """打印脚本头部信息"""
    print("=" * 60)
    print("STRM Poller WebUI 访问测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"系统: {platform.system()} {platform.release()}")
    print("=" * 60)
    print()


def check_port_listening(port):
    """检查指定端口是否正在监听"""
    print(f"检查端口 {port} 是否正在监听...")
    
    # 使用socket尝试连接
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    
    # 尝试连接到本地端口
    result = sock.connect_ex((LOCALHOST, port))
    sock.close()
    
    if result == 0:
        print(f"✅ 端口 {port} 正在监听")
        return True
    else:
        print(f"❌ 端口 {port} 未在监听")
        print("  可能的原因：")
        print("  - STRM Poller 服务未启动")
        print("  - 服务启动失败")
        print("  - 端口被其他服务占用")
        return False


def check_port_occupation(port):
    """检查端口被哪个进程占用"""
    print(f"\n检查端口 {port} 的占用情况...")
    
    system = platform.system()
    try:
        if system == "Windows":
            # Windows系统使用netstat命令
            cmd = f"netstat -ano | findstr :{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                print("端口占用信息:")
                print(result.stdout.strip())
                
                # 提取PID
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[4]
                        print(f"\n查询进程信息 (PID: {pid}):")
                        process_cmd = f"tasklist /FI \"PID eq {pid}\" /FO LIST"
                        process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
                        print(process_result.stdout.strip() or f"未找到PID为 {pid} 的进程信息")
            else:
                print("未发现端口占用信息")
                
        else:
            # Linux/macOS系统使用lsof或netstat
            try:
                cmd = f"lsof -i :{port}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout:
                    print("端口占用信息:")
                    print(result.stdout.strip())
                else:
                    cmd = f"netstat -tulpn | grep :{port}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.stdout:
                        print("端口占用信息:")
                        print(result.stdout.strip())
                    else:
                        print("未发现端口占用信息")
            except Exception as e:
                print(f"检查端口占用失败: {e}")
    except Exception as e:
        print(f"执行命令时出错: {e}")


def test_webui_access():
    """测试从本地访问WebUI"""
    print(f"\n尝试访问本地WebUI (http://{LOCALHOST}:{PORT})...")
    
    # 尝试使用curl或wget测试访问
    system = platform.system()
    try:
        if system == "Windows":
            # Windows系统使用PowerShell的Invoke-WebRequest
            cmd = f"powershell -Command "Try {{ Invoke-WebRequest -Uri http://{LOCALHOST}:{PORT} -UseBasicParsing -TimeoutSec 5; Write-Output '成功'; }} Catch {{ Write-Output $_.Exception.Message }}""
        else:
            # Linux/macOS系统优先使用curl
            cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://{LOCALHOST}:{PORT} --max-time 5"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if system == "Windows":
            output = result.stdout.strip()
            if "成功" in output:
                print(f"✅ WebUI本地访问成功")
                return True
            else:
                print(f"❌ WebUI本地访问失败")
                print(f"  错误信息: {output}")
                return False
        else:
            http_code = result.stdout.strip()
            if http_code.startswith('2') or http_code.startswith('3'):
                print(f"✅ WebUI本地访问成功，HTTP状态码: {http_code}")
                return True
            else:
                print(f"❌ WebUI本地访问失败，HTTP状态码: {http_code or '连接超时'}")
                return False
    except subprocess.TimeoutExpired:
        print(f"❌ WebUI访问超时（10秒）")
        return False
    except Exception as e:
        print(f"❌ 执行访问测试时出错: {e}")
        return False


def get_network_interfaces():
    """获取网络接口信息"""
    print("\n获取网络接口信息...")
    
    system = platform.system()
    try:
        if system == "Windows":
            # Windows系统使用ipconfig
            cmd = "ipconfig"
        else:
            # Linux/macOS系统使用ifconfig或ip
            cmd = "ifconfig -a 2>/dev/null || ip addr"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout.strip())
    except Exception as e:
        print(f"获取网络接口信息失败: {e}")


def get_public_ip():
    """尝试获取公网IP（如果有）"""
    print("\n尝试获取公网IP信息...")
    
    try:
        # 使用多个公共API尝试获取公网IP
        services = [
            "curl -s https://api.ipify.org",
            "curl -s https://ifconfig.me",
            "curl -s https://ipecho.net/plain"
        ]
        
        for service in services:
            try:
                result = subprocess.run(service, shell=True, capture_output=True, text=True, timeout=5)
                if result.stdout.strip():
                    print(f"公网IP: {result.stdout.strip()}")
                    return
            except:
                continue
        
        print("无法获取公网IP信息")
    except Exception as e:
        print(f"获取公网IP失败: {e}")


def print_docker_test_commands():
    """打印Docker测试命令"""
    print("\n=" * 30)
    print("Docker测试命令")
    print("=" * 30)
    
    print("\n1. 检查Docker是否安装并运行:")
    print("   docker --version")
    print("   docker info")
    
    print("\n2. 启动容器（使用端口映射）:")
    print(f"   docker run -d --name strm-poller-test -p {PORT}:{PORT} strm-poller")
    
    print("\n3. 启动容器（使用host网络模式，推荐）:")
    print("   docker run -d --name strm-poller-test --network=host strm-poller")
    
    print("\n4. 查看容器日志:")
    print("   docker logs -f strm-poller-test")
    
    print("\n5. 查看容器网络设置:")
    print("   docker inspect --format='{{json .NetworkSettings}}' strm-poller-test")
    
    print("\n6. 停止并删除测试容器:")
    print("   docker stop strm-poller-test")
    print("   docker rm strm-poller-test")


def print_firewall_test_commands():
    """打印防火墙测试命令"""
    print("\n=" * 30)
    print("防火墙测试命令")
    print("=" * 30)
    
    system = platform.system()
    
    if system == "Windows":
        print("\nWindows防火墙检查:")
        print(f"   netsh advfirewall firewall show rule name=all | findstr \"{PORT}\"")
        print("\n添加Windows防火墙规则:")
        print(f"   netsh advfirewall firewall add rule name=\"STRM Poller\" dir=in action=allow protocol=TCP localport={PORT} remoteip=any profile=any")
    else:
        print("\nLinux防火墙检查 (Ubuntu/Debian - ufw):")
        print("   sudo ufw status")
        print("   sudo ufw show added | grep 35455")
        print(f"   sudo ufw allow {PORT}/tcp")
        
        print("\nLinux防火墙检查 (CentOS/RHEL - firewalld):")
        print("   sudo firewall-cmd --list-ports")
        print(f"   sudo firewall-cmd --permanent --add-port={PORT}/tcp")
        print("   sudo firewall-cmd --reload")


def print_access_urls():
    """打印所有可能的访问URL"""
    print("\n=" * 30)
    print("可能的WebUI访问地址")
    print("=" * 30)
    
    # 获取本机IP地址
    ip_addresses = []
    try:
        # 获取主机名
        hostname = socket.gethostname()
        
        # 获取所有IP地址
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith('127.'):
                ip_addresses.append(ip)
        
        # 如果没找到，尝试另一种方法
        if not ip_addresses:
            for res in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = res[4][0]
                if not ip.startswith('127.'):
                    ip_addresses.append(ip)
        
        # 去重
        ip_addresses = list(set(ip_addresses))
        
        # 添加localhost和0.0.0.0
        print(f"   http://localhost:{PORT}")
        print(f"   http://127.0.0.1:{PORT}")
        print(f"   http://{DEFAULT_HOST}:{PORT}")
        
        # 打印所有发现的IP地址
        for ip in ip_addresses:
            print(f"   http://{ip}:{PORT}")
            
    except Exception as e:
        print(f"获取IP地址信息失败: {e}")
        print(f"请尝试使用: http://localhost:{PORT}")
        print(f"或: http://[您的IP地址]:{PORT}")


def print_troubleshooting_tips():
    """打印故障排除提示"""
    print("\n=" * 30)
    print("故障排除提示")
    print("=" * 30)
    
    tips = [
        "1. 确保STRM Poller服务正在运行",
        "2. 检查35455端口是否已开放",
        "3. 验证防火墙设置是否允许访问35455端口",
        "4. Docker环境下，确保使用了正确的端口映射或host网络模式",
        "5. 检查是否有其他服务占用了35455端口",
        "6. 尝试使用不同的浏览器访问",
        "7. 查看应用日志以获取更多错误信息",
        f"8. 参考文档: docs/FIREWALL_CONFIG.md",
        "9. 对于远程访问，确保网络设备（如路由器）允许端口转发"
    ]
    
    for tip in tips:
        print(f"   {tip}")


def main():
    """主函数"""
    print_header()
    
    # 检查端口监听状态
    is_port_listening = check_port_listening(PORT)
    
    if not is_port_listening:
        # 如果端口未监听，检查端口占用
        check_port_occupation(PORT)
    else:
        # 如果端口在监听，测试WebUI访问
        webui_accessible = test_webui_access()
        
        if not webui_accessible:
            print("\nWebUI访问失败，请检查以下可能的原因:")
            print("  - 应用启动失败但端口已绑定")
            print("  - 应用内部错误")
            print("  - 请查看应用日志以获取更多信息")
    
    # 获取网络配置信息
    get_network_interfaces()
    get_public_ip()
    
    # 打印访问URL
    print_access_urls()
    
    # 打印测试命令
    print_docker_test_commands()
    print_firewall_test_commands()
    
    # 打印故障排除提示
    print_troubleshooting_tips()
    
    print("\n=" * 60)
    print("测试完成！")
    print("如果您仍然无法访问WebUI，请参考上面的故障排除提示。")
    print("如需更多帮助，请检查应用日志或联系技术支持。")
    print("=" * 60)


if __name__ == "__main__":
    main()