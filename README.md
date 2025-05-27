# Weather Plugin

基于 [**高德开放平台（Amap）**](https://lbs.amap.com/) 的免费 API，为 [AstrBot](https://github.com/Soulter/AstrBot) 提供 `/weather` 指令，支持查询当前天气、未来 4 天预报等功能。

## 功能特性

1. **当前天气**：输入 `/weather current <城市>` 即可查询该城市的实时天气信息（气温、湿度、风速、天气现象等）。  
2. **未来预报**：输入 `/weather forecast <城市>` 可查看未来 4 天的天气预报。  
3. **可配置**：通过管理面板或配置文件修改 **Amap** API Key、默认城市等。  
4. **可选 LLM Function-Calling**：在开启 function-calling 的情况下，LLM 可自动调用插件提供的天气查询工具函数，实现自动获取天气结果。

## 安装与配置

1. 将插件文件夹（包含 `main.py`, `_conf_schema.json`, `plugin.yaml` 等）放入 AstrBot 的插件目录。  
2. 重启 AstrBot，进入管理面板找到本插件，在“配置”中填写你的 **Amap** API Key（免费版可用）。  
3. 如需修改默认城市或其他选项，可在管理面板的插件配置处，或在 `config` 文件中进行更改。

## 使用示例

- **查询当前天气：**
  ```bash
  /weather current 北京
  ```
  插件返回一个图文卡片，展示温度、湿度、风速等信息。

- **查询未来 4 天预报：**
  ```bash
  /weather forecast 上海
  ```
  插件返回一张包含未来 4 天天气情况的图片。

- **查看插件帮助：**
  ```bash
  /weather help
  ```

## 注意事项

- 高德开放平台免费版支持 **4 天预报**，以及当前天气的部分字段。若需更多高级功能或更长预报天数，请参考[官方文档](https://lbs.amap.com/)并升级套餐。  
- 如果使用中遇到 **超时** 或 **无结果**，请先检查日志，确认网络可访问 `restapi.amap.com`，以及你的 API Key 填写是否正确。

## 开源协议

本插件的源码位于 [GitHub](https://github.com/BB0813/astrbot_plugin_weather-Amap)。欢迎提出 Issue 或 PR 来帮助我们改进插件。

## 🤝 特别感谢

本项目基于w33d大佬的心知天气插件二次开发: [https://github.com/Last-emo-boy/astrbot_plugin_weather](https://github.com/Last-emo-boy/astrbot_plugin_weather)
