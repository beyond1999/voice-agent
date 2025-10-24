import datetime as dt
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient import errors

"""这是整个流程中最关键的一步。我们需要从 Google 获取授权，允许我们的 Python 脚本访问您的日历。
进入 Google Cloud Console：访问 https://console.cloud.google.com/ 并登录您的 Google 账户。
创建新项目：如果需要，创建一个新项目（例如，命名为 "Voice Agent"）。
启用 Google Calendar API：
在顶部的搜索框中，搜索 "Google Calendar API" 并进入。
点击 “启用” (Enable) 按钮。
创建凭据 (Credentials)：
点击左侧菜单的 “凭据”。
点击 “+ 创建凭据” -> “OAuth 客户端 ID”。
如果需要，先配置“OAuth 同意屏幕”，选择 “外部”，然后填写应用名称（例如 "Voice Agent"），并提供您的邮箱地址，其他留空并保存即可。
返回创建凭据页面，在“应用类型”中选择 “桌面应用”。
给它一个名称（例如 "Voice Agent Desktop Client"），然后点击 “创建”。
下载凭据文件：
创建后会弹出一个窗口，点击 “下载 JSON” 按钮。
将下载的文件重命名为 credentials.json，并将它放在您项目的根目录下（与 .env 文件同级）。这是您的应用密钥，切勿泄露！
"""

# --- 授权范围：允许读写日历 ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
# --- 凭证文件路径 (这两个文件应位于项目根目录) ---
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def _get_calendar_service():
    """获取一个经过授权的 Google Calendar 服务对象。"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "错误: 找不到 credentials.json 文件。请从 Google Cloud Console 下载并放置在项目根目录。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(summary: str, start_time_iso: str, end_time_iso: str, description: str = "") -> str:
    """在 Google Calendar 中创建一个新事件。"""
    try:
        service = _get_calendar_service()
        
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time_iso, 'timeZone': 'Asia/Shanghai'},
            'end': {'dateTime': end_time_iso, 'timeZone': 'Asia/Shanghai'},
            'reminders': {'useDefault': True},
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return f"日程已创建：'{summary}'。链接：{created_event.get('htmlLink')}"
    except errors.HttpError as error:
        return f"调用 Google Calendar API 时出错: {error}"
    except Exception as e:
        return f"创建日历事件时发生未知错误: {e}"

def list_upcoming_events(max_results: int = 5) -> str:
    """列出 Google Calendar 中即将发生的事件。"""
    try:
        service = _get_calendar_service()
        now = dt.datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return "您接下来没有安排。"
            
        result_str = "您接下来的日程安排：\n"
        for event in events:
            start_str = event['start'].get('dateTime', event['start'].get('date'))
            # 解析并格式化时间
            start_dt = dt.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            formatted_time = start_dt.strftime('%Y-%m-%d %H:%M')
            result_str += f"- {formatted_time}: {event['summary']}\n"
        
        return result_str.strip()
    except Exception as e:
        return f"获取日历事件时出错: {e}"