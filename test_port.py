import socket
import subprocess
import sys

def test_port_connectivity(host='localhost', port=35455):
    print(f"测试 {host}:{port} 的端口连接性...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ 成功连接到 {host}:{port}")
            return True
        else:
            print(f"✗ 无法连接到 {host}:{port} (错误代码: {result})")
            return False
    except Exception as e:
        print(f"✗ 连接出错: {str(e)}")
        return False

def check_process_running(process_name='uvicorn'):
    print(f"\n检查进程 '{process_name}' 是否在运行...")
    try:
        # 使用tasklist命令查找进程
        output = subprocess.check_output('tasklist', shell=True).decode()
        processes = [line.split()[0] for line in output.splitlines()[3:]]
        
        # 检查Python进程，因为uvicorn是作为Python模块运行的
        python_processes = [p for p in processes if 'python' in p.lower()]
        if python_processes:
            print(f"✓ 发现运行中的Python进程: {', '.join(python_processes)}")
            return True
        else:
            print(f"✗ 未发现运行中的Python进程")
            return False
    except Exception as e:
        print(f"✗ 检查进程失败: {str(e)}")
        return False

def check_port_binding():
    print("\n检查端口绑定情况...")
    try:
        # 使用netstat命令检查端口占用
        output = subprocess.check_output('netstat -ano | findstr :35455', shell=True).decode()
        if output.strip():
            print("✓ 发现端口35455被占用:")
            print(output)
            return True
        else:
            print("✗ 端口35455未被占用")
            return False
    except subprocess.CalledProcessError:
        print("✗ 端口35455未被占用")
        return False
    except Exception as e:
        print(f"✗ 检查端口失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("端口连接性测试工具\n")
    
    # 测试本地回环地址
    print("=== 测试本地连接 ===")
    localhost_connected = test_port_connectivity('localhost', 35455)
    
    # 测试127.0.0.1
    test_port_connectivity('127.0.0.1', 35455)
    
    # 测试可能的局域网IP
    test_port_connectivity('192.168.153.1', 35455)
    
    # 检查进程和端口
    process_running = check_process_running()
    port_bound = check_port_binding()
    
    print("\n=== 测试总结 ===")
    print(f"服务器进程: {'运行中' if process_running else '未运行'}")
    print(f"端口绑定: {'已绑定' if port_bound else '未绑定'}")
    print(f"本地连接: {'成功' if localhost_connected else '失败'}")
    
    if process_running and port_bound and not localhost_connected:
        print("\n可能的问题:")
        print("1. 防火墙可能阻止了连接")
        print("2. 网络配置问题")
        print("3. 服务器绑定到了错误的接口")
    elif not process_running:
        print("\n请确保服务器正在运行。")
    elif not port_bound:
        print("\n端口未绑定，请检查服务器配置。")