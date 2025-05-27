import aiohttp
import logging
import datetime
from typing import Optional, List, Dict
import traceback

from astrbot.api.all import (
    Star, Context, register,
    AstrMessageEvent, command_group, command,
    MessageEventResult, llm_tool
)
from astrbot.api.event import filter

# ==============================
# 1) HTML 模板
# ==============================

CURRENT_WEATHER_TEMPLATE = """
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 1280px; /* 确保匹配 render 预设的图片尺寸 */
      height: 720px;
      background-color: #fff;
    }
    .weather-container {
      width: 100%;
      height: 100%;
      padding: 8px;
      display: flex;
      flex-direction: column;
      justify-content: center; /* 垂直居中 */
      align-items: center; /* 水平居中 */
      background-color: #ffffff;
      color: #333;
      font-family: sans-serif;
      font-size: 30px;
      border: 1px solid #ddd;
      border-radius: 8px;
    }
    .weather-container h2 {
      margin-top: 0;
      color: #4e6ef2;
      text-align: center;
      font-size: 40px;
    }
    .weather-info {
      margin-bottom: 10px;
    }
    .source-info {
      border-top: 1px solid #ddd;
      margin-top: 12px;
      padding-top: 12px;
      font-size: 16px;
      color: #999;
    }
  </style>
</head>
<body>
  <div class="weather-container">
    <h2>当前天气</h2>
    
    <div class="weather-info">
      <strong>城市:</strong> {{ city }}
    </div>
    <div class="weather-info">
      <strong>天气:</strong> {{ desc }}
    </div>
    <div class="weather-info">
      <strong>温度:</strong> {{ temp }}℃ (体感: {{ feels_like }}℃)
    </div>
    <div class="weather-info">
      <strong>湿度:</strong> {{ humidity }}%
    </div>
    <div class="weather-info">
      <strong>风速:</strong> {{ wind_speed }} km/h
    </div>
    
    <div class="source-info">
      数据来源: 心知天气（Seniverse） 免费API
    </div>
  </div>
</body>
</html>
"""

FORECAST_TEMPLATE = """
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 1280px;
      height: 720px;
      background-color: #fff;
    }
    .forecast-container {
      width: 100%;
      height: 100%;
      padding: 8px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      background-color: #fff;
      color: #333;
      font-family: sans-serif;
      font-size: 30px;
      border: 1px solid #ddd;
      border-radius: 8px;
    }
    .forecast-container h2 {
      margin-top: 0;
      color: #4e6ef2;
      text-align: center;
      font-size: 40px;
    }
    .city-info {
      margin-bottom: 8px;
    }
    .day-item {
      margin-bottom: 8px;
      border-bottom: 1px solid #eee;
      padding-bottom: 4px;
    }
    .day-title {
      font-weight: bold;
      color: #4e6ef2;
      margin-bottom: 4px;
    }
    .source-info {
      font-size: 16px;
      color: #999;
      margin-top: 12px;
      border-top: 1px solid #ddd;
      padding-top: 8px;
    }
  </style>
</head>
<body>
  <div class="forecast-container">
    <h2>未来{{ total_days }}天天气预报</h2>
    <div class="city-info">
      <strong>城市:</strong> {{ city }}
    </div>

    {% for day in days %}
    <div class="day-item">
      <div class="day-title">{{ day.date }}</div>
      <div><strong>白天:</strong> {{ day.text_day }} — {{ day.high }}℃</div>
      <div><strong>夜晚:</strong> {{ day.text_night }} — {{ day.low }}℃</div>
      <div><strong>湿度:</strong> {{ day.humidity }}%  <strong>风速:</strong> {{ day.wind_speed }} km/h</div>
    </div>
    {% endfor %}

    <div class="source-info">
      数据来源: 高德开放平台（Amap） 免费API
    </div>
  </div>
</body>
</html>
"""

@register(
    "astrbot_plugin_weather-Amap",
    "BB0813",
    "一个基于高德开放平台API的天气查询插件",
    "1.0.0",
    "https://github.com/BB0813/astrbot_plugin_weather-Amap"
)
class WeatherPlugin(Star):
    """
    这是一个调用高德开放平台API的天气查询插件示例。
    支持 /weather current /weather forecast /weather help
    - current: 查询当前实况
    - forecast: 查询未来4天天气预报
    """
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.logger = logging.getLogger("WeatherPlugin")
        self.logger.setLevel(logging.DEBUG)
        self.config = config
        # 使用配置中的 amap_api_key
        self.api_key = config.get("amap_api_key", "")
        self.default_city = config.get("default_city", "北京")
        # 新增配置项：send_mode，控制发送模式 "image" 或 "text"
        self.send_mode = config.get("send_mode", "image")
        self.logger.debug(f"WeatherPlugin initialized with API key: {self.api_key}, default_city: {self.default_city}, send_mode: {self.send_mode}")

    # =============================
    # 命令组 "weather"
    # =============================
    @command_group("weather")
    def weather_group(self):
        """
        天气相关功能命令组。
        使用方法：
        /weather <子指令> <城市或其它参数>
        子指令包括：current, forecast, help
        """
        pass

    @weather_group.command("current")
    async def weather_current(self, event: AstrMessageEvent, city: Optional[str] = None):
        """
        查看当前实况天气
        用法: /weather current <城市>
        示例: /weather current 北京
        """
        self.logger.info(f"User called /weather current with city={city}")
        if not city:
            city = self.default_city
        if not self.api_key:
            yield event.plain_result("未配置 Amap API Key，无法查询天气。请在管理面板中配置后再试。")
            return
        data = await self.get_current_weather_by_city(city)
        if data is None:
            yield event.plain_result(f"查询 [{city}] 的当前天气失败，请稍后再试。")
            return
        # 根据配置决定发送模式
        if self.send_mode == "image":
            result_img_url = await self.render_current_weather(data)
            yield event.image_result(result_img_url)
        else:
            text = (
                f"当前天气：\n"
                f"城市: {data['city']}\n"
                f"天气: {data['desc']}\n"
                f"温度: {data['temp']}℃\n"
                f"湿度: {data['humidity']}%\n"
                f"风速: {data['wind_speed']} km/h"
            )
            yield event.plain_result(text)

    @weather_group.command("forecast")
    async def weather_forecast(self, event: AstrMessageEvent, city: Optional[str] = None):
        """
        查看未来4天天气预报
        用法: /weather forecast <城市>
        示例: /weather forecast 北京
        """
        self.logger.info(f"User called /weather forecast with city={city}")
        if not city:
            city = self.default_city
        if not self.api_key:
            yield event.plain_result("未配置 Amap API Key，无法查询天气。请在管理面板中配置后再试。")
            return
        forecast_data = await self.get_forecast_weather_by_city(city)
        if forecast_data is None:
            yield event.plain_result(f"查询 [{city}] 的未来天气失败，请稍后再试。")
            return
        suggestion_data = await self.get_life_suggestion_by_city(city)
        # 根据配置决定发送模式
        if self.send_mode == "image":
            forecast_img_url = await self.render_forecast_weather(
                city,
                days_data=forecast_data,
                suggestions=suggestion_data
            )
            yield event.image_result(forecast_img_url)
        else:
            text = f"未来{len(forecast_data)}天天气预报\n城市: {city}\n"
            for day in forecast_data:
                text += (
                    f"{day['date']}: 白天: {day['text_day']} - {day['high']}℃, "
                    f"夜晚: {day['text_night']} - {day['low']}℃, "
                    f"湿度: {day['humidity']}%, "
                    f"风速: {day['wind_speed']} km/h\n"
                )
            if suggestion_data:
                text += "生活指数:\n"
                for s in suggestion_data:
                    text += f"{s['name']}: {s['brief']}\n"
            yield event.plain_result(text)

    @weather_group.command("help")
    async def weather_help(self, event: AstrMessageEvent):
        """
        显示天气插件的帮助信息
        用法: /weather help
        """
        self.logger.info("User called /weather help")
        msg = (
            "=== 高德开放平台插件命令列表 ===\n"
            "/weather current <城市>  查看当前实况\n"
            "/weather forecast <城市> 查看未来4天天气预报\n"
            "/weather help            显示本帮助\n"
        )
        yield event.plain_result(msg)

    # =============================
    # LLM Function-Calling (可选)
    # =============================
    @llm_tool(name="get_current_weather")
    async def get_current_weather_tool(self, event: AstrMessageEvent, city: str) -> MessageEventResult:
        '''当用户对某个城市的天气情况感兴趣时，用于获取当前天气信息。

        Args:
            city (string): 地点，例如：杭州，或者浙江杭州
        '''
        if not city:
            city = self.default_city
        data = await self.get_current_weather_by_city(city)
        if not data:
            yield event.plain_result(f"查询 [{city}] 天气失败，请稍后再试。")
            return
        if self.send_mode == "image":
            url = await self.render_current_weather(data)
            yield event.image_result(url)
        else:
            text = (
                f"当前天气：\n"
                f"城市: {data['city']}\n"
                f"天气: {data['desc']}\n"
                f"温度: {data['temp']}℃\n"
                f"湿度: {data['humidity']}%\n"
                f"风速: {data['wind_speed']} km/h"
            )
            yield event.plain_result(text)

    @llm_tool(name="get_forecast_weather")
    async def get_forecast_weather_tool(self, event: AstrMessageEvent, city: str) -> MessageEventResult:
        '''当用户对某个城市未来天气预报感兴趣时，用于获取天气预报信息。

        Args:
            city (string): 地点，例如：杭州，或者浙江杭州
        '''
        if not city:
            city = self.default_city
        forecast_data = await self.get_forecast_weather_by_city(city)
        suggestion_data = await self.get_life_suggestion_by_city(city)
        if not forecast_data:
            yield event.plain_result(f"查询 [{city}] 天气失败，请稍后再试。")
            return
        if self.send_mode == "image":
            url = await self.render_forecast_weather(city, forecast_data, suggestion_data)
            yield event.image_result(url)
        else:
            text = f"未来{len(forecast_data)}天天气预报\n城市: {city}\n"
            for day in forecast_data:
                text += (
                    f"{day['date']}: 白天: {day['text_day']} - {day['high']}℃, "
                    f"夜晚: {day['text_night']} - {day['low']}℃, "
                    f"湿度: {day['humidity']}%, "
                    f"风速: {day['wind_speed']} km/h\n"
                )
            if suggestion_data:
                text += "生活指数:\n"
                for s in suggestion_data:
                    text += f"{s['name']}: {s['brief']}\n"

            yield event.plain_result(text)

    # =============================
    # 核心逻辑
    # =============================
    async def get_current_weather_by_city(self, city: str) -> Optional[dict]:
        """
        调用高德开放平台API，返回城市当前实况
        """
        self.logger.debug(f"get_current_weather_by_city city={city}")
        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "base"
        }
        self.logger.debug(f"Requesting: {url}, params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"Amap now raw data: {data}")
                        lives = data.get("lives", [])
                        if not lives:
                            return None
                        now = lives[0]
                        desc = now.get("weather", "未知")
                        temp = now.get("temperature", "0")
                        humidity = now.get("humidity", "0")
                        wind_speed = now.get("windpower", "0")
                        return {
                            "city": city,
                            "desc": desc,
                            "temp": temp,
                            "humidity": humidity,
                            "wind_speed": wind_speed
                        }

                    else:
                        self.logger.error(f"get_current_weather_by_city status={resp.status}")
                        return None
        except Exception as e:
            self.logger.error(f"get_current_weather_by_city error: {e}")
            self.logger.error(traceback.format_exc())
            return None

    async def get_forecast_weather_by_city(self, city: str) -> Optional[List[dict]]:
        """
        调用高德开放平台API，获取未来4天天气预报
        """
        self.logger.debug(f"get_forecast_weather_by_city city={city}")
        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "all"
        }
        self.logger.debug(f"Requesting forecast: {url}, params={params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(f"Amap daily raw data: {data}")
                        forecasts = data.get("forecasts", [])
                        if not forecasts:
                            return None
                        daily_list = forecasts[0].get("casts", [])
                        if not daily_list:
                            return None
                        result = []
                        for day_data in daily_list:
                            date = day_data.get("date", "1970-01-01")
                            text_day = day_data.get("dayweather", "未知")
                            text_night = day_data.get("nightweather", "未知")

                            high = day_data.get("daytemp", "0")
                            low = day_data.get("nighttemp", "0")
                            humidity = day_data.get("humidity", "0")
                            wind_speed = day_data.get("daypower", "0")
                            result.append({
                                "date": date,
                                "text_day": text_day,
                                "text_night": text_night,
                                "high": high,
                                "low": low,
                                "humidity": humidity,
                                "wind_speed": wind_speed
                            })
                        return result
                    else:
                        self.logger.error(f"get_forecast_weather_by_city status={resp.status}")
                        return None
        except Exception as e:
            self.logger.error(f"get_forecast_weather_by_city error: {e}")
            self.logger.error(traceback.format_exc())
            return None

    async def get_life_suggestion_by_city(self, city: str) -> Optional[List[dict]]:
        """
        调用高德开放平台API，获取生活指数
        """
        self.logger.debug(f"get_life_suggestion_by_city city={city}")
        # 高德开放平台不提供生活指数API，故此功能暂时无法实现
        return None

    async def render_current_weather(self, data: dict) -> str:
        """
        渲染当前天气图文信息
        """
        self.logger.debug(f"render_current_weather for {data}")
        url = await self.html_render(
            CURRENT_WEATHER_TEMPLATE,
            {
                "city": data["city"],
                "desc": data["desc"],
                "temp": data["temp"],
                "humidity": data["humidity"],
                "wind_speed": data["wind_speed"]
            },
            return_url=True
        )
        return url

    async def render_forecast_weather(self, city: str, days_data: List[dict], suggestions: Optional[List[dict]] = None) -> str:
        """
        渲染未来4天天气预报图文信息
        """
        self.logger.debug(f"render_forecast_weather for city={city}, days={days_data}, suggestions={suggestions}")
        url = await self.html_render(
            FORECAST_TEMPLATE,
            {
                "city": city,
                "days": days_data,
                "total_days": len(days_data),
                "suggestions": suggestions or []
            },
            return_url=True
        )
        return url
