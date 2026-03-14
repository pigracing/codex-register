"""
设置 API 路由
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...database import crud
from ...database.session import get_db
from ...config.settings import get_settings, update_settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ============== Pydantic Models ==============

class SettingItem(BaseModel):
    """设置项"""
    key: str
    value: str
    description: Optional[str] = None
    category: str = "general"


class SettingUpdateRequest(BaseModel):
    """设置更新请求"""
    value: str


class ProxySettings(BaseModel):
    """代理设置"""
    enabled: bool = False
    type: str = "http"  # http, socks5
    host: str = "127.0.0.1"
    port: int = 7890
    username: Optional[str] = None
    password: Optional[str] = None


class RegistrationSettings(BaseModel):
    """注册设置"""
    max_retries: int = 3
    timeout: int = 120
    default_password_length: int = 12
    sleep_min: int = 5
    sleep_max: int = 30


class WebUISettings(BaseModel):
    """Web UI 设置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class AllSettings(BaseModel):
    """所有设置"""
    proxy: ProxySettings
    registration: RegistrationSettings
    webui: WebUISettings


# ============== API Endpoints ==============

@router.get("")
async def get_all_settings():
    """获取所有设置"""
    settings = get_settings()

    return {
        "proxy": {
            "enabled": settings.proxy_enabled,
            "type": settings.proxy_type,
            "host": settings.proxy_host,
            "port": settings.proxy_port,
            "username": settings.proxy_username,
            "has_password": bool(settings.proxy_password),
        },
        "registration": {
            "max_retries": settings.registration_max_retries,
            "timeout": settings.registration_timeout,
            "default_password_length": settings.registration_default_password_length,
            "sleep_min": settings.registration_sleep_min,
            "sleep_max": settings.registration_sleep_max,
        },
        "webui": {
            "host": settings.webui_host,
            "port": settings.webui_port,
            "debug": settings.debug,
        },
        "tempmail": {
            "base_url": settings.tempmail_base_url,
            "timeout": settings.tempmail_timeout,
            "max_retries": settings.tempmail_max_retries,
        },
        "email_code": {
            "timeout": settings.email_code_timeout,
            "poll_interval": settings.email_code_poll_interval,
        },
    }


@router.get("/proxy")
async def get_proxy_settings():
    """获取代理设置"""
    settings = get_settings()

    return {
        "enabled": settings.proxy_enabled,
        "type": settings.proxy_type,
        "host": settings.proxy_host,
        "port": settings.proxy_port,
        "username": settings.proxy_username,
        "has_password": bool(settings.proxy_password),
        "proxy_url": settings.proxy_url,
    }


@router.post("/proxy")
async def update_proxy_settings(request: ProxySettings):
    """更新代理设置"""
    update_dict = {
        "proxy_enabled": request.enabled,
        "proxy_type": request.type,
        "proxy_host": request.host,
        "proxy_port": request.port,
        "proxy_username": request.username,
    }

    if request.password:
        update_dict["proxy_password"] = request.password

    update_settings(**update_dict)

    return {"success": True, "message": "代理设置已更新"}


@router.post("/proxy/test")
async def test_proxy_settings(request: ProxySettings):
    """测试代理连接"""
    import time
    from curl_cffi import requests as cffi_requests

    # 构建代理 URL
    if request.type == "http":
        scheme = "http"
    elif request.type == "socks5":
        scheme = "socks5"
    else:
        raise HTTPException(status_code=400, detail="不支持的代理类型")

    auth = ""
    if request.username and request.password:
        auth = f"{request.username}:{request.password}@"

    proxy_url = f"{scheme}://{auth}{request.host}:{request.port}"

    # 测试连接
    test_url = "https://api.ipify.org?format=json"
    start_time = time.time()

    try:
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        response = cffi_requests.get(
            test_url,
            proxies=proxies,
            timeout=3,
            impersonate="chrome110"
        )

        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            ip_info = response.json()
            return {
                "success": True,
                "ip": ip_info.get("ip", ""),
                "response_time": round(elapsed_time * 1000),  # 毫秒
                "message": f"代理连接成功，出口 IP: {ip_info.get('ip', 'unknown')}"
            }
        else:
            return {
                "success": False,
                "message": f"代理返回错误状态码: {response.status_code}"
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"代理连接失败: {str(e)}"
        }


@router.get("/registration")
async def get_registration_settings():
    """获取注册设置"""
    settings = get_settings()

    return {
        "max_retries": settings.registration_max_retries,
        "timeout": settings.registration_timeout,
        "default_password_length": settings.registration_default_password_length,
        "sleep_min": settings.registration_sleep_min,
        "sleep_max": settings.registration_sleep_max,
    }


@router.post("/registration")
async def update_registration_settings(request: RegistrationSettings):
    """更新注册设置"""
    update_settings(
        registration_max_retries=request.max_retries,
        registration_timeout=request.timeout,
        registration_default_password_length=request.default_password_length,
        registration_sleep_min=request.sleep_min,
        registration_sleep_max=request.sleep_max,
    )

    return {"success": True, "message": "注册设置已更新"}


@router.get("/database")
async def get_database_info():
    """获取数据库信息"""
    settings = get_settings()

    import os
    from pathlib import Path

    db_path = settings.database_url
    if db_path.startswith("sqlite:///"):
        db_path = db_path[10:]

    db_file = Path(db_path) if os.path.isabs(db_path) else Path(db_path)
    db_size = db_file.stat().st_size if db_file.exists() else 0

    with get_db() as db:
        from ...database.models import Account, EmailService, RegistrationTask

        account_count = db.query(Account).count()
        service_count = db.query(EmailService).count()
        task_count = db.query(RegistrationTask).count()

    return {
        "database_url": settings.database_url,
        "database_size_bytes": db_size,
        "database_size_mb": round(db_size / (1024 * 1024), 2),
        "accounts_count": account_count,
        "email_services_count": service_count,
        "tasks_count": task_count,
    }


@router.post("/database/backup")
async def backup_database():
    """备份数据库"""
    import shutil
    from datetime import datetime

    settings = get_settings()

    db_path = settings.database_url
    if db_path.startswith("sqlite:///"):
        db_path = db_path[10:]

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    # 创建备份目录
    backup_dir = Path(db_path).parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"database_backup_{timestamp}.db"

    # 复制数据库文件
    shutil.copy2(db_path, backup_path)

    return {
        "success": True,
        "message": "数据库备份成功",
        "backup_path": str(backup_path)
    }


@router.post("/database/cleanup")
async def cleanup_database(
    days: int = 30,
    keep_failed: bool = True
):
    """清理过期数据"""
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    with get_db() as db:
        from ...database.models import RegistrationTask
        from sqlalchemy import delete

        # 删除旧任务
        conditions = [RegistrationTask.created_at < cutoff_date]
        if not keep_failed:
            conditions.append(RegistrationTask.status != "failed")
        else:
            conditions.append(RegistrationTask.status.in_(["completed", "cancelled"]))

        result = db.execute(
            delete(RegistrationTask).where(*conditions)
        )
        db.commit()

        deleted_count = result.rowcount

    return {
        "success": True,
        "message": f"已清理 {deleted_count} 条过期任务记录",
        "deleted_count": deleted_count
    }


@router.get("/logs")
async def get_recent_logs(
    lines: int = 100,
    level: str = "INFO"
):
    """获取最近日志"""
    settings = get_settings()

    log_file = settings.log_file
    if not log_file:
        return {"logs": [], "message": "日志文件未配置"}

    from pathlib import Path
    log_path = Path(log_file)

    if not log_path.exists():
        return {"logs": [], "message": "日志文件不存在"}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]

        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines)
        }
    except Exception as e:
        return {"logs": [], "error": str(e)}


# ============== 临时邮箱设置 ==============

class TempmailSettings(BaseModel):
    """临时邮箱设置"""
    api_url: Optional[str] = None
    enabled: bool = True


class EmailCodeSettings(BaseModel):
    """验证码等待设置"""
    timeout: int = 120  # 验证码等待超时（秒）
    poll_interval: int = 3  # 验证码轮询间隔（秒）


@router.get("/tempmail")
async def get_tempmail_settings():
    """获取临时邮箱设置"""
    settings = get_settings()

    return {
        "api_url": settings.tempmail_base_url,
        "timeout": settings.tempmail_timeout,
        "max_retries": settings.tempmail_max_retries,
        "enabled": True  # 临时邮箱默认可用
    }


@router.post("/tempmail")
async def update_tempmail_settings(request: TempmailSettings):
    """更新临时邮箱设置"""
    update_dict = {}

    if request.api_url:
        update_dict["tempmail_base_url"] = request.api_url

    update_settings(**update_dict)

    return {"success": True, "message": "临时邮箱设置已更新"}


# ============== 验证码等待设置 ==============

@router.get("/email-code")
async def get_email_code_settings():
    """获取验证码等待设置"""
    settings = get_settings()
    return {
        "timeout": settings.email_code_timeout,
        "poll_interval": settings.email_code_poll_interval,
    }


@router.post("/email-code")
async def update_email_code_settings(request: EmailCodeSettings):
    """更新验证码等待设置"""
    # 验证参数范围
    if request.timeout < 30 or request.timeout > 600:
        raise HTTPException(status_code=400, detail="超时时间必须在 30-600 秒之间")
    if request.poll_interval < 1 or request.poll_interval > 30:
        raise HTTPException(status_code=400, detail="轮询间隔必须在 1-30 秒之间")

    update_settings(
        email_code_timeout=request.timeout,
        email_code_poll_interval=request.poll_interval,
    )

    return {"success": True, "message": "验证码等待设置已更新"}


# ============== 代理列表 CRUD ==============

class ProxyCreateRequest(BaseModel):
    """创建代理请求"""
    name: str
    type: str = "http"  # http, socks5
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: bool = True
    priority: int = 0


class ProxyUpdateRequest(BaseModel):
    """更新代理请求"""
    name: Optional[str] = None
    type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


@router.get("/proxies")
async def get_proxies_list(enabled: Optional[bool] = None):
    """获取代理列表"""
    with get_db() as db:
        proxies = crud.get_proxies(db, enabled=enabled)
        return {
            "proxies": [p.to_dict() for p in proxies],
            "total": len(proxies)
        }


@router.post("/proxies")
async def create_proxy_item(request: ProxyCreateRequest):
    """创建代理"""
    with get_db() as db:
        proxy = crud.create_proxy(
            db,
            name=request.name,
            type=request.type,
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            enabled=request.enabled,
            priority=request.priority
        )
        return {"success": True, "proxy": proxy.to_dict()}


@router.get("/proxies/{proxy_id}")
async def get_proxy_item(proxy_id: int):
    """获取单个代理"""
    with get_db() as db:
        proxy = crud.get_proxy_by_id(db, proxy_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="代理不存在")
        return proxy.to_dict(include_password=True)


@router.patch("/proxies/{proxy_id}")
async def update_proxy_item(proxy_id: int, request: ProxyUpdateRequest):
    """更新代理"""
    with get_db() as db:
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.type is not None:
            update_data["type"] = request.type
        if request.host is not None:
            update_data["host"] = request.host
        if request.port is not None:
            update_data["port"] = request.port
        if request.username is not None:
            update_data["username"] = request.username
        if request.password is not None:
            update_data["password"] = request.password
        if request.enabled is not None:
            update_data["enabled"] = request.enabled
        if request.priority is not None:
            update_data["priority"] = request.priority

        proxy = crud.update_proxy(db, proxy_id, **update_data)
        if not proxy:
            raise HTTPException(status_code=404, detail="代理不存在")
        return {"success": True, "proxy": proxy.to_dict()}


@router.delete("/proxies/{proxy_id}")
async def delete_proxy_item(proxy_id: int):
    """删除代理"""
    with get_db() as db:
        success = crud.delete_proxy(db, proxy_id)
        if not success:
            raise HTTPException(status_code=404, detail="代理不存在")
        return {"success": True, "message": "代理已删除"}


@router.post("/proxies/{proxy_id}/test")
async def test_proxy_item(proxy_id: int):
    """测试单个代理"""
    import time
    from curl_cffi import requests as cffi_requests

    with get_db() as db:
        proxy = crud.get_proxy_by_id(db, proxy_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="代理不存在")

        proxy_url = proxy.proxy_url
        test_url = "https://api.ipify.org?format=json"
        start_time = time.time()

        try:
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }

            response = cffi_requests.get(
                test_url,
                proxies=proxies,
                timeout=3,
                impersonate="chrome110"
            )

            elapsed_time = time.time() - start_time

            if response.status_code == 200:
                ip_info = response.json()
                return {
                    "success": True,
                    "ip": ip_info.get("ip", ""),
                    "response_time": round(elapsed_time * 1000),
                    "message": f"代理连接成功，出口 IP: {ip_info.get('ip', 'unknown')}"
                }
            else:
                return {
                    "success": False,
                    "message": f"代理返回错误状态码: {response.status_code}"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"代理连接失败: {str(e)}"
            }


@router.post("/proxies/test-all")
async def test_all_proxies():
    """测试所有启用的代理"""
    import time
    from curl_cffi import requests as cffi_requests

    with get_db() as db:
        proxies = crud.get_enabled_proxies(db)

        results = []
        for proxy in proxies:
            proxy_url = proxy.proxy_url
            test_url = "https://api.ipify.org?format=json"
            start_time = time.time()

            try:
                proxies_dict = {
                    "http": proxy_url,
                    "https": proxy_url
                }

                response = cffi_requests.get(
                    test_url,
                    proxies=proxies_dict,
                    timeout=3,
                    impersonate="chrome110"
                )

                elapsed_time = time.time() - start_time

                if response.status_code == 200:
                    ip_info = response.json()
                    results.append({
                        "id": proxy.id,
                        "name": proxy.name,
                        "success": True,
                        "ip": ip_info.get("ip", ""),
                        "response_time": round(elapsed_time * 1000)
                    })
                else:
                    results.append({
                        "id": proxy.id,
                        "name": proxy.name,
                        "success": False,
                        "message": f"状态码: {response.status_code}"
                    })

            except Exception as e:
                results.append({
                    "id": proxy.id,
                    "name": proxy.name,
                    "success": False,
                    "message": str(e)
                })

        success_count = sum(1 for r in results if r["success"])
        return {
            "total": len(proxies),
            "success": success_count,
            "failed": len(proxies) - success_count,
            "results": results
        }


@router.post("/proxies/{proxy_id}/enable")
async def enable_proxy(proxy_id: int):
    """启用代理"""
    with get_db() as db:
        proxy = crud.update_proxy(db, proxy_id, enabled=True)
        if not proxy:
            raise HTTPException(status_code=404, detail="代理不存在")
        return {"success": True, "message": "代理已启用"}


@router.post("/proxies/{proxy_id}/disable")
async def disable_proxy(proxy_id: int):
    """禁用代理"""
    with get_db() as db:
        proxy = crud.update_proxy(db, proxy_id, enabled=False)
        if not proxy:
            raise HTTPException(status_code=404, detail="代理不存在")
        return {"success": True, "message": "代理已禁用"}


# ============== CPA 设置 ==============

class CPASettings(BaseModel):
    """CPA 设置"""
    enabled: bool = False
    api_url: str = ""
    api_token: str = ""


class CPATestRequest(BaseModel):
    """CPA 测试请求"""
    api_url: str
    api_token: str


@router.get("/cpa")
async def get_cpa_settings():
    """获取 CPA 设置"""
    settings = get_settings()

    return {
        "enabled": settings.cpa_enabled,
        "api_url": settings.cpa_api_url,
        "has_token": bool(settings.cpa_api_token and settings.cpa_api_token.get_secret_value()),
    }


@router.post("/cpa")
async def update_cpa_settings(request: CPASettings):
    """更新 CPA 设置"""
    update_dict = {
        "cpa_enabled": request.enabled,
        "cpa_api_url": request.api_url,
    }

    # 只有提供了 token 才更新
    if request.api_token:
        update_dict["cpa_api_token"] = request.api_token

    update_settings(**update_dict)

    return {"success": True, "message": "CPA 设置已更新"}


@router.post("/cpa/test")
async def test_cpa_connection(request: CPATestRequest):
    """测试 CPA 连接"""
    from ...core.cpa_upload import test_cpa_connection as do_test

    settings = get_settings()
    proxy = settings.proxy_url

    # 如果传入 'use_saved_token'，使用已保存的 token
    api_token = request.api_token
    if api_token == 'use_saved_token' or not api_token:
        if settings.cpa_api_token:
            api_token = settings.cpa_api_token.get_secret_value()
        else:
            return {
                "success": False,
                "message": "未配置 API Token"
            }

    success, message = do_test(request.api_url, api_token, proxy)

    return {
        "success": success,
        "message": message
    }
