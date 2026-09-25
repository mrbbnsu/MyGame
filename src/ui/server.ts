/**
 * F1/WO-008：本地 UI 服务 —— 静态文件 + /api/* 转发 Adapter + 精简卡表。
 *
 * 铁律（工单 K1/K2、architecture-v2）：零 npm 依赖；只监听 127.0.0.1；
 * 前端一切经 /api（不 spawn 进程、不碰二进制）；协议类型单一来源 = src/adapter。
 * 热座（K6）：viewer 由服务端强制为「当前应答玩家」（pending.player ?? turn_player），
 * 前端无法请求其他视角。
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { AdapterClient, AdapterClientError } from '../adapter/client.ts';
import type {
  AdapterEvent,
  DuelState,
  GetStateResult,
  NewDuelResult,
  RespondResult,
} from '../adapter/types.ts';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)),
                               '..', '..');
const PUBLIC_DIR = path.join(REPO_ROOT, 'src', 'ui', 'public');
const DATA_DIR = path.join(REPO_ROOT, 'data');
const LOG_TAIL = 120;

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
  '.jpg': 'image/jpeg',
};

/** 精简卡表条目（工单 K2 字段） */
export interface CardInfo {
  id: number;
  name: string;
  card_type: string;
  flags: string[];
  race: string | null;
  attribute: string | null;
  level: number | null;
  atk: number | null;
  def: number | null;
  desc: string;
}

/** 解析 cards_clean 的 flags 字符串（"['NORMAL']" → ['NORMAL']） */
function parseFlags(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String);
  if (typeof raw !== 'string') return [];
  const inner = raw.trim().replace(/^\[/, '').replace(/\]$/, '').trim();
  if (!inner) return [];
  return inner.split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
    .filter(Boolean);
}

function numOrNull(v: unknown): number | null {
  const n = typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : NaN;
  return Number.isFinite(n) ? n : null;
}

export function buildCardTable(cardsFile: string): Record<string, CardInfo> {
  const raw = JSON.parse(fs.readFileSync(cardsFile, 'utf8')) as Record<
    string, unknown>[];
  const table: Record<string, CardInfo> = {};
  for (const c of raw) {
    const id = numOrNull(c.id);
    if (id === null) continue;
    table[String(id)] = {
      id,
      name: String(c.cn_name ?? c.name ?? `#${id}`),
      card_type: String(c.card_type ?? ''),
      flags: parseFlags(c.flags),
      race: c.race == null || c.race === '' ? null : String(c.race),
      attribute: c.attribute == null || c.attribute === ''
        ? null : String(c.attribute),
      level: numOrNull(c.level),
      atk: numOrNull(c.atk),
      def: numOrNull(c.def),
      desc: String(c.desc ?? ''),
    };
  }
  return table;
}

interface DuelCtx {
  state: DuelState;
  log: AdapterEvent[];
}

export interface UiServerOptions {
  port?: number;
  decksDir?: string;
  cardsFile?: string;
  /** 测试注入：不 spawn 真 adapter 时用（默认真实 spawn） */
  adapter?: AdapterClient;
}

export interface UiServer {
  port: number;
  adapter: AdapterClient;
  cardCount: number;
  close(): Promise<void>;
}

export function startServer(opts: UiServerOptions = {}): Promise<UiServer> {
  const cardsFile = opts.cardsFile ?? path.join(DATA_DIR, 'cards_clean.json');
  const decksDir = opts.decksDir ?? path.join(DATA_DIR, 'decks');
  const cards = buildCardTable(cardsFile);
  const adapter = opts.adapter ?? new AdapterClient();
  const ownAdapter = !opts.adapter;

  const ctx: { duel: DuelCtx | null } = { duel: null };

  /** 热座 viewer（K6）：当前应答玩家 */
  const computeViewer = (state: DuelState): 0 | 1 =>
    state.pending ? state.pending.player : state.turn_player;

  const deckSummaries = (): { file: string; name: string; desc: string;
                               count: number }[] => {
    if (!fs.existsSync(decksDir)) return [];
    return fs.readdirSync(decksDir).filter((f) => f.endsWith('.json'))
      .map((f) => {
        try {
          const d = JSON.parse(
            fs.readFileSync(path.join(decksDir, f), 'utf8')) as {
            name?: string; desc?: string; cards?: number[];
          };
          return { file: f, name: d.name ?? f, desc: d.desc ?? '',
                   count: d.cards?.length ?? 0 };
        } catch {
          return { file: f, name: f, desc: '（解析失败）', count: 0 };
        }
      });
  };

  const loadDeck = (file: string): number[] => {
    if (!/^[\w.-]+\.json$/.test(file)) {
      throw new AdapterClientError('BAD_REQUEST', `非法卡组名: ${file}`);
    }
    const p = path.join(decksDir, file);
    const d = JSON.parse(fs.readFileSync(p, 'utf8')) as { cards?: number[] };
    if (!Array.isArray(d.cards) || d.cards.length === 0) {
      throw new AdapterClientError('BAD_REQUEST', `卡组 ${file} 无卡`);
    }
    for (const c of d.cards) {
      if (!Number.isInteger(c) || c < 0) {
        throw new AdapterClientError('BAD_REQUEST', `卡组 ${file} 有非法 passcode`);
      }
    }
    return d.cards;
  };

  const apiError = (code: string, message: string): string =>
    JSON.stringify({ ok: false, error: { code, message } });

  async function handleApi(req: http.IncomingMessage, url: URL):
    Promise<string> {
    const route = `${req.method} ${url.pathname}`;
    if (route === 'GET /api/health') {
      let ready: boolean | null = null;
      let coreVersion: string | null = null;
      try {
        const info = await adapter.ensureReady();
        ready = true;
        coreVersion = info.core_api_version;
      } catch {
        ready = false;
      }
      return JSON.stringify({ ok: true, adapter_ready: ready,
                              core_api_version: coreVersion,
                              duel_active: ctx.duel !== null,
                              card_count: Object.keys(cards).length });
    }
    if (route === 'GET /api/cards') {
      return JSON.stringify({ ok: true, result: cards });
    }
    if (route === 'GET /api/decks') {
      return JSON.stringify({ ok: true, result: deckSummaries() });
    }
    if (route === 'POST /api/new_duel') {
      const body = await readJson(req);
      const decks = [loadDeck(String(body.player_deck)),
                     loadDeck(String(body.opponent_deck))];
      const seed = [(Date.now() & 0xffffffff) >>> 0, 1, 2, 3];
      // 开局 viewer 恒为 0（先攻玩家）：state 与事件流一并过滤，
      // 对手起手手牌不泄漏到浏览器（K3/K6）
      const res = (await adapter.newDuel({
        decks: decks as [number[], number[]],
        opts: { lp: 8000, start_hand: 5, seed },
        viewer: 0,
      })) as NewDuelResult;
      ctx.duel = { state: res.state, log: [...res.events] };
      return JSON.stringify({
        ok: true,
        result: { state: res.state, viewer: computeViewer(res.state),
                  log: ctx.duel.log.slice(-LOG_TAIL) },
      });
    }
    if (route === 'GET /api/state') {
      if (!ctx.duel) {
        return JSON.stringify({ ok: true,
                                result: { state: null, viewer: null, log: [] } });
      }
      const viewer = computeViewer(ctx.duel.state);
      const res = (await adapter.getState({ viewer })) as GetStateResult;
      ctx.duel.state = res.state;
      return JSON.stringify({
        ok: true,
        result: { state: res.state, viewer: computeViewer(res.state),
                  log: ctx.duel.log.slice(-LOG_TAIL) },
      });
    }
    if (route === 'POST /api/respond') {
      if (!ctx.duel) {
        return apiError('NO_DUEL', '尚未开局（先 POST /api/new_duel）');
      }
      const body = await readJson(req);
      const viewer = computeViewer(ctx.duel.state);
      const res = (await adapter.respond({
        choice: body.choice as number | number[] | undefined,
        cancel: body.cancel as boolean | undefined,
        viewer,
      })) as RespondResult;
      ctx.duel.state = res.state;
      ctx.duel.log.push(...res.events);
      // respond 以应答方视角过滤；若自然视角已变化（pending 转移或终局），
      // 立即按新视角重取 state，避免对端盖卡信息残留在返回里（K3/K6）
      const newViewer = computeViewer(res.state);
      if (newViewer !== viewer) {
        const fresh = (await adapter.getState({ viewer: newViewer })) as
          GetStateResult;
        ctx.duel.state = fresh.state;
        return JSON.stringify({
          ok: true,
          result: { state: fresh.state, viewer: newViewer,
                    log: ctx.duel.log.slice(-LOG_TAIL) },
        });
      }
      return JSON.stringify({
        ok: true,
        result: { state: res.state, viewer: newViewer,
                  log: ctx.duel.log.slice(-LOG_TAIL) },
      });
    }
    return apiError('NOT_FOUND', `未知 API: ${route}`);
  }

  function serveStatic(url: URL): { status: number; body: Buffer; type: string } |
    null {
    let file: string | null = null;
    if (url.pathname === '/' || url.pathname === '/index.html') {
      file = path.join(PUBLIC_DIR, 'index.html');
    } else if (/^\/(ui\.js|ui\.css|placeholder\.svg)$/.test(url.pathname)) {
      file = path.join(PUBLIC_DIR, url.pathname.slice(1));
    } else if (/^\/art\/\d+\.jpg$/.test(url.pathname)) {
      file = path.join(DATA_DIR, 'art', url.pathname.slice('/art/'.length));
    }
    if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) return null;
    return { status: 200, body: fs.readFileSync(file),
             type: MIME[path.extname(file)] ?? 'application/octet-stream' };
  }

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://127.0.0.1');
    handle(req, res, url).catch((e: unknown) => {
      const err = e instanceof AdapterClientError
        ? e
        : new AdapterClientError('INTERNAL', String(e));
      end(res, 200, apiError(err.code, err.message));
    });
  });

  async function handle(req: http.IncomingMessage, res: http.ServerResponse,
                        url: URL): Promise<void> {
    if (url.pathname.startsWith('/api/')) {
      const body = await handleApi(req, url);
      end(res, 200, body);
      return;
    }
    const stat = serveStatic(url);
    if (stat) {
      res.writeHead(stat.status, {
        'Content-Type': stat.type,
        'Cache-Control': 'no-cache',
      });
      res.end(stat.body);
      return;
    }
    if (url.pathname.startsWith('/art/')) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('not found');   // 无图卡由前端 onerror 切占位图
      return;
    }
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('not found');
  }

  function end(res: http.ServerResponse, status: number, body: string): void {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(body);
  }

  function readJson(req: http.IncomingMessage): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = [];
      let size = 0;
      req.on('data', (c: Buffer) => {
        size += c.length;
        if (size > 1 << 20) {
          reject(new AdapterClientError('BAD_REQUEST', '请求体过大'));
          req.destroy();
          return;
        }
        chunks.push(c);
      });
      req.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8').trim();
        if (!raw) return resolve({});
        try {
          const parsed = JSON.parse(raw) as Record<string, unknown>;
          resolve(parsed);
        } catch {
          reject(new AdapterClientError('BAD_REQUEST', '请求体不是合法 JSON'));
        }
      });
      req.on('error', (e) => reject(new AdapterClientError('INTERNAL', String(e))));
    });
  }

  return new Promise((resolve, reject) => {
    server.on('error', reject);
    server.listen(opts.port ?? 8412, '127.0.0.1', () => {
      const addr = server.address();
      const port = typeof addr === 'object' && addr ? addr.port : 8412;
      resolve({
        port,
        adapter,
        cardCount: Object.keys(cards).length,
        close: async () => {
          if (ownAdapter) adapter.close();   // stdin EOF -> python 干净退出
          await new Promise<void>((res) => server.close(() => res()));
        },
      });
    });
  });
}

// 直接运行（零依赖零构建）：
//   node --experimental-strip-types src/ui/server.ts
// Ctrl+C 触发 SIGINT -> close() -> adapter stdin EOF，python 进程干净退出。
if (process.argv[1] && path.resolve(process.argv[1]) ===
    path.resolve(fileURLToPath(import.meta.url))) {
  const srv = await startServer();
  console.log(`UI: http://127.0.0.1:${srv.port}  (Ctrl+C 退出)`);
  process.on('SIGINT', async () => {
    await srv.close();
    process.exit(0);
  });
}
