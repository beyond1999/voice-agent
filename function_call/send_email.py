import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 安全第一：从环境变量读取凭证 ---
# 用户必须在项目根目录创建一个 .env 文件来配置这些信息
# 对于 Gmail/Outlook, 这是 "应用专用密码"
# 对于 QQ/163 邮箱, 这是 "授权码"
SENDER_EMAIL =  os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# --- 常见邮箱的 SMTP 服务器配置 ---
SMTP_SETTINGS = {
    # 域名: (服务器地址, 端口号)
    "gmail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp.office365.com", 587),
    "hotmail.com": ("smtp.office365.com", 587),
    "163.com": ("smtp.163.com", 465),    # 使用 SSL
    "qq.com": ("smtp.qq.com", 465),      # 使用 SSL
}

def send_email(recipient: str, subject: str, body: str) -> str:
    """
    向指定的收件人发送邮件。

    Args:
        recipient (str): 收件人的电子邮箱地址。
        subject (str): 邮件的主题。
        body (str): 邮件的正文内容。

    Returns:
        str: 一个描述操作结果（成功或失败）的消息。
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return "错误：发件人邮箱未配置。请在 .env 文件中设置 SENDER_EMAIL 和 SENDER_PASSWORD。"

    # --- 核心修复：重构 try...except 块，确保 domain 安全 ---
    domain = None  # 1. 预先定义 domain 变量
    try:
        # 2. 从邮箱地址中提取域名
        domain = SENDER_EMAIL.split('@')[1]
        # 3. 查找 SMTP 配置
        if domain not in SMTP_SETTINGS:
            raise KeyError(f"SMTP setting for '{domain}' not found.")
        smtp_server, smtp_port = SMTP_SETTINGS[domain]
    except (IndexError, KeyError) as e:
        # 4. 捕获两种可能的错误，并提供清晰的反馈
        if isinstance(e, IndexError):
            return f"错误：发件人邮箱地址 '{SENDER_EMAIL}' 格式无效，无法提取域名。"
        else: # isinstance(e, KeyError)
            return f"错误：不支持的发件邮箱域名 '{domain}'。请在 email_tools.py 的 SMTP_SETTINGS 中添加配置。"
    # --- 修复结束 ---

    print(f"准备发送邮件至 {recipient}，主题：{subject}...")

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient
    msg.set_content(body)

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        
        success_message = f"邮件已成功发送至 {recipient}。"
        print(success_message)
        return success_message
    except smtplib.SMTPAuthenticationError:
        error_message = "错误：邮箱认证失败。请检查密码和授权码。"
        print(error_message)
        return error_message
        
    # --- 核心修复：专门处理这个“伪错误” ---
    except smtplib.SMTPResponseException as e:
        # 检查是否是我们遇到的那个特定的、无害的连接关闭错误
        if e.smtp_code == -1 and e.smtp_error == b'\x00\x00\x00':
            # 这是一个在连接关闭时发生的无害异常，但邮件已发送成功
            success_message = f"邮件已成功发送至 {recipient}。（连接关闭时有轻微异常，已忽略）"
            print(success_message)
            return success_message
        else:
            # 如果是其他真正的 SMTP 响应错误，则正常报告
            error_message = f"发送邮件时发生 SMTP 错误: {e}"
            print(error_message)
            return error_message
        
            
    except Exception as e:
        # 捕获其他所有网络错误、超时等
        error_message = f"发送邮件时发生未知错误: {type(e).__name__}: {e}"
        print(error_message)
        return error_message