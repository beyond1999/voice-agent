from function_call.play_music import play_music
from function_call.write_article_in_word import write_article_in_word
from function_call.send_email import send_email
from function_call.Search_the_web import open_website_or_search
from .reminder_dispatcher import set_reminder
from .google_calendar_tools import list_upcoming_events

function_map = {}
function_map["play_music"] = play_music
function_map["write_article_in_word"] = write_article_in_word
function_map["send_email"] = send_email
function_map["open_website_or_search"] = open_website_or_search
function_map["set_reminder"] = set_reminder                     # 创建提醒的总入口
function_map["list_upcoming_events"] = list_upcoming_events     # 查看日程的入口