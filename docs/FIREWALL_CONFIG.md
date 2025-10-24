# 防火墙配置指南

为确保STRM Poller的WebUI能够正常被访问，需要在系统防火墙中开放35455端口。本指南提供了在不同操作系统上配置防火墙的详细步骤。

## Windows系统

### 方法1：使用管理员权限运行命令提示符

1. **以管理员身份打开命令提示符**：
   - 右键点击"开始"菜单
   - 选择"Windows PowerShell (管理员)"或"命令提示符 (管理员)"

2. **执行以下命令开放35455端口**：
   ```powershell
   netsh advfirewall firewall add rule name="STRM Poller - WebUI" dir=in action=allow protocol=TCP localport=35455 remoteip=any profile=any
   ```

3. **验证规则是否添加成功**：
   ```powershell
   netsh advfirewall firewall show rule name="STRM Poller - WebUI"
   ```

### 方法2：通过Windows Defender防火墙设置

1. **打开Windows Defender防火墙**：
   - 搜索并打开"Windows Defender 防火墙"

2. **点击"高级设置"**

3. **在左侧面板选择"入站规则"**，然后在右侧面板点击"新建规则..."

4. **规则类型选择"端口"**，点击"下一步"

5. **选择"TCP"**，然后在"特定本地端口"中输入`35455`，点击"下一步"

6. **选择"允许连接"**，点击"下一步"

7. **选择应用规则的网络位置**（建议全部勾选），点击"下一步"

8. **为规则命名**（例如："STRM Poller - WebUI"），添加描述（可选），点击"完成"

## Linux系统

### Ubuntu/Debian (使用ufw)

1. **开放35455端口**：
   ```bash
   sudo ufw allow 35455/tcp
   ```

2. **重新加载防火墙规则**：
   ```bash
   sudo ufw reload
   ```

3. **验证规则是否添加成功**：
   ```bash
   sudo ufw status
   ```

### CentOS/RHEL/Fedora (使用firewalld)

1. **开放35455端口**：
   ```bash
   sudo firewall-cmd --permanent --add-port=35455/tcp
   ```

2. **重新加载防火墙规则**：
   ```bash
   sudo firewall-cmd --reload
   ```

3. **验证规则是否添加成功**：
   ```bash
   sudo firewall-cmd --list-ports
   ```

## macOS系统

### 使用终端

1. **开放35455端口**：
   ```bash
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /path/to/your/application
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /path/to/your/application
   ```

   或者，使用pfctl（更高级的方法）：
   ```bash
   echo "pass in proto tcp from any to any port 35455" | sudo pfctl -ef -
   ```

### 通过系统偏好设置

1. **打开"系统偏好设置"** > "安全性与隐私" > "防火墙"

2. **点击锁图标并输入管理员密码解锁设置**

3. **点击"防火墙选项..."**

4. **添加STRM Poller应用并允许传入连接**

## Docker环境中的特殊配置

### 确保容器端口映射正确

1. **使用-p参数映射端口**：
   ```bash
   docker run -p 35455:35455 your-image-name
   ```

2. **或使用--network=host直接使用主机网络**（推荐用于本地开发）：
   ```bash
   docker run --network=host your-image-name
   ```

3. **或在docker-compose.yml中正确配置**：
   ```yaml
   services:
     strm-poller:
       ports:
         - "35455:35455"
       # 或者使用host网络模式
       # network_mode: "host"
   ```

## 验证端口是否开放成功

配置完成后，可以使用以下方法验证端口是否开放成功：

### Windows/Linux/macOS通用方法

1. **使用telnet命令**（部分系统可能需要安装）：
   ```bash
   telnet localhost 35455
   ```

2. **使用netcat命令**（nc）：
   ```bash
   nc -zv localhost 35455
   ```

3. **使用PowerShell测试连接**（Windows）：
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 35455
   ```

4. **从另一台设备访问**：
   ```
   http://[服务器IP地址]:35455
   ```

## 常见问题排查

1. **端口已被占用**：
   - 检查哪个进程占用了35455端口
   - Windows: `netstat -ano | findstr :35455`
   - Linux/macOS: `lsof -i :35455` 或 `netstat -tulpn | grep :35455`

2. **防火墙规则已添加但仍然无法访问**：
   - 确保使用正确的IP地址访问（不是localhost而是服务器的实际IP）
   - 检查是否有多层防火墙（如公司网络、路由器防火墙等）
   - 尝试临时禁用防火墙测试是否为防火墙问题

3. **Docker容器中无法访问**：
   - 确保容器正在运行：`docker ps`
   - 检查容器日志：`docker logs [container-id]`
   - 尝试使用host网络模式
   - 检查Docker网络配置

如果遇到其他防火墙相关问题，请参考您的操作系统文档或联系系统管理员寻求帮助。