import subprocess
import datetime as dt

def set_native_reminder(time_str: str, message: str) -> str:
    """
    在 Windows 任务计划程序中设置一个一次性的弹窗提醒。

    Args:
        time_str (str): 提醒时间，格式应为 'YYYY-MM-DD HH:MM'。
        message (str): 提醒时弹窗显示的消息内容。

    Returns:
        str: 操作结果。
    """
    try:
        # 将 'YYYY-MM-DD HH:MM' 格式转换为 schtasks 需要的格式
        parsed_dt = dt.datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        date_formatted = parsed_dt.strftime('%Y/%m/%d')
        time_formatted = parsed_dt.strftime('%H:%M')
        
        task_name = f"VoiceAgentReminder_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"
        command_to_run = f'msg * "{message}"'
        
        args = [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", command_to_run,
            "/sc", "ONCE",
            "/sd", date_formatted,
            "/st", time_formatted,
            "/f"
        ]
        
        result = subprocess.run(args, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        if "成功" in result.stdout:
            return f"好的，我会在 {time_str} 通过系统弹窗提醒您：{message}"
        else:
            return f"创建系统提醒时可能存在问题: {result.stdout}"
            
    except subprocess.CalledProcessError as e:
        return f"执行系统命令 schtasks 失败: {e.stderr}"
    except Exception as e:
        return f"创建本机提醒时发生未知错误: {e}"