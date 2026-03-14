"""
命令行入口 - 保持向后兼容性
"""

import argparse
import json
import random
import time
import logging
from datetime import datetime
from typing import Optional

from src.core.utils import setup_logging, get_data_dir
from src.core.register import RegistrationEngine
from src.services import EmailServiceFactory, EmailServiceType
from src.database.init_db import initialize_database
from src.config.settings import get_settings


def setup_database():
    """初始化数据库"""
    try:
        initialize_database()
        print("[Info] 数据库初始化完成")
        return True
    except Exception as e:
        print(f"[Error] 数据库初始化失败: {e}")
        return False


def create_tempmail_service(proxy_url: Optional[str] = None):
    """创建 Tempmail 服务"""
    config = {
        "base_url": "https://api.tempmail.lol/v2",
        "timeout": 30,
        "max_retries": 3,
        "proxy_url": proxy_url,
    }

    try:
        service = EmailServiceFactory.create(
            EmailServiceType.TEMPMAIL,
            config,
            name="tempmail_cli"
        )
        print("[Info] Tempmail 服务创建成功")
        return service
    except Exception as e:
        print(f"[Error] 创建 Tempmail 服务失败: {e}")
        return None


def run_registration(proxy: Optional[str] = None) -> Optional[dict]:
    """
    执行一次注册流程

    Args:
        proxy: 代理地址

    Returns:
        注册结果字典，如果失败返回 None
    """
    # 创建邮箱服务
    email_service = create_tempmail_service(proxy)
    if not email_service:
        return None

    # 创建注册引擎
    engine = RegistrationEngine(
        email_service=email_service,
        proxy_url=proxy,
        callback_logger=lambda msg: print(msg)
    )

    # 执行注册
    result = engine.run()

    if result.success:
        # 保存到数据库
        engine.save_to_database(result)

        # 保存到文件（保持向后兼容）
        try:
            t_data = {
                "id_token": result.id_token,
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "account_id": result.account_id,
                "last_refresh": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "email": result.email,
                "type": "codex",
                "expired": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")  # 简化处理
            }

            fname_email = result.email.replace("@", "_")
            file_name = f"token_{fname_email}_{int(time.time())}.json"

            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(t_data, f, ensure_ascii=False, separators=(",", ":"))

            print(f"[*] 成功! Token 已保存至: {file_name}")

        except Exception as e:
            print(f"[Warning] 保存 Token 文件失败: {e}")

        return result.to_dict()
    else:
        print(f"[-] 本次注册失败: {result.error_message}")
        return None


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="OpenAI 自动注册脚本 (重构版本)")
    parser.add_argument(
        "--proxy", default=None, help="代理地址，如 http://127.0.0.1:7890"
    )
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--sleep-min", type=int, default=5, help="循环模式最短等待秒数")
    parser.add_argument(
        "--sleep-max", type=int, default=30, help="循环模式最长等待秒数"
    )
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    parser.add_argument("--log-file", help="日志文件路径")
    args = parser.parse_args()

    # 配置日志
    setup_logging(
        log_level=args.log_level,
        log_file=args.log_file
    )

    # 初始化数据库
    if not setup_database():
        return

    # 参数验证
    sleep_min = max(1, args.sleep_min)
    sleep_max = max(sleep_min, args.sleep_max)

    count = 0
    print("[Info] OpenAI Auto-Registrar")

    while True:
        count += 1
        print(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 开始第 {count} 次注册流程 <<<"
        )

        try:
            result = run_registration(args.proxy)

            if result:
                print(f"[*] 注册成功! 邮箱: {result.get('email')}")
            else:
                print("[-] 本次注册失败。")

        except Exception as e:
            print(f"[Error] 发生未捕获异常: {e}")

        if args.once:
            break

        wait_time = random.randint(sleep_min, sleep_max)
        print(f"[*] 休息 {wait_time} 秒...")
        time.sleep(wait_time)


if __name__ == "__main__":
    main()