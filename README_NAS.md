# strm-poller服务部署和访问指南

## 概述

本指南提供了部署和访问strm-poller服务的详细步骤，适用于各种环境配置。

## 1. 网络配置检查

### 1.1 主机网络设置

1. **确认主机IP地址**：
   - 确认运行服务的主机局域网IP地址（通常为192.168.x.x格式）
   - 推荐设置静态IP地址，避免IP变更导致服务访问中断
   - 服务会自动检测并显示可用的局域网IP地址

2. **防火墙配置**：
   - 确保主机防火墙允许端口35455的入站连接
   - 对于Linux系统，使用ufw或iptables添加规则
   - 对于Windows系统，在防火墙高级设置中添加入站规则
   - 对于NAS设备，在各自的控制面板安全设置中添加例外

### 1.2 局域网访问测试

在访问服务前，先测试网络连接：

```bash
# 在Windows命令提示符中，替换[NAS_IP]为您的NAS实际IP地址
ping [NAS_IP]

# 检查端口是否可访问
Test-NetConnection -ComputerName [NAS_IP] -Port 35455
```

## 2. Docker部署配置

### 2.1 支持的网络模式

我们提供两种网络模式配置：

1. **Host网络模式（推荐）**：
   - 直接使用主机网络栈，性能更好
   - 无需端口映射，服务直接监听主机端口
   - 使用docker-compose.yml文件

2. **Bridge网络模式**：
   - 使用独立的网络隔离
   - 需要配置端口映射35455:35455
   - 使用docker-compose-bridge.yml文件

### 2.2 部署步骤

1. **复制配置文件**：
   - 将docker-compose.yml和docker-compose-bridge.yml复制到部署目录

2. **使用Host网络模式启动（推荐）**：

```bash
# 进入配置文件所在目录
docker-compose down
docker-compose up -d
```

3. **或使用Bridge网络模式启动**：

```bash
# 进入配置文件所在目录
docker-compose -f docker-compose-bridge.yml down
docker-compose -f docker-compose-bridge.yml up -d
```

3. **验证容器状态**：

```bash
docker-compose ps
docker-compose logs -f --tail 100
```

## 3. 访问方法

### 3.1 WebUI访问

服务启动后，会自动检测并显示可用的访问地址：

1. 查看容器日志获取推荐访问地址：
   ```bash
   docker-compose logs | grep "推荐访问地址"
   ```

2. 访问显示的地址，格式通常为：
   ```
   http://[主机局域网IP]:35455/
   ```

### 3.2 替代访问方式

如果直接IP访问失败，尝试以下替代方式：

1. **使用主机名**：
   ```
   http://[主机名]:35455/
   ```

2. **尝试其他IP地址**：
   - 检查主机可能的其他网络接口IP
   - 查看docker-compose logs中的"可用访问地址"部分

## 4. 故障排除

### 4.1 常见问题排查

1. **无法访问WebUI**：
   - 检查防火墙设置
   - 验证容器是否正常运行
   - 检查服务日志中的错误信息

2. **静态文件加载失败**：
   - 服务已自动添加回退机制
   - 查看日志中的"静态文件目录"相关信息

3. **容器启动失败**：
   - 检查端口是否被占用
   - 验证文件权限
   - 查看详细错误日志

### 4.2 日志分析

服务日志包含详细的网络诊断信息：

```bash
docker-compose logs --grep "network" --grep "IP" --grep "address"
```

查找关键信息：
- 监听地址和端口
- 检测到的网络接口
- NAS环境识别状态
- 可用访问地址列表

### 4.3 网络诊断命令

在NAS上执行以下命令进行诊断：

```bash
# 检查容器网络配置
docker inspect strm-poller | grep -A 20 "NetworkSettings"

# 检查端口监听
docker exec strm-poller netstat -tulpn

# 从容器内部测试连接
docker exec -it strm-poller curl -v http://localhost:35455/
```

## 5. 高级配置

### 5.1 环境变量调优

根据NAS性能调整以下环境变量：

```yaml
environment:
  - NAS_ENV=true
  # NAS_HOST_IP已不再需要，服务会自动检测内网IP
  - WORKER_COUNT=4  # 根据CPU核心数调整
  - MAX_CONNECTIONS=100  # 根据内存调整
  - NETWORK_TIMEOUT=60  # 网络超时时间
```

**重要提示**：无需手动设置NAS_HOST_IP，服务会自动检测所有可用的网络接口和IP地址，并推荐最佳的访问地址。

### 5.2 网络模式切换

如果bridge模式仍有问题，可尝试host网络模式：

```yaml
version: '3.8'
services:
  strm-poller:
    # ...
    network_mode: "host"
    # 移除ports配置，因为host模式下不需要端口映射
    # ports:
    #   - "35455:35455"
    # ...
```

## 6. 最佳实践

1. **定期检查更新**：
   - 监控容器镜像更新
   - 定期重启服务以应用配置更改

2. **备份配置**：
   - 定期备份docker-compose.yml文件
   - 备份重要数据和配置文件

3. **性能监控**：
   - 监控容器CPU和内存使用情况
   - 根据需要调整资源限制

---

按照本指南配置后，您应该能够顺利地通过局域网IP访问您的strm-poller服务。如果仍有问题，请参考日志中的详细诊断信息或寻求进一步支持。