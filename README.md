# Weather Plugin

基于 **OpenWeatherMap v2.5** 的天气查询插件，为 [AstrBot](https://github.com/Soulter/AstrBot) 提供 `/weather` 指令，支持查询当前天气、未来 3 天预报等功能。

## 功能特性

1. **当前天气**：输入 `/weather current <城市>` 即可查询该城市的实时天气信息。
2. **未来预报**：输入 `/weather forecast <城市>` 可查看未来 3 天的天气预报。
3. **自定义配置**：通过管理面板或配置文件修改 API Key、默认城市等。
4. **可选 LLM Function-Calling**：在开启 function-calling 的情况下，LLM 可自动调用插件提供的天气查询工具函数。

## 安装与配置

1. 将插件文件夹（包含 `main.py`, `_conf_schema.json`, `plugin.yaml` 等）放入 AstrBot 的插件目录。
2. 重启 AstrBot，进入管理面板找到本插件，在“配置”中填写你的 **OpenWeatherMap** API Key（免费版也可使用，但功能有限）。
3. 如需修改默认城市或其他选项，可在管理面板的插件配置处或在 `config` 文件中进行更改。

## 使用示例

- **查询当前天气：**
  ```
  /weather current 上海
  ```
  插件会返回一个图文卡片，展示温度、湿度、风速等信息。

- **查询未来 3 天预报：**
  ```
  /weather forecast 上海
  ```
  插件会返回一个包含后 3 天天气情况的图片。

- **查看插件帮助：**
  ```
  /weather help
  ```

## 注意事项

- 本插件使用的是 **OpenWeatherMap v2.5** 接口，其中 `2.5/forecast/daily` 是官方旧版接口，若无法使用，可自行切换到 `2.5/forecast`（3 小时步进）。
- 天气预警 (`alerts`) 功能在 2.5 中暂不支持，会提示“当前版本不支持”。
- 如果你在使用中遇到 **超时** 或 **无结果**，请先检查日志，确认网络可访问 `api.openweathermap.org`，以及 API Key 是否正确。

## 开源协议

本插件的源码位于 [GitHub](https://github.com/Last-emo-boy/astrbot_plugin_weather)。