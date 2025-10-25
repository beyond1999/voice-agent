import datetime as dt
from typing import List, Optional
# 1. 导入新的“时间翻译器”
import dateparser

from .google_calendar_tools import create_calendar_event
from .windows_tools import set_native_reminder

def set_reminder(
    summary: str, 
    time_expression: str, # 2. 参数名改变，现在接收的是原始时间短语
    platforms: List[str],
    description: Optional[str] = ""
) -> str:
    """
    总调度器：使用 dateparser 解析自然语言时间，并设置提醒。
    """
    # 3. 使用 dateparser 将“明天下午3点”这样的短语翻译成精确的时间
    #    'PREFER_DATES_FROM': 'future' 能确保 "10:30" 被理解为未来的时间
    start_dt = dateparser.parse(time_expression, settings={'PREFER_DATES_FROM': 'future'})

    # 如果翻译失败，就礼貌地告诉用户
    if start_dt is None:
        return f"抱歉，我无法理解您说的时间 '{time_expression}'。您可以试试说“明天上午10点”或者“1小时后”。"

    # 翻译成功后，我们才开始准备各种格式的时间
    start_time_iso = start_dt.isoformat()
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
        return "错误：未指定有效的提醒平台。"

    return "\n".join(results)