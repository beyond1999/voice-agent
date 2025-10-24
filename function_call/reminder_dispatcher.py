import datetime as dt
from typing import List, Optional
from .google_calendar_tools import create_calendar_event
from .windows_tools import set_native_reminder

def set_reminder(
    summary: str, 
    start_time_iso: str, 
    platforms: List[str],
    end_time_iso: Optional[str] = None,
    description: Optional[str] = ""
) -> str:
    """
    总调度器：根据用户指定的平台设置一个或多个提醒。
    """
    try:
        start_dt = dt.datetime.fromisoformat(start_time_iso)
    except ValueError:
        return f"错误：时间格式 '{start_time_iso}' 无效，必须是 ISO 8601 格式。"

    if not end_time_iso:
        end_dt = start_dt + dt.timedelta(hours=1)
        end_time_iso = end_dt.isoformat()

    results = []
    
    normalized_platforms = [p.lower() for p in platforms]
    if "both" in normalized_platforms:
        target_platforms = ["google", "windows"]
    else:
        target_platforms = normalized_platforms

    if "google" in target_platforms:
        google_result = create_calendar_event(
            summary=summary,
            start_time_iso=start_time_iso,
            end_time_iso=end_time_iso,
            description=description or summary
        )
        results.append(f"Google Calendar: {google_result}")

    if "windows" in target_platforms:
        windows_time_str = start_dt.strftime('%Y-%m-%d %H:%M')
        windows_result = set_native_reminder(
            time_str=windows_time_str,
            message=summary
        )
        results.append(f"Windows 本机提醒: {windows_result}")

    if not results:
        return "错误：未指定有效的提醒平台。请选择 'google', 'windows', 或 'both'。"

    return "\n".join(results)