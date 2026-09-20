# 配网报告部署说明

## 推荐部署方式

正式项目只在一台受控的 Windows 服务电脑上运行服务，现场用户通过浏览器访问。现场用户不需要安装 Python，也不需要知道 Oracle 账号密码。

```text
现场浏览器  ──HTTP/HTTPS──>  报告服务电脑  ──Oracle──>  D5000 数据库
```

不要把 Oracle 账号密码发给现场人员，也不要把数据库端口暴露到现场网络或互联网。

正式发布时建议使用打包后的 `配网信号测试报告.exe`。现场电脑不需要安装 Python、pip 或虚拟环境。

## 交付目录

发布包中应包含：

```text
distribution-signal-verifier/
├─ e2e_report.html
├─ distribution_signal_verifier.py
├─ live_report_server.py
├─ start_distribution_report.ps1
├─ setup.ps1
├─ requirements.txt
├─ pyproject.toml
└─ 配网报告配置.json
```

不要把包含真实密码的配置文件交给无权限人员，也不要交付 `.venv/`、临时导出的敏感数据、`__pycache__/`、`build/`、`dist/`。

`e2e_report.html` 放在 `start_distribution_report.ps1` 同目录后，启动脚本可以脱离原开发机路径运行。

## 在服务电脑上首次安装

```powershell
Set-Location D:\Apps\distribution-signal-verifier
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

如果电脑没有 Python 3.10 或更高版本，需要先安装 Python，并勾选加入 PATH。

## 配置文件

直接编辑发布包中的 `配网报告配置.json`，只在服务电脑保存 Oracle 主机、Service Name、账号和密码。这个文件不发给现场普通用户，也不要提交到代码仓库。

配置示例：

```json
{
  "server": { "host": "0.0.0.0", "port": 8787, "template": "e2e_report.html" },
  "oracle": {
    "host": "数据库主机",
    "port": 1521,
    "service": "服务名",
    "user": "数据库账号",
    "password": "数据库密码"
  }
}
```

## 启动服务

### EXE 发布包

填写配置文件后，以后直接双击或执行一条命令：

```powershell
.\配网信号测试报告.exe
```

EXE 默认读取 JSON 中的监听地址、端口和模板路径，并自动打开本机浏览器。

```powershell
.\配网信号测试报告.exe --port 8788
```

### 源码模式

配置完成后，最简单的启动方式是执行一个命令：

```powershell
.\run_distribution_report.ps1 -ListenAddress 0.0.0.0 -Port 8787
```

第一次运行会自动创建虚拟环境、安装依赖并执行测试；以后直接启动服务。Oracle 配置仍需要管理员首次填写一次。

仅本机使用：

```powershell
.\start_distribution_report.ps1
```

同一局域网的现场电脑访问：

```powershell
.\start_distribution_report.ps1 -ListenAddress 0.0.0.0 -Port 8787
```

现场用户打开：

```text
http://服务电脑的局域网IP:8787/?network=distribution
```

例如：`http://192.168.1.20:8787/?network=distribution`。

用户在页面输入 RMU 名称，例如 `34661`，点击“搜索数据库”。

## 正式发布建议

只在服务电脑的 Windows 防火墙中为内网开放 TCP 8787，不要开放到公网。正式项目建议接入公司现有的 HTTPS 反向代理和统一认证。

多个现场优先使用一台中心服务；如果各现场访问不同 Oracle，则每个现场部署一台服务电脑，并分别配置本地的 `配网报告配置.json`。

## 停止服务

启动脚本会输出实际进程号：

```powershell
Stop-Process -Id 12345
```

## 正式发布前检查

```powershell
python -m unittest discover -v
```

确认 `34661` 能查到 RMU 映射、50 个三遥点，并确认报告编号、表号、SMART、NOP 和 IEC-104 信息正确。