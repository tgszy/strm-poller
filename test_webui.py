import requests
import sys
import time

def test_static_files():
    print("=== 测试静态文件访问 ===")
    static_files = [
        "/static/bootstrap-local.css",
        "/static/bootstrap-local.js",
        "/static/js/app.js",
    ]
    
    for file_path in static_files:
        url = f"http://localhost:35455{file_path}"
        try:
            print(f"测试访问: {url}")
            start_time = time.time()
            response = requests.get(url, timeout=5)
            elapsed = time.time() - start_time
            print(f"  状态码: {response.status_code}")
            print(f"  响应时间: {elapsed:.2f}秒")
            print(f"  内容长度: {len(response.content)} 字节")
            if response.status_code == 200:
                print(f"  内容前50字符: {response.content[:50]}")
            print()
        except Exception as e:
            print(f"  访问失败: {str(e)}")
            print()

def test_root_page():
    print("=== 测试根页面访问 ===")
    url = "http://localhost:35455/"
    try:
        response = requests.get(url, timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"内容长度: {len(response.content)} 字节")
        print("\n检查HTML内容中的静态资源引用:")
        
        # 检查修复后的路径
        content = response.text
        if 'src="/static/js/app.js"' in content:
            print("✓ app.js路径已正确修复为绝对路径")
        else:
            print("✗ app.js路径未正确修复")
            
        if 'src="/static/bootstrap-local.js"' in content:
            print("✓ bootstrap-local.js路径已正确修复为绝对路径")
        else:
            print("✗ bootstrap-local.js路径未正确修复")
            
        if 'href="/static/bootstrap-local.css"' in content:
            print("✓ bootstrap-local.css路径已正确修复为绝对路径")
        else:
            print("✗ bootstrap-local.css路径未正确修复")
            
    except Exception as e:
        print(f"访问失败: {str(e)}")

def test_api_health():
    print("\n=== 测试健康检查API ===")
    url = "http://localhost:35455/api/health"
    try:
        response = requests.get(url, timeout=5)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"响应内容: {response.json()}")
    except Exception as e:
        print(f"访问失败: {str(e)}")

def check_server_running():
    print("=== 检查服务器运行状态 ===")
    try:
        response = requests.get("http://localhost:35455/api/health", timeout=3)
        print("✓ 服务器正在运行")
        return True
    except requests.ConnectionError:
        print("✗ 无法连接到服务器，请确认服务是否启动")
        return False
    except Exception as e:
        print(f"✗ 连接出错: {str(e)}")
        return False

if __name__ == "__main__":
    print("WebUI诊断工具\n")
    
    if not check_server_running():
        print("\n请先启动服务器，然后再运行此测试。")
        sys.exit(1)
    
    test_root_page()
    test_static_files()
    test_api_health()
    
    print("\n=== 诊断完成 ===")
    print("请根据上述测试结果分析问题。")