"""
AstrBot 豆瓣电影查询插件
"""
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.message_components import Plain, Image, Node, Nodes
from astrbot.core.star.filter.event_message_type import EventMessageType
import requests
import json
import urllib.parse
import time
import os
import logging
import textwrap


def do_request(url, referer='https://movie.douban.com/', is_mobile_api=False):
    """执行 HTTP 请求"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': referer
    }
    
    if is_mobile_api:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
            'Accept': 'application/json',
            'Referer': referer,
            'X-Requested-With': 'XMLHttpRequest'
        }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"请求失败：{e}")
    
    return None


@register("astrbot_plugin_douban", "YourName", "豆瓣电影查询", "1.0.0")
class DoubanMovie(Star):
    """豆瓣电影查询插件"""
    
    def __init__(self, context, config):
        super().__init__(context)
        self.config = config
        self.timeout = config.get("timeout", 30)
        self.max_results = config.get("max_results", 20)
        self.timeout_seconds = config.get("timeout_seconds", 60)
        self.search_cache = {}
        
        # 初始化日志
        self.plugin_logger = logging.getLogger("astrbot_plugin_douban")
        self.plugin_logger.setLevel(logging.INFO)
        self.plugin_logger.propagate = True
        
        self.MOBILE_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    
    def search_movies(self, keyword):
        """搜索电影"""
        if not keyword:
            return []
        
        search_url = 'https://movie.douban.com/j/subject_suggest?q=' + urllib.parse.quote(keyword)
        referer = 'https://m.douban.com/movie/'
        response = do_request(search_url, referer, True)
        
        if not response:
            return []
        
        try:
            results = json.loads(response)
            if isinstance(results, list):
                if len(results) < 5:
                    results_full = self.search_movies_full(keyword)
                    if results_full:
                        return results_full
                return results
        except:
            return []
        
        return []
    
    def search_movies_full(self, keyword, count=20):
        """使用豆瓣官方搜索API获取更多结果"""
        api_key = '0b2bdeda43b5688921839c8ecb20399b'
        search_url = f'https://api.douban.com/v2/movie/search?q={urllib.parse.quote(keyword)}&count={count}&apikey={api_key}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=15, verify=False)
            if response.status_code == 200:
                data = json.loads(response.text)
                if 'subjects' in data and isinstance(data['subjects'], list):
                    results = []
                    for item in data['subjects']:
                        result = {
                            'id': item.get('id', ''),
                            'title': item.get('title', ''),
                            'year': str(item.get('year', '')),
                            'type': item.get('subtype', 'movie'),
                            'url': item.get('alt', ''),
                            'img': item.get('images', {}).get('medium', '') if isinstance(item.get('images'), dict) else ''
                        }
                        results.append(result)
                    return results
        except Exception as e:
            self.plugin_logger.error(f"完整搜索失败: {e}")
        
        return None
    
    def format_search_results(self, results):
        """格式化搜索结果"""
        if not results:
            return "❌ 未找到相关结果"
        
        text = f"🔍 找到 {len(results)} 个结果：\n\n"
        
        for i, r in enumerate(results[:self.max_results], 1):
            title = r.get('title', '未知')
            year = r.get('year', '')
            movie_type = r.get('type', 'movie') or 'movie'
            
            # 根据类型显示不同图标
            type_icon = "📺" if movie_type in ['tv', 'TVSeries'] else "🎬"
            
            text += f"{i}. {type_icon} {title}"
            if year:
                text += f" ({year})"
            text += "\n"
        
        text += "\n💡 回复数字序号查看详情"
        
        return text
    
    def format_movie_detail(self, movie):
        """格式化电影详情（简洁版）"""
        if not movie:
            return "❌ 获取详情失败"
        
        text = ""
        
        # 标题
        text += f"🎬 {movie.get('title', '未知')}"
        if movie.get('year'):
            text += f" ({movie['year']})\n"
        else:
            text += "\n"
        text += "\n"
        
        # 海报
        if movie.get('img'):
            text += f"🖼️ 海报：{movie['img']}\n\n"
        
        # 基本信息
        movie_type = movie.get('type', 'movie') or 'movie'
        type_text = "电视剧" if movie_type in ['tv', 'TVSeries'] else "电影"
        text += f"📺 类型：{type_text}\n"
        text += f"📅 年份：{movie.get('year', '未知')}\n"
        
        # 评分
        if movie.get('rating'):
            rating = movie['rating']
            rating_stars = "⭐" * int(float(rating) / 2)
            text += f"{rating_stars} 评分：{rating}/10"
            if movie.get('ratings_count'):
                text += f" ({movie['ratings_count']}人评价)\n"
            else:
                text += "\n"
        
        # 题材
        genres = movie.get('genres')
        if genres and isinstance(genres, list):
            text += f"🎭 题材：{' / '.join(genres)}\n"
        
        # 地区
        countries = movie.get('countries')
        if countries and isinstance(countries, list):
            text += f"🌍 地区：{', '.join(countries)}\n"
        
        # 时长
        if movie.get('durations'):
            durations = movie['durations']
            if isinstance(durations, list) and len(durations) > 0:
                duration = durations[0]
                if duration and duration.isdigit():
                    duration = f"{duration}分钟"
                    text += f"⏱️ 时长：{duration}\n"
        
        # 上映日期
        if movie.get('pubdate'):
            pubdate = movie.get('pubdate', [])
            if isinstance(pubdate, list) and len(pubdate) > 0:
                dates = []
                for date in pubdate[:3]:
                    if isinstance(date, str):
                        date_clean = date.split('(')[0].strip() if '(' in date else date
                        dates.append(date_clean)
                if dates:
                    text += f"📅 上映：{' | '.join(dates)}\n"
            elif isinstance(pubdate, str):
                text += f"📅 上映：{pubdate}\n"
        
        text += "\n"
        
        # 导演
        directors = movie.get('directors')
        if directors and isinstance(directors, list):
            director_names = [d['name'] if isinstance(d, dict) else d for d in directors]
            text += f"🎬 导演：{', '.join(director_names)}\n"
        
        # 演员（显示全部）
        casts = movie.get('casts')
        if casts and isinstance(casts, list):
            casts_info = []
            for c in casts:
                if isinstance(c, dict):
                    name = c.get('name', '')
                    role = c.get('role', '')
                    if role:
                        casts_info.append(f"{name}({role})")
                    else:
                        casts_info.append(name)
                else:
                    casts_info.append(str(c))
            text += f"🎭 主演：{', '.join(casts_info)}\n"
        
        text += "\n"
        
        # 语言
        languages = movie.get('languages')
        if languages and isinstance(languages, list):
            text += f"🗣️ 语言：{', '.join(languages)}\n"
        
        # 别名
        aka = movie.get('aka')
        if aka and isinstance(aka, list) and len(aka) > 0:
            text += f"🏷️ 别名：{' | '.join(aka[:3])}\n"
        
        text += "\n"
        
        # 简介
        if movie.get('summary'):
            summary = movie['summary'].strip()
            if summary:
                text += f"📖 简介\n"
                # 简介完整显示，每行最多 60 个字符自动换行
                wrapped_summary = textwrap.fill(summary, width=60)
                text += f"{wrapped_summary}\n\n"
        
        # 链接
        if movie.get('url'):
            text += f"🔗 详情：{movie['url']}\n"
        
        return text
    
    def download_poster(self, url):
        """下载海报图片到临时文件"""
        try:
            import tempfile
            resp = requests.get(url, headers=self.MOBILE_HEADERS, timeout=self.timeout, verify=False)
            if resp.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                    f.write(resp.content)
                    return f.name
        except Exception as e:
            self.plugin_logger.error(f"下载海报失败：{e}")
        return None
    
    async def send_movie_forward_msg(self, event, movie, include_comments=False):
        """发送电影详情合并消息"""
        self.plugin_logger.info("进入 send_movie_forward_msg 函数")
        try:
            self.plugin_logger.info(f"开始发送合并消息，include_comments={include_comments}")
            
            # 构造合并消息节点列表
            nodes = []
            
            # 添加电影信息文本节点
            text = self.format_movie_detail(movie)
            self.plugin_logger.info(f"电影详情文本长度：{len(text)}")
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": int(event.get_self_id()),
                    "nickname": "豆瓣电影",
                    "content": [{"type": "text", "data": {"text": text}}]
                }
            })
            
            # 如果需要包含评论，获取并添加评论节点
            if include_comments and movie.get('id'):
                self.plugin_logger.info(f"正在获取电影 {movie.get('id')} 的评论...")
                comments = self.get_movie_comments(movie['id'], count=50)
                self.plugin_logger.info(f"获取到评论数：{len(comments) if comments else 0}")
                if comments:
                    # 添加评论头部节点
                    comment_header = f"📝 热门评论（共 {len(comments)} 条）\n"
                    nodes.append({
                        "type": "node",
                        "data": {
                            "user_id": int(event.get_self_id()),
                            "nickname": "豆瓣电影",
                            "content": [{"type": "text", "data": {"text": comment_header}}]
                        }
                    })
                    
                    # 每条评论单独节点
                    for i, c in enumerate(comments[:50], 1):
                        rating = c.get('rating', '无评分')
                        comment = c.get('comment', '')
                        votes = c.get('votes', 0)
                        create_time = c.get('create_time', '')
                        
                        comment_text = f"{i}. 评分：{rating}  有用：{votes}  {create_time}\n"
                        if comment:
                            comment_text += f"\n{comment}"
                        
                        nodes.append({
                            "type": "node",
                            "data": {
                                "user_id": int(event.get_self_id()),
                                "nickname": "豆瓣电影",
                                "content": [{"type": "text", "data": {"text": comment_text}}]
                            }
                        })
                    self.plugin_logger.info(f"添加了评论节点，评论数：{len(comments)}")
            
            self.plugin_logger.info(f"总共构造了 {len(nodes)} 个节点")
            
            if nodes:
                payload = {
                    "message": nodes,
                    "prompt": "[豆瓣电影查询结果]",
                    "summary": "豆瓣电影查询结果",
                    "source": "豆瓣电影"
                }
                
                try:
                    if event.is_private_chat():
                        payload["user_id"] = int(event.get_sender_id())
                        action = "send_private_forward_msg"
                    else:
                        payload["group_id"] = int(event.get_group_id())
                        action = "send_group_forward_msg"
                    
                    await event.bot.api.call_action(action, **payload)
                    event.stop_event()
                    self.plugin_logger.info("合并消息发送成功")
                except Exception as forward_error:
                    self.plugin_logger.error(f"发送合并转发失败：{forward_error}，使用分条发送")
                    self.plugin_logger.info(f"降级发送，节点总数：{len(nodes)}")
                    # 分条发送
                    for node in nodes:
                        content = node["data"]["content"][0]
                        if content["type"] == "text":
                            yield event.plain_result(content["data"]["text"])
                        elif content["type"] == "image":
                            yield event.plain_result("🖼️ 海报图片")
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.plugin_logger.error(f"❌ 外层异常：{e}")
            self.plugin_logger.error(f"错误堆栈：{error_trace}")
            self.plugin_logger.error(f"降级为发送普通消息")
            # 发送普通消息
            yield event.plain_result(self.format_movie_detail(movie))
    
    def get_user_id(self, event):
        """获取用户 ID"""
        try:
            if hasattr(event, 'get_sender_id'):
                user_id = event.get_sender_id()
                if user_id:
                    return str(user_id)
            if hasattr(event, 'get_user_id'):
                user_id = event.get_user_id()
                if user_id:
                    return str(user_id)
            if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'sender'):
                if hasattr(event.message_obj.sender, 'user_id'):
                    return str(event.message_obj.sender.user_id)
            return None
        except Exception as e:
            self.plugin_logger.error(f"获取用户 ID 失败：{e}")
            return None
    
    def get_movie_detail(self, movie_id):
        """获取电影详情"""
        url = f'https://m.douban.com/rexxar/api/v2/movie/{urllib.parse.quote(movie_id)}?ck=&for_mobile=1'
        resp = do_request(url, f'https://m.douban.com/movie/subject/{movie_id}/', True)
        if not resp:
            url = f'https://m.douban.com/rexxar/api/v2/tv/{urllib.parse.quote(movie_id)}?ck=&for_mobile=1'
            resp = do_request(url, f'https://m.douban.com/movie/subject/{movie_id}/', True)
        if resp:
            try:
                return json.loads(resp)
            except:
                pass
        return None
    
    def get_movie_comments(self, movie_id, count=50, start=0):
        """获取电影评论"""
        if not movie_id:
            return []
        
        if count <= 0:
            count = 10
        if count > 100:
            count = 100
        
        api_url = f'https://m.douban.com/rexxar/api/v2/tv/{urllib.parse.quote(movie_id)}/interests?count={count}&order_by=hot&anony=0&start={start}&ck=&for_mobile=1'
        referer = f'https://m.douban.com/movie/subject/{movie_id}/'
        
        resp = do_request(api_url, referer, True)
        
        if not resp:
            api_url = f'https://m.douban.com/rexxar/api/v2/movie/{urllib.parse.quote(movie_id)}/interests?count={count}&order_by=hot&anony=0&start={start}&ck=&for_mobile=1'
            resp = do_request(api_url, referer, True)
        
        if not resp:
            return []
        
        try:
            data = json.loads(resp)
        except:
            return []
        
        if 'code' in data and data['code'] != 0 and 'msg' in data:
            return []
        
        comments = []
        if 'interests' in data and isinstance(data['interests'], list):
            for interest in data['interests']:
                comment = {}
                if isinstance(interest, dict):
                    if 'rating' in interest and isinstance(interest['rating'], dict) and 'value' in interest['rating']:
                        comment['rating'] = str(interest['rating']['value'])
                    if 'comment' in interest:
                        comment['comment'] = interest['comment']
                    if 'user' in interest and isinstance(interest['user'], dict):
                        if 'name' in interest['user']:
                            comment['user_name'] = interest['user']['name']
                        if 'avatar' in interest['user'] and isinstance(interest['user']['avatar'], dict) and 'url' in interest['user']['avatar']:
                            comment['user_avatar'] = interest['user']['avatar']['url']
                    if 'create_time' in interest:
                        comment['create_time'] = interest['create_time']
                    if 'votes' in interest:
                        comment['votes'] = interest['votes']
                comments.append(comment)
        
        return comments
    
    def format_comments(self, comments):
        """格式化评论列表"""
        if not comments:
            return "暂无评论"
        
        text = f"【评论列表】共 {len(comments)} 条\n"
        text += "=" * 80 + "\n\n"
        
        for i, c in enumerate(comments, 1):
            rating = c.get('rating', '无评分')
            comment = c.get('comment', '')
            votes = c.get('votes', 0)
            create_time = c.get('create_time', '')
            
            text += f"{i}. 评分：{rating}  有用：{votes}  {create_time}\n"
            if comment:
                text += f"   {comment}\n"
            text += "-" * 80 + "\n\n"
        
        return text
    
    def format_mobile_api_data(self, movie_id, data, search_result=None):
        """格式化移动端 API 数据"""
        if not data:
            return None
        
        movie = {'id': movie_id, 'url': f'https://m.douban.com/movie/subject/{movie_id}/'}
        
        if 'title' in data:
            movie['title'] = data['title']
        if 'year' in data:
            movie['year'] = str(data['year'])
        
        if search_result and 'type' in search_result:
            movie['type'] = search_result['type']
        elif 'type' in data:
            movie['type'] = data['type']
        elif 'is_tv' in data:
            movie['type'] = 'TVSeries' if data['is_tv'] else 'Movie'
        elif 'category' in data:
            movie['type'] = 'TVSeries' if data['category'] == 'tv' else 'Movie'
        else:
            movie['type'] = 'movie'
        
        if 'rating' in data and isinstance(data['rating'], dict):
            movie['rating'] = str(data['rating'].get('value', ''))
            movie['ratings_count'] = str(data['rating'].get('count', ''))
        
        if 'genres' in data and isinstance(data['genres'], list):
            movie['genres'] = data['genres']
        else:
            movie['genres'] = []
        
        if 'directors' in data and isinstance(data['directors'], list):
            movie['directors'] = []
            for d in data['directors']:
                director = {}
                if 'name' in d:
                    director['name'] = d['name']
                if 'id' in d:
                    director['id'] = d['id']
                if 'cover_url' in d:
                    director['avatar'] = d['cover_url']
                if director:
                    movie['directors'].append(director)
        else:
            movie['directors'] = []
        
        if 'actors' in data and isinstance(data['actors'], list):
            movie['casts'] = []
            for a in data['actors']:
                actor = {}
                if 'name' in a:
                    actor['name'] = a['name']
                if 'id' in a:
                    actor['id'] = a['id']
                if 'cover_url' in a:
                    actor['avatar'] = a['cover_url']
                if 'character_name' in a:
                    actor['role'] = a['character_name']
                if actor:
                    movie['casts'].append(actor)
        else:
            movie['casts'] = []
        
        if 'languages' in data and isinstance(data['languages'], list):
            movie['languages'] = data['languages']
        else:
            movie['languages'] = []
        
        if 'pubdate' in data:
            movie['pubdate'] = data['pubdate']
        else:
            movie['pubdate'] = []
        
        if 'durations' in data and isinstance(data['durations'], list):
            movie['durations'] = data['durations']
        else:
            movie['durations'] = []
        
        # 简介（优先使用 intro 字段）
        if 'intro' in data:
            movie['summary'] = data['intro']
        elif 'summary' in data:
            movie['summary'] = data['summary']
        # 也检查 overview 字段（有些 API 用这个名称）
        elif 'overview' in data:
            movie['summary'] = data['overview']
        
        # countries/regions 字段
        if 'countries' in data and isinstance(data['countries'], list):
            movie['countries'] = data['countries']
        elif 'regions' in data and isinstance(data['regions'], list):
            movie['countries'] = data['regions']
        else:
            movie['countries'] = []
        
        if 'aka' in data and isinstance(data['aka'], list):
            movie['aka'] = data['aka']
        else:
            movie['aka'] = []
        
        if 'cover' in data and isinstance(data['cover'], dict) and data['cover'].get('url'):
            movie['img'] = data['cover']['url']
        elif 'img' in data:
            movie['img'] = data['img']
        elif 'image' in data:
            movie['img'] = data['image']
        elif 'cover_url' in data:
            movie['img'] = data['cover_url']
        elif 'poster' in data and isinstance(data['poster'], dict) and data['poster'].get('url'):
            movie['img'] = data['poster']['url']
        
        return movie
    
    @filter.command("豆瓣")
    async def douban_cmd(self, event: AstrMessageEvent):
        """豆瓣电影查询"""
        try:
            msg = event.get_message_str().strip()
            if msg.startswith("豆瓣"):
                msg = msg[2:].strip()
            
            if not msg:
                yield event.plain_result("用法：/豆瓣 电影名\n   /豆瓣 ID")
                return
            
            if msg.isdigit():
                yield event.plain_result("🔍 正在查询...")
                data = self.get_movie_detail(msg)
                movie = self.format_mobile_api_data(msg, data)
                
                # 使用 send_movie_forward_msg 发送包含评论的合并消息
                async for msg in self.send_movie_forward_msg(event, movie, include_comments=True):
                    yield msg
                event.stop_event()
                return
            
            yield event.plain_result("🔍 搜索中...")
            results = self.search_movies(msg)
            
            if not results:
                yield event.plain_result("❌ 未找到相关结果")
                return
            
            if len(results) == 1:
                movie_id = results[0].get('id')
                self.plugin_logger.info(f"单条结果 - 电影 ID: {movie_id}")
                data = self.get_movie_detail(movie_id)
                movie = self.format_mobile_api_data(movie_id, data, search_result=results[0])
                
                # 使用 send_movie_forward_msg 发送包含评论的合并消息
                async for msg in self.send_movie_forward_msg(event, movie, include_comments=True):
                    yield msg
                event.stop_event()
                self.plugin_logger.info(f"单条结果 - 合并消息发送完成")
                return
            
            yield event.plain_result(self.format_search_results(results))
            
            user_id = self.get_user_id(event)
            self.plugin_logger.info(f"搜索命令 - 用户 ID: {user_id}")
            if user_id:
                self.search_cache[user_id] = {
                    'results': results,
                    'time': time.time()
                }
                self.plugin_logger.info(f"搜索结果已缓存，用户 ID: {user_id}，结果数量：{len(results)}")
            else:
                self.plugin_logger.warning("无法获取用户 ID，搜索结果将无法通过序号选择")
        
        except Exception as e:
            self.plugin_logger.error(str(e))
            yield event.plain_result(f"❌ 错误：{str(e)}")
    
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """监听所有消息，处理序号选择"""
        try:
            user_id = self.get_user_id(event)
            message_text = event.message_str.strip()
            
            self.plugin_logger.info(f"消息监听器 - 用户 ID: {user_id}, 消息内容：{repr(message_text)}")
            
            if not message_text.isdigit():
                self.plugin_logger.debug(f"消息不是纯数字，忽略：{repr(message_text)}")
                return
            
            self.plugin_logger.info(f"消息是纯数字：{message_text}")
            
            if user_id not in self.search_cache:
                self.plugin_logger.info(f"用户{user_id}没有缓存的搜索结果，缓存键：{list(self.search_cache.keys())}")
                return
            
            cache_data = self.search_cache[user_id]
            if time.time() - cache_data['time'] > self.timeout_seconds:
                del self.search_cache[user_id]
                self.plugin_logger.info(f"用户{user_id}的缓存已过期，已删除")
                return
            
            results = cache_data['results']
            index = int(message_text)
            
            if index < 1 or index > len(results):
                self.plugin_logger.info(f"序号{index}超出范围 (1-{len(results)})")
                return
            
            selected = results[index - 1]
            movie_id = selected.get('id')
            
            if movie_id:
                self.plugin_logger.info(f"用户{user_id}选择了序号{index}，电影 ID: {movie_id}")
                
                data = self.get_movie_detail(movie_id)
                movie = self.format_mobile_api_data(movie_id, data, search_result=selected)
                
                # 使用 send_movie_forward_msg 发送包含评论的合并消息
                async for msg in self.send_movie_forward_msg(event, movie, include_comments=True):
                    yield msg
                event.stop_event()
                self.plugin_logger.info(f"序号选择 - 合并消息发送成功")
                
                del self.search_cache[user_id]
                self.plugin_logger.info(f"用户{user_id}的缓存已清除")
                return
        
        except Exception as e:
            self.plugin_logger.error(f"处理序号选择失败：{e}", exc_info=True)
    
    @filter.command("豆瓣帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        yield event.plain_result(
            "📚 豆瓣查询\n\n"
            "用法:\n"
            "  /豆瓣 电影名 - 搜索并选择\n"
            "  /豆瓣 ID   - 直接查详情\n"
            "  /豆瓣评论 电影名/ID - 查看评论\n\n"
            "示例:\n"
            "  /豆瓣 流浪地球\n"
            "  /豆瓣 1724604\n"
            "  /豆瓣评论 流浪地球"
        )
    
    @filter.command("豆瓣评论")
    async def comments_cmd(self, event: AstrMessageEvent):
        """查看评论"""
        import os
        import json
        
        temp_file = None
        try:
            msg = event.get_message_str().strip()
            if msg.startswith("豆瓣评论"):
                msg = msg[4:].strip()
            
            if not msg:
                yield event.plain_result("用法：/豆瓣评论 电影名/ID")
                return
            
            if msg.isdigit():
                movie_id = msg
                yield event.plain_result("🔍 正在获取评论...")
            else:
                yield event.plain_result("🔍 搜索中...")
                results = self.search_movies(msg)
                
                if not results:
                    yield event.plain_result("❌ 未找到相关结果")
                    return
                
                movie_id = results[0].get('id')
                if not movie_id:
                    yield event.plain_result("❌ 无法获取电影ID")
                    return
            
            # 获取评论并保存到本地
            yield event.plain_result("📥 正在下载评论...")
            comments = self.get_movie_comments(movie_id, count=100)
            
            if not comments:
                yield event.plain_result("暂无评论")
                return
            
            # 保存到临时文件
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
            json.dump(comments, temp_file, ensure_ascii=False, indent=2)
            temp_file.close()
            
            # 发送合并消息
            yield event.plain_result("📤 正在发送评论...")
            
            nodes = []
            
            # 添加头部节点
            display_count = min(len(comments), 50)  # 试 50 条
            header = f"【评论列表】共 {display_count} 条"
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": int(event.get_self_id()),
                    "nickname": "豆瓣电影",
                    "content": [{"type": "text", "data": {"text": header}}]
                }
            })
            
            # 每条评论作为一个独立节点
            for i, c in enumerate(comments[:display_count], 1):
                rating = c.get('rating', '无评分')
                comment = c.get('comment', '')
                votes = c.get('votes', 0)
                create_time = c.get('create_time', '')
                
                comment_text = f"评分：{rating}  有用：{votes}  {create_time}\n"
                if comment:
                    comment_text += f"\n{comment}"
                
                nodes.append({
                    "type": "node",
                    "data": {
                        "user_id": int(event.get_self_id()),
                        "nickname": "豆瓣电影",
                        "content": [{"type": "text", "data": {"text": comment_text}}]
                    }
                })
            
            # 发送合并消息
            if nodes:
                try:
                    payload = {
                        "message": nodes,
                        "prompt": "[豆瓣评论]",
                        "summary": f"豆瓣评论 {len(comments)} 条",
                        "source": "豆瓣电影"
                    }
                    
                    if event.is_private_chat():
                        payload["user_id"] = int(event.get_sender_id())
                        action = "send_private_forward_msg"
                    else:
                        payload["group_id"] = int(event.get_group_id())
                        action = "send_group_forward_msg"
                    
                    await event.bot.api.call_action(action, **payload)
                    event.stop_event()
                except Exception as e:
                    import traceback
                    self.plugin_logger.error(f"发送合并消息失败：{e}")
                    self.plugin_logger.error(f"详细错误：{traceback.format_exc()}")
                    # 失败了用普通消息发送全部评论
                    yield event.plain_result("❌ 合并消息发送失败，改用普通发送")
                    for i, c in enumerate(comments, 1):
                        rating = c.get('rating', '无评分')
                        comment = c.get('comment', '')
                        votes = c.get('votes', 0)
                        create_time = c.get('create_time', '')
                        
                        text = f"{i}. 评分：{rating}  有用：{votes}  {create_time}\n"
                        if comment:
                            text += f"\n{comment}"
                        yield event.plain_result(text)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.plugin_logger.error(f"获取评论失败：{e}")
            self.plugin_logger.error(f"错误堆栈：{error_trace}")
            yield event.plain_result(f"❌ 获取评论失败：{str(e)}")
        
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
