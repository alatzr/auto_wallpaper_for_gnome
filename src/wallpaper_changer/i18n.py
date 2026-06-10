"""Simple i18n module for wallpaper-changer GUI."""

import locale
from typing import Optional

TRANSLATIONS = {
    'en': {
        'app_title': 'Wallpaper Changer',
        'tab_preview': 'Preview',
        'tab_sources': 'Sources',
        'tab_timer': 'Timer',
        'tab_settings': 'Settings',
        'btn_previous': 'Previous',
        'btn_random': 'Random',
        'btn_next': 'Next',
        'monitor_primary': '(primary)',
        'label_monitor': 'Monitor',
        'label_source_folder': 'Source Folder',
        'btn_browse': 'Browse',
        'btn_save': 'Save',
        'btn_refresh': 'Refresh Monitors',
        'btn_add_folder': 'Add Monitor Folder',
        'label_interval': 'Interval',
        'label_change_every': 'Change every (seconds)',
        'label_scheduler': 'Scheduler',
        'label_systemd': 'Systemd Service',
        'label_install_service': 'Install as user service',
        'btn_start': 'Start',
        'btn_stop': 'Stop',
        'label_status': 'Status',
        'status_running': 'Running',
        'status_stopped': 'Stopped',
        'status_paused': 'Paused',
        'label_scaling': 'Wallpaper Scaling',
        'label_scaling_option': 'Scaling option',
        'label_system_tray': 'System Tray',
        'label_minimize_tray': 'Minimize to tray on close',
        'label_language': 'Language',
        'btn_apply': 'Apply',
        'btn_reset': 'Reset',
        'label_wallpaper': 'Wallpaper',
        'option_scaled': 'Scaled',
        'option_stretched': 'Stretched',
        'option_zoom': 'Zoom',
        'option_centered': 'Centered',
        'option_wallpaper': 'Tiled',
        'option_spanned': 'Spanned',
        'option_none': 'None',
        'tray_next': 'Next Wallpaper',
        'tray_pause': 'Pause',
        'tray_resume': 'Resume',
        'tray_show': 'Show Window',
        'tray_quit': 'Quit',
        'msg_saved': 'Settings saved',
        'msg_error': 'Error',
        'menu_about': 'About',
    },
    'zh': {
        'app_title': '壁纸更换器',
        'tab_preview': '预览',
        'tab_sources': '源文件夹',
        'tab_timer': '定时器',
        'tab_settings': '设置',
        'btn_previous': '上一张',
        'btn_random': '随机',
        'btn_next': '下一张',
        'monitor_primary': '(主显示器)',
        'label_monitor': '显示器',
        'label_source_folder': '源文件夹',
        'btn_browse': '浏览',
        'btn_save': '保存',
        'btn_refresh': '刷新显示器',
        'btn_add_folder': '添加显示器文件夹',
        'label_interval': '间隔',
        'label_change_every': '更换间隔（秒）',
        'label_scheduler': '调度器',
        'label_systemd': '系统服务',
        'label_install_service': '安装为用户服务',
        'btn_start': '开始',
        'btn_stop': '停止',
        'label_status': '状态',
        'status_running': '运行中',
        'status_stopped': '已停止',
        'status_paused': '已暂停',
        'label_scaling': '壁纸缩放',
        'label_scaling_option': '缩放选项',
        'label_system_tray': '系统托盘',
        'label_minimize_tray': '关闭时最小化到托盘',
        'label_language': '语言',
        'btn_apply': '应用',
        'btn_reset': '重置',
        'label_wallpaper': '壁纸',
        'option_scaled': '缩放',
        'option_stretched': '拉伸',
        'option_zoom': '缩放填充',
        'option_centered': '居中',
        'option_wallpaper': '平铺',
        'option_spanned': '跨屏',
        'option_none': '无',
        'tray_next': '下一张壁纸',
        'tray_pause': '暂停',
        'tray_resume': '继续',
        'tray_show': '显示窗口',
        'tray_quit': '退出',
        'msg_saved': '设置已保存',
        'msg_error': '错误',
        'menu_about': '关于',
    },
}

_current_lang = 'en'


def get_system_language() -> str:
    try:
        lang = locale.getdefaultlocale()[0]
        if lang and lang.startswith('zh'):
            return 'zh'
    except Exception:
        pass
    return 'en'


def set_language(lang: str) -> None:
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    return _current_lang


def t(key: str) -> str:
    return TRANSLATIONS.get(_current_lang, TRANSLATIONS['en']).get(key, key)


def init_i18n() -> None:
    global _current_lang
    _current_lang = get_system_language()
