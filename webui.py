"""
Web UI 启动入口
"""

import uvicorn
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.utils import setup_logging
from src.database.init_db import initialize_database
from src.config.settings import get_settings


def setup_application():
    """设置应用程序"""
    # 初始化数据库（必须先于获取设置）
    try:
        initialize_database()
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise

    # 获取配置（需要数据库已初始化）
    settings = get_settings()

    # 配置日志
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file
    )

    logger = logging.getLogger(__name__)
    logger.info("数据库初始化完成")

    # 检查数据目录
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    logger.info(f"数据目录: {data_dir}")

    # 检查日志目录
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    logger.info(f"日志目录: {logs_dir}")

    logger.info("应用程序设置完成")
    return settings


def start_webui():
    """启动 Web UI"""
    # 设置应用程序
    settings = setup_application()

    # 导入 FastAPI 应用（延迟导入以避免循环依赖）
    from src.web.app import app

    # 配置 uvicorn
    uvicorn_config = {
        "app": "src.web.app:app",
        "host": settings.webui_host,
        "port": settings.webui_port,
        "reload": settings.debug,
        "log_level": "info" if settings.debug else "warning",
        "access_log": settings.debug,
    }

    logger = logging.getLogger(__name__)
    logger.info(f"启动 Web UI 在 http://{settings.webui_host}:{settings.webui_port}")
    logger.info(f"调试模式: {settings.debug}")

    # 启动服务器
    uvicorn.run(**uvicorn_config)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenAI/Codex CLI 自动注册系统 Web UI")
    parser.add_argument("--host", help="监听主机")
    parser.add_argument("--port", type=int, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--reload", action="store_true", help="启用热重载")
    parser.add_argument("--log-level", help="日志级别")
    args = parser.parse_args()

    # 更新配置
    from src.config.settings import update_settings

    updates = {}
    if args.host:
        updates["webui_host"] = args.host
    if args.port:
        updates["webui_port"] = args.port
    if args.debug:
        updates["debug"] = args.debug
    if args.log_level:
        updates["log_level"] = args.log_level

    if updates:
        update_settings(**updates)

    # 启动 Web UI
    start_webui()


if __name__ == "__main__":
    main()