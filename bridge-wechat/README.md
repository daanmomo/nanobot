# WeChat Bridge for nanobot

基于 Wechaty 的微信桥接服务，通过 WebSocket 与 nanobot 通信。

## 支持的 Puppet

| Puppet | 协议 | 说明 |
|--------|------|------|
| wechaty-puppet-wechat4u | UOS | 默认，免费，基于 UOS 微信协议 |
| wechaty-puppet-padlocal | iPad | 付费，稳定性最好 |
| wechaty-puppet-xp | Windows | 需要运行 Windows 微信客户端 |

## 安装

```bash
cd bridge-wechat
npm install
npm run build
```

## 运行

### 使用默认 puppet (wechat4u)

```bash
npm start
```

### 使用 PadLocal (推荐，需要 token)

```bash
WECHATY_PUPPET=wechaty-puppet-padlocal \
WECHATY_PUPPET_TOKEN=your_padlocal_token \
npm start
```

### 自定义端口

```bash
BRIDGE_PORT=3002 npm start
```

## 配置 nanobot

在 `~/.nanobot/config.json` 中添加：

```json
{
  "channels": {
    "wechat": {
      "enabled": true,
      "mode": "websocket",
      "bridge_url": "ws://localhost:3002"
    }
  }
}
```

## 消息格式

### 入站消息 (bridge -> nanobot)

```json
{
  "type": "message",
  "id": "message_id",
  "sender": "wxid_xxx",
  "sender_name": "张三",
  "content": "你好",
  "timestamp": 1234567890,
  "is_group": false
}
```

群消息：

```json
{
  "type": "message",
  "id": "message_id",
  "sender": "wxid_xxx",
  "sender_name": "张三",
  "room": "room_id",
  "room_name": "测试群",
  "content": "你好",
  "timestamp": 1234567890,
  "is_group": true,
  "mention_self": true
}
```

### 出站消息 (nanobot -> bridge)

```json
{
  "type": "send",
  "to": "wxid_xxx",
  "text": "回复内容"
}
```

### 状态消息

```json
{
  "type": "status",
  "status": "logged_in"
}
```

```json
{
  "type": "qr",
  "url": "https://...",
  "qr_terminal": "qr_code_string"
}
```

## 获取 PadLocal Token

1. 访问 [pad-local.com](https://pad-local.com)
2. 注册并购买 token
3. 设置环境变量 `WECHATY_PUPPET_TOKEN`

## 注意事项

- wechat4u puppet 可能不稳定，建议使用 PadLocal
- 首次登录需要扫描二维码
- 群消息需要 @机器人 才会响应（可在 nanobot 配置中关闭）
- 请遵守微信使用规范，避免频繁发送消息
