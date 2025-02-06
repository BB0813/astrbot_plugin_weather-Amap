import aiohttp
import logging
import datetime
from typing import Optional, List
import traceback


from astrbot.api.all import (
    Star, Context, register, 
    AstrMessageEvent, command_group, command, 
    MessageEventResult, llm_tool
)
from astrbot.api.event import filter

# ==============================
# 下面是我们定义的 HTML 模板
# ==============================

CURRENT_WEATHER_TEMPLATE = """
<div style="width: 720px; padding: 16px; background-color: #ffffff; color: #333; font-family: sans-serif; border: 1px solid #ddd; border-radius: 8px;">
  <h2 style="margin-top: 0; color: #4e6ef2; text-align: center;">
    当前天气
  </h2>
  <div style="margin-bottom: 8px;">
    <strong>城市:</strong> {{ city }}
  </div>
  <div style="margin-bottom: 8px;">
    <strong>天气:</strong> {{ desc }}
  </div>
  <div style="margin-bottom: 8px;">
    <strong>温度:</strong> {{ temp }}℃ 
    <span style="font-size: 12px; color: #888;">(体感: {{ feels_like }}℃)</span>
  </div>
  <div style="margin-bottom: 8px;">
    <strong>湿度:</strong> {{ humidity }}%
  </div>
  <div style="margin-bottom: 8px;">
    <strong>风速:</strong> {{ wind_speed }} m/s
  </div>
  <div style="border-top: 1px solid #ddd; margin-top: 12px; padding-top: 12px; font-size: 12px; color: #999;">
    数据来源: OpenWeatherMap API 2.5
  </div>
</div>
"""

FORECAST_TEMPLATE = """
<div style="width: 720px; background-color: #fff; color: #333; font-family: sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
  <h2 style="margin-top: 0; color: #4e6ef2; text-align: center;">
    未来{{ total_days }}天天气预报
  </h2>
  <div style="margin-bottom: 8px;"><strong>城市:</strong> {{ city }}</div>
  
  {% for day in days %}
  <div style="margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
    <div style="font-weight: bold; color: #4e6ef2;">
      {{ day.date_str }} ({{ day.weekday_str }})
    </div>
    <div><strong>天气:</strong> {{ day.desc }}</div>
    <div><strong>温度范围:</strong> {{ day.temp_min }}℃ ~ {{ day.temp_max }}℃</div>
    <div><strong>白天:</strong> {{ day.temp_day }}℃  <strong>夜晚:</strong> {{ day.temp_night }}℃</div>
    <div><strong>湿度:</strong> {{ day.humidity }}%  <strong>风速:</strong> {{ day.wind_speed }} m/s</div>
  </div>
  {% endfor %}
  
  <div style="font-size: 12px; color: #999; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">
    数据来源: OpenWeatherMap API 2.5
  </div>
</div>
"""

ALERTS_TEMPLATE = """
<div style="width: 720px; background-color: #fff; color: #333; font-family: sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
  <h2 style="margin-top: 0; color: #ff4e4e; text-align: center;">
    天气预警
  </h2>
  <div style="margin-bottom: 8px;"><strong>城市:</strong> {{ city }}</div>
  
  {% if alerts|length == 0 %}
    <div>目前没有预警信息或暂不支持此功能</div>
  {% else %}
    {% for alert in alerts %}
      <div style="margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
        <div style="font-weight: bold; color: #ff4e4e;">
          {{ alert.event }}
        </div>
        <div><strong>开始:</strong> {{ alert.start_str }}</div>
        <div><strong>结束:</strong> {{ alert.end_str }}</div>
        <div style="white-space: pre-wrap; margin-top: 6px;">
          {{ alert.description }}
        </div>
      </div>
    {% endfor %}
  {% endif %}
  
  <div style="font-size: 12px; color: #999; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">
    数据来源: 暂不支持 OpenWeatherMap API 2.5 Alerts
  </div>
</div>
"""

@register(
    "astrbot_plugin_weather",                 
    "w33d",      
    "一个基于 OpenWeatherMap v2.5 API 的天气查询插件",  
    "1.0.0",                    
    "https://github.com/Last-emo-boy/astrbot_plugin_weather" 
)
class WeatherPlugin(Star):
    """
    这是一个调用 OpenWeatherMap 2.5 接口（及旧版 /forecast/daily）实现的天气查询插件示例。
    支持 /weather current /weather forecast /weather alerts /weather help
    """
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        
        self.logger = logging.getLogger("WeatherPlugin")
        self.logger.setLevel(logging.DEBUG)  # 可根据需求修改日志级别

        self.config = config
        self.api_key = config.get("openweather_api_key", "")
        self.default_city = config.get("default_city", "北京")

        self.logger.debug(f"WeatherPlugin initialized with API key: {self.api_key}, default_city: {self.default_city}")

    # =============================
    # 1) 命令组 "weather"
    # =============================
    @command_group("weather")
    def weather_group(self):
        """
        天气相关功能命令组。
        使用方法：
        /weather <子指令> <城市或其它参数>
        子指令包括：current, forecast, alerts, help
        """
        pass

    # weather current
    @weather_group.command("current")
    async def weather_current(self, event: AstrMessageEvent, city: Optional[str] = None):
        """
        查看当前天气
        用法: /weather current <城市>
        示例: /weather current 上海
        """
        self.logger.info(f"User called /weather current with city: {city}")

        if not city:
            city = self.default_city

        if not self.api_key:
            self.logger.warning("API Key is not configured. Cannot query weather.")
            yield event.plain_result("未配置 OpenWeatherMap API Key，无法查询天气。请在管理面板中配置后再试。")
            return

        data = await self.get_current_weather_by_city(city)
        if data is None:
            self.logger.warning(f"Failed to get current weather for city={city}")
            yield event.plain_result(f"查询 [{city}] 的当前天气失败，请稍后再试。")
            return

        # 渲染为图片
        result_img_url = await self.render_current_weather(data)
        yield event.image_result(result_img_url)

    # weather forecast
    @weather_group.command("forecast")
    async def weather_forecast(self, event: AstrMessageEvent, city: Optional[str] = None):
        """
        查看未来 3 天的天气预报 (基于 forecast/daily 接口)
        用法: /weather forecast <城市>
        示例: /weather forecast 上海
        """
        self.logger.info(f"User called /weather forecast with city: {city}")

        if not city:
            city = self.default_city

        if not self.api_key:
            self.logger.warning("API Key is not configured. Cannot query forecast.")
            yield event.plain_result("未配置 OpenWeatherMap API Key，无法查询天气。请在管理面板中配置后再试。")
            return

        data_list = await self.get_forecast_weather_by_city(city)
        if data_list is None:
            self.logger.warning(f"Failed to get forecast weather for city={city}")
            yield event.plain_result(f"查询 [{city}] 的未来天气失败，请稍后再试。")
            return

        # 渲染为图片
        forecast_img_url = await self.render_forecast_weather(city, data_list)
        yield event.image_result(forecast_img_url)

    # weather alerts
    @weather_group.command("alerts")
    async def weather_alerts(self, event: AstrMessageEvent, city: Optional[str] = None):
        """
        查询城市的天气预警
        用法: /weather alerts <城市>
        示例: /weather alerts 上海
        但在 v2.5 中并无 alerts 接口，这里示例仅返回空信息。
        """
        self.logger.info(f"User called /weather alerts with city: {city}")

        # 这里只演示提示用户“暂不支持”
        # 如果你有自己额外的数据源，可以在这里进行查询
        yield event.plain_result("抱歉，当前使用的 2.5 API 不支持天气预警功能。")

    # weather help
    @weather_group.command("help")
    async def weather_help(self, event: AstrMessageEvent):
        """
        显示天气插件的帮助信息
        /weather help
        """
        self.logger.info("User called /weather help")
        msg = (
            "=== 天气插件命令列表 ===\n"
            "/weather current <城市>  查看当前天气\n"
            "/weather forecast <城市> 查看未来 3 天预报\n"
            "/weather alerts <城市>   (2.5 API 暂不支持)\n"
            "/weather help            显示本帮助\n"
        )
        yield event.plain_result(msg)

    # =============================
    # 2) LLM Function-Calling (可选)
    # =============================
    @llm_tool(name="get_current_weather")
    async def get_current_weather_tool(self, event: AstrMessageEvent, city: str) -> MessageEventResult:
        """
        获取当前天气并返回图片

        Args:
            city (string): 城市名称
        """
        self.logger.debug(f"LLM called get_current_weather_tool with city={city}")

        if not city:
            city = self.default_city

        if not self.api_key:
            self.logger.warning("API Key is missing in get_current_weather_tool.")
            yield event.plain_result("抱歉，无法查询天气（缺少 API Key）")
            return

        data = await self.get_current_weather_by_city(city)
        if data is None:
            self.logger.warning(f"get_current_weather_tool failed to retrieve weather for {city}")
            yield event.plain_result(f"查询 [{city}] 天气失败，请稍后再试。")
            return

        img_url = await self.render_current_weather(data)
        yield event.image_result(img_url)

    @llm_tool(name="get_forecast_weather")
    async def get_forecast_weather_tool(self, event: AstrMessageEvent, city: str) -> MessageEventResult:
        """
        获取未来 3 天天气并返回图片

        Args:
            city (string): 城市名称
        """
        self.logger.debug(f"LLM called get_forecast_weather_tool with city={city}")

        if not city:
            city = self.default_city

        if not self.api_key:
            self.logger.warning("API Key is missing in get_forecast_weather_tool.")
            yield event.plain_result("抱歉，无法查询天气（缺少 API Key）")
            return

        data_list = await self.get_forecast_weather_by_city(city)
        if data_list is None:
            self.logger.warning(f"get_forecast_weather_tool failed to retrieve forecast for {city}")
            yield event.plain_result(f"查询 [{city}] 天气失败，请稍后再试。")
            return

        forecast_img_url = await self.render_forecast_weather(city, data_list)
        yield event.image_result(forecast_img_url)

    # =============================
    # 3) 核心业务: 获取天气数据
    # =============================

    async def get_current_weather_by_city(self, city: str) -> Optional[dict]:
        """
        1) 根据城市名获取 (lat, lon)
        2) 调用 "2.5/weather" 获取当前天气
        3) 返回 dict {city, desc, temp, feels_like, humidity, wind_speed}
        """
        self.logger.debug(f"Entering get_current_weather_by_city with city={city}")
        coords = await self.get_city_coords(city)
        if coords is None:
            self.logger.error(f"get_current_weather_by_city: coords is None for city={city}")
            return None

        lat, lon = coords
        url = "https://api.openweathermap.org/data/2.5/weather"  # v2.5 端点
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "zh_cn"
        }

        self.logger.debug(f"Requesting current weather: city={city}, lat={lat}, lon={lon}, params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Response status for current weather: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"Current weather raw data: {data}")
                        # data 中包含主键 "main", "weather", "wind" 等
                        # 例如: data["main"]["temp"], data["wind"]["speed"]
                        # 下面是简要解析
                        main_part = data.get("main", {})
                        weather_arr = data.get("weather", [{}])
                        wind_part = data.get("wind", {})

                        desc = weather_arr[0].get("description", "暂无描述")
                        temp = main_part.get("temp")
                        feels_like = main_part.get("feels_like")
                        humidity = main_part.get("humidity")
                        wind_speed = wind_part.get("speed", 0)

                        return {
                            "city": city,
                            "desc": desc,
                            "temp": temp,
                            "feels_like": feels_like,
                            "humidity": humidity,
                            "wind_speed": wind_speed
                        }
                    else:
                        self.logger.error(f"get_current_weather_by_city status: {resp.status}, city={city}")
                        return None
        except Exception as e:
            self.logger.error(f"[WeatherPlugin] get_current_weather_by_city error: {e}")
            return None

    async def get_forecast_weather_by_city(self, city: str) -> Optional[List[dict]]:
        """
        1) 根据城市名获取 (lat, lon)
        2) 调用 "2.5/forecast/daily" 获取未来几天的预报（旧版接口）
        3) 返回列表，每个元素包含 {date_str, weekday_str, desc, temp_*}
           这里演示取未来 3 天。free 版一般默认返回 7 天数据
        """
        self.logger.debug(f"Entering get_forecast_weather_by_city with city={city}")
        coords = await self.get_city_coords(city)
        if coords is None:
            self.logger.error(f"get_forecast_weather_by_city: coords is None for city={city}")
            return None

        lat, lon = coords
        url = "https://api.openweathermap.org/data/2.5/forecast/daily"  # 旧版接口
        params = {
            "lat": lat,
            "lon": lon,
            "cnt": 4,  # 获取“今天+后3天”，共4天
            "appid": self.api_key,
            "units": "metric",
            "lang": "zh_cn"
        }

        self.logger.debug(f"Requesting forecast weather: city={city}, lat={lat}, lon={lon}, params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Response status for forecast weather: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"Forecast weather raw data: {data}")

                        # data["list"] 是天数列表
                        daily_list = data.get("list")
                        if not daily_list or len(daily_list) < 2:
                            self.logger.error("Not enough daily data for forecast.")
                            return None

                        # daily_list[0] 表示当天, daily_list[1..] 表示后面几天
                        # 我们只要后面3天
                        slice_days = daily_list[1:]  # 取下标 1..(cnt-1)

                        result = []
                        for day_data in slice_days:
                            dt = day_data.get("dt", 0)
                            weather_info = day_data.get("weather", [{}])
                            desc = weather_info[0].get("description", "暂无描述")

                            temp_info = day_data.get("temp", {})
                            temp_day = temp_info.get("day")
                            temp_night = temp_info.get("night")
                            temp_min = temp_info.get("min")
                            temp_max = temp_info.get("max")

                            humidity = day_data.get("humidity")
                            wind_speed = day_data.get("speed", 0)  # 在 daily forecast 里，风速字段是 "speed"

                            # V2.5 daily forecast 里没有 "timezone_offset" 字段
                            # 只能直接用 UTC 时间戳 dt，假设本地时区自行计算或直接显示日期
                            date_str, weekday_str = self.format_day(dt)
                            result.append({
                                "date_str": date_str,
                                "weekday_str": weekday_str,
                                "desc": desc,
                                "temp_day": temp_day,
                                "temp_night": temp_night,
                                "temp_min": temp_min,
                                "temp_max": temp_max,
                                "humidity": humidity,
                                "wind_speed": wind_speed,
                            })
                        return result
                    else:
                        self.logger.error(f"get_forecast_weather_by_city status: {resp.status}, city={city}")
                        return None
        except Exception as e:
            self.logger.error(f"[WeatherPlugin] get_forecast_weather_by_city error: {e}")
            return None

    async def get_alerts_by_city(self, city: str) -> Optional[List[dict]]:
        """
        在 v2.5 中并无官方 alerts 接口，因此这里统一返回一个空列表
        或者可以实现为返回 None
        """
        self.logger.debug(f"Entering get_alerts_by_city with city={city}")
        self.logger.warning("v2.5 API does not provide weather alerts. Returning empty list.")
        return []

    # =============================
    # 4) GeoCoding: 城市 -> (lat, lon)
    # =============================
    async def get_city_coords(self, city: str) -> Optional[tuple]:
        """
        调用 Geocoding API，根据城市名称获取 (lat, lon)
        参考: https://openweathermap.org/api/geocoding-api
        示例: https://api.openweathermap.org/geo/1.0/direct?q=London&limit=1&appid={API key}
        """
        self.logger.debug(f"Entering get_city_coords with city={city}")
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        params = {
            "q": city,
            "limit": 1,
            "appid": self.api_key
        }
        self.logger.debug(f"Requesting coords with {geo_url}, params={params}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(geo_url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Response status for geocoding: {resp.status}")
                
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"Geo raw data: {data}")

                        if not data:
                            self.logger.error(f"地理编码API：城市[{city}]未找到坐标")
                            return None

                        lat = data[0]["lat"]
                        lon = data[0]["lon"]
                        self.logger.info(f"Got coords for city={city}: lat={lat}, lon={lon}")
                        return (lat, lon)
                    else:
                        self.logger.error(f"地理编码API：状态码 {resp.status} for city={city}")
                        return None

        except Exception as e:
            self.logger.error(f"[WeatherPlugin] get_city_coords error: {e}")
            self.logger.error(traceback.format_exc())  # 额外输出完整堆栈
            return None

    # =============================
    # 5) 渲染为图片
    # =============================
    async def render_current_weather(self, data: dict) -> str:
        """
        渲染当前天气的 HTML
        """
        self.logger.debug(f"Rendering current weather for {data}")
        url = await self.html_render(
            CURRENT_WEATHER_TEMPLATE,
            {
                "city": data["city"],
                "desc": data["desc"],
                "temp": data["temp"],
                "feels_like": data["feels_like"],
                "humidity": data["humidity"],
                "wind_speed": data["wind_speed"]
            },
            return_url=True
        )
        self.logger.debug(f"Current weather image URL: {url}")
        return url

    async def render_forecast_weather(self, city: str, days_data: List[dict]) -> str:
        """
        渲染未来 3 天的天气预报
        """
        self.logger.debug(f"Rendering forecast weather for city={city}, days={days_data}")
        url = await self.html_render(
            FORECAST_TEMPLATE,
            {
                "city": city,
                "days": days_data,
                "total_days": len(days_data)
            },
            return_url=True
        )
        self.logger.debug(f"Forecast weather image URL: {url}")
        return url

    async def render_alerts(self, city: str, alerts: List[dict]) -> str:
        """
        渲染天气预警信息 (此处为演示，v2.5 无法获取实际预警)
        """
        self.logger.debug(f"Rendering alerts for city={city}, alerts={alerts}")
        url = await self.html_render(
            ALERTS_TEMPLATE,
            {
                "city": city,
                "alerts": alerts
            },
            return_url=True
        )
        self.logger.debug(f"Alerts image URL: {url}")
        return url

    # =============================
    # 6) 工具方法：格式化日期/时间戳
    # =============================
    def format_day(self, unix_ts: int) -> tuple:
        """
        将 daily 的 dt 转化为 yyyy-mm-dd 格式和周几
        注: V2.5 daily forecast 没有 timezone_offset
        这里直接用 UTC 时间戳 dt
        """
        dt_obj = datetime.datetime.utcfromtimestamp(unix_ts)
        date_str = dt_obj.strftime("%Y-%m-%d")
        weekday_str = ["周一","周二","周三","周四","周五","周六","周日"][dt_obj.weekday()]
        return date_str, weekday_str

    def format_timestamp(self, unix_ts: Optional[int], tz_offset: Optional[int] = 0) -> str:
        """
        对 alerts 里日期的格式化，这里不实际使用
        """
        if not unix_ts:
            return "N/A"
        local_ts = unix_ts + (tz_offset or 0)
        dt_obj = datetime.datetime.utcfromtimestamp(local_ts)
        return dt_obj.strftime("%Y-%m-%d %H:%M")
