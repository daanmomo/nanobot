/**
 * WeChat Bridge for nanobot using Wechaty.
 *
 * This bridge connects to WeChat via Wechaty and forwards messages
 * to nanobot via WebSocket.
 *
 * Supported Puppets:
 * - wechaty-puppet-wechat4u (default, UOS protocol)
 * - wechaty-puppet-padlocal (iPad protocol, requires token)
 * - wechaty-puppet-xp (Windows WeChat)
 */

import { WechatyBuilder, ScanStatus, Message, Contact } from 'wechaty';
import { WebSocketServer, WebSocket } from 'ws';
import qrcode from 'qrcode-terminal';

const PORT = parseInt(process.env.BRIDGE_PORT || '3002');
const PUPPET = process.env.WECHATY_PUPPET || 'wechaty-puppet-wechat4u';
const PUPPET_TOKEN = process.env.WECHATY_PUPPET_TOKEN || '';

interface BridgeMessage {
  type: string;
  [key: string]: unknown;
}

class WeChatBridge {
  private wss: WebSocketServer;
  private clients: Set<WebSocket> = new Set();
  private bot: ReturnType<typeof WechatyBuilder.build> | null = null;
  private isLoggedIn = false;

  constructor(port: number) {
    this.wss = new WebSocketServer({ port });
    console.log(`🌐 WebSocket server listening on port ${port}`);

    this.wss.on('connection', (ws) => {
      console.log('📡 Client connected');
      this.clients.add(ws);

      // Send current status
      this.send(ws, {
        type: 'status',
        status: this.isLoggedIn ? 'logged_in' : 'waiting_login',
      });

      ws.on('message', async (data) => {
        try {
          const msg = JSON.parse(data.toString());
          await this.handleClientMessage(msg);
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      });

      ws.on('close', () => {
        console.log('📡 Client disconnected');
        this.clients.delete(ws);
      });
    });
  }

  async start(): Promise<void> {
    const puppetOptions: Record<string, unknown> = {};

    // Configure puppet-specific options
    if (PUPPET_TOKEN) {
      puppetOptions.token = PUPPET_TOKEN;
    }

    this.bot = WechatyBuilder.build({
      name: 'nanobot-wechat',
      puppet: PUPPET,
      puppetOptions,
    });

    // Handle QR code scan
    this.bot.on('scan', (qrCode: string, status: ScanStatus) => {
      if (status === ScanStatus.Waiting || status === ScanStatus.Timeout) {
        console.log('\n📱 Scan QR code to login:\n');
        qrcode.generate(qrCode, { small: true });

        this.broadcast({
          type: 'qr',
          url: `https://wechaty.js.org/qrcode/${encodeURIComponent(qrCode)}`,
          qr_terminal: qrCode,
          status,
        });
      }
    });

    // Handle login
    this.bot.on('login', async (user: Contact) => {
      console.log(`✅ Logged in as: ${user.name()}`);
      this.isLoggedIn = true;

      this.broadcast({
        type: 'login',
        user_name: user.name(),
        user_id: user.id,
      });

      this.broadcast({
        type: 'status',
        status: 'logged_in',
      });
    });

    // Handle logout
    this.bot.on('logout', (user: Contact) => {
      console.log(`👋 Logged out: ${user.name()}`);
      this.isLoggedIn = false;

      this.broadcast({
        type: 'logout',
        user_name: user.name(),
      });

      this.broadcast({
        type: 'status',
        status: 'logged_out',
      });
    });

    // Handle incoming messages
    this.bot.on('message', async (msg: Message) => {
      // Skip self messages
      if (msg.self()) return;

      const talker = msg.talker();
      const room = msg.room();
      const text = msg.text();

      // Skip empty messages
      if (!text) return;

      const messageData: BridgeMessage = {
        type: 'message',
        id: msg.id,
        sender: talker.id,
        sender_name: talker.name(),
        content: text,
        timestamp: msg.date().getTime(),
        is_self: false,
      };

      if (room) {
        messageData.room = room.id;
        messageData.room_name = await room.topic();
        messageData.is_group = true;

        // Check if bot is mentioned
        const mentionSelf = await msg.mentionSelf();
        messageData.mention_self = mentionSelf;
      } else {
        messageData.is_group = false;
      }

      console.log(
        `📨 ${room ? `[${messageData.room_name}] ` : ''}${talker.name()}: ${text.substring(0, 50)}...`
      );

      this.broadcast(messageData);
    });

    // Handle errors
    this.bot.on('error', (error: Error) => {
      console.error('❌ Bot error:', error);
      this.broadcast({
        type: 'error',
        error: error.message,
      });
    });

    console.log('🤖 Starting Wechaty...');
    await this.bot.start();
  }

  private async handleClientMessage(msg: BridgeMessage): Promise<void> {
    if (msg.type === 'send') {
      await this.sendMessage(msg.to as string, msg.text as string);
    }
  }

  private async sendMessage(to: string, text: string): Promise<void> {
    if (!this.bot || !this.isLoggedIn) {
      console.error('Cannot send message: not logged in');
      return;
    }

    try {
      // Try to find as contact first
      const contact = await this.bot.Contact.find({ id: to });
      if (contact) {
        await contact.say(text);
        console.log(`📤 Sent to ${contact.name()}: ${text.substring(0, 50)}...`);
        return;
      }

      // Try as room
      const room = await this.bot.Room.find({ id: to });
      if (room) {
        await room.say(text);
        console.log(`📤 Sent to room ${await room.topic()}: ${text.substring(0, 50)}...`);
        return;
      }

      console.error(`Cannot find contact or room: ${to}`);
    } catch (e) {
      console.error('Failed to send message:', e);
    }
  }

  private send(ws: WebSocket, data: BridgeMessage): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  private broadcast(data: BridgeMessage): void {
    const json = JSON.stringify(data);
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(json);
      }
    }
  }
}

// Main
const bridge = new WeChatBridge(PORT);
bridge.start().catch(console.error);
