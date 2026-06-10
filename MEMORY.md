# Wallpaper Changer 项目记忆文档

## 项目概述
**目标**: 定时自动更换Fedora 43桌面壁纸，支持多显示器独立配置
**状态**: GUI完成
**开始时间**: 2026-06-10
**完成时间**: 2026-06-10

## 核心需求
1. 支持Fedora 43 Linux桌面（GNOME Wayland）
2. 多显示器（分屏）独立设置壁纸
3. 每个显示器可配置独立的壁纸源文件夹
4. 随机切换壁纸时从各自源文件夹获取
5. 轻量级，Linux友好

## 技术选型
- **语言**: Python 3.14
- **壁纸设置**: gsettings (GNOME Wayland)
- **图片处理**: Pillow
- **配置格式**: TOML
- **打包**: systemd user service
- **GUI框架**: GTK4 + libadwaita

## 关键决策记录
| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-06-10 | 使用Python开发 | 轻量级，Linux生态好 |
| 2026-06-10 | 使用gsettings | GNOME Wayland原生支持 |
| 2026-06-10 | 图片合成方案 | GNOME不支持多壁纸，需合成 |
| 2026-06-10 | TOML配置 | Python 3.11+内置支持 |
| 2026-06-10 | GTK4+libadwaita | GNOME原生UI，现代化外观 |
| 2026-06-10 | D-Bus StatusNotifierItem | 系统托盘，无需AppIndicator3 |

## 里程碑
- [x] M1: 基础功能实现（单显示器壁纸切换）
- [x] M2: 多显示器支持（图片合成）
- [x] M3: 配置管理（TOML配置文件）
- [x] M4: 定时任务集成（systemd service）
- [x] M5: 完善与优化（91个测试通过）
- [x] M6: GUI界面（GTK4 + 系统托盘）

## 项目结构
```
wallpaper_changer/
├── src/wallpaper_changer/
│   ├── __init__.py
│   ├── monitor.py      # 显示器检测
│   ├── wallpaper.py    # 壁纸设置与合成
│   ├── source.py       # 壁纸源管理
│   ├── config.py       # 配置管理
│   ├── scheduler.py    # 定时任务
│   ├── systemd.py      # systemd服务
│   └── cli.py          # CLI接口
├── tests/              # 测试文件
├── config/             # 配置示例
├── MEMORY.md           # 本文件
└── TASK.md             # 任务跟踪
```

## 核心模块
1. **monitor.py**: 检测显示器（Mutter D-Bus/wlr-randr/xrandr）
2. **wallpaper.py**: 设置壁纸（gsettings）和图片合成（Pillow）
3. **source.py**: 管理壁纸源文件夹，随机选择避免重复
4. **config.py**: TOML配置读写
5. **scheduler.py**: 定时任务调度
6. **systemd.py**: systemd service管理
7. **cli.py**: 命令行接口（9个子命令）
8. **gui.py**: GTK4图形界面（4个标签页 + 系统托盘）

## CLI命令
```bash
wallpaper-changer start      # 启动自动轮换
wallpaper-changer stop       # 停止自动轮换
wallpaper-changer next       # 立即切换下一张
wallpaper-changer set <img>  # 设置指定壁纸
wallpaper-changer list       # 列出可用壁纸
wallpaper-changer monitors   # 显示检测到的显示器
wallpaper-changer config     # 查看/编辑配置
wallpaper-changer install    # 安装systemd服务
wallpaper-changer uninstall  # 卸载systemd服务
```

## 测试状态
- 总测试数: 100
- 通过: 100
- 失败: 0

## GUI功能
```bash
# 启动GUI
python -m wallpaper_changer.gui
```
- 壁纸预览与切换
- 源文件夹管理（每个显示器独立配置）
- 定时器设置（间隔、开始/停止）
- 系统托盘图标（右键菜单）
- 最小化到托盘（可配置）

## 下一步
- [x] 创建README文档
- [ ] 添加更多壁纸选项（居中、平铺等）
- [x] 考虑添加GUI界面
- [ ] RPM打包（可选）

## 问题与解决
- GNOME Wayland不支持多显示器独立壁纸 → 使用图片合成方案
- Wayland下feh/nitrogen不可用 → 使用gsettings原生命令
- 需要DBUS_SESSION_BUS_ADDRESS → 从gnome-session获取
