import webbrowser
from typing import Optional
from urllib.parse import quote

# 预设的网站别名与 URL 映射 (保持不变)
WEBSITE_MAP = {
    "B站": "https://www.bilibili.com",
    "哔哩哔哩": "https://www.bilibili.com",
    "淘宝": "https://www.taobao.com",
    "京东": "https://www.jd.com",
    "知乎": "https://www.zhihu.com",
    "GitHub": "https://github.com",
    "谷歌": "https://www.google.com",
    "百度": "https://www.baidu.com",
}

# <--- 新增：搜索引擎映射字典 --->
# 将用户可能说的别名映射到标准名称和URL模板
SEARCH_ENGINE_MAP = {
    "bing": "https://www.bing.com/search?q=",
    "必应": "https://www.bing.com/search?q=",
    "google": "https://www.google.com/search?q=",
    "谷歌": "https://www.google.com/search?q=",
    "baidu": "https://www.baidu.com/s?wd=",
    "百度": "https://www.baidu.com/s?wd=",
}
DEFAULT_SEARCH_ENGINE = "bing" # 设置一个默认搜索引擎

def open_website_or_search(site_name: Optional[str] = None, 
                           search_query: Optional[str] = None, 
                           engine: Optional[str] = None) -> str: # <--- 修改：增加 engine 参数
    """
    打开预设网站或使用指定搜索引擎进行搜索。

    Args:
        site_name (str, optional): 预设网站的别名 (例如 "B站").
        search_query (str, optional): 需要搜索的关键词.
        engine (str, optional): 指定的搜索引擎别名 (例如 "谷歌", "百度"). 默认为必应.

    Returns:
        str: 操作执行结果的描述.
    """
    # 优先处理打开预设网站的指令
    if site_name:
        normalized_site = site_name.strip()
        url = WEBSITE_MAP.get(normalized_site)
        if url:
            webbrowser.open(url, new=2)
            return f"成功打开网站：{normalized_site} ({url})"
        else:
            search_query = normalized_site

    # 如果是搜索指令
    if search_query:
        # 确定使用哪个搜索引擎
        # 1. 用户指定的引擎 (转换为小写以匹配字典)
        # 2. 如果未指定或找不到，则使用默认引擎
        search_engine_name = (engine or DEFAULT_SEARCH_ENGINE).lower()
        url_template = SEARCH_ENGINE_MAP.get(search_engine_name, SEARCH_ENGINE_MAP[DEFAULT_SEARCH_ENGINE])
        # <--- 对搜索词进行 URL 编码 --->
        encoded_query = quote(search_query.strip())
        
        final_url = url_template + encoded_query# <--- 使用编码后的查询词
        webbrowser.open(final_url, new=2)
        
        # 在返回信息中明确指出用了哪个引擎
        used_engine_name = next((k for k, v in SEARCH_ENGINE_MAP.items() if v == url_template), DEFAULT_SEARCH_ENGINE)
        return f"已使用 {used_engine_name} 搜索：{search_query.strip()}"

    return "错误：需要提供网站名称或搜索内容。"