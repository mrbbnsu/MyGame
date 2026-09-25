/**
 * E1/WO-007：Classic Duel Adapter 的 TS 客户端。
 *
 * 职责：spawn Python 服务进程 + JSON Lines 读写 + 请求 id 关联 + 类型化结果。
 * 红线（K4）：只说 JSON；任何字节级解析都不允许出现在 TS 侧。
 */
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { createInterface } from 'node:readline';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
  AdapterResponse,
  GetStateRequest,
  GetStateResult,
  NewDuelRequest,
  NewDuelResult,
  ReadyLine,
  RespondRequest,
  RespondResult,
} from './types.ts';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)),
                               '..', '..');
const SERVICE_SCRIPT = path.join(REPO_ROOT, 'adapter', 'service.py');

export class AdapterClientError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(`[${code}] ${message}`);
    this.code = code;
  }
}

export interface AdapterClientOptions {
  /** python 可执行文件（默认 python，需支持 -X utf8，即 3.7+） */
  python?: string;
  /** service.py 路径（默认仓库内） */
  serviceScript?: string;
  /** DLL/cdb/脚本根路径（透传 --dll/--cdb/--scripts） */
  dll?: string;
  cdb?: string;
  scripts?: string;
}

export class AdapterClient {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private nextId = 1;
  private pending = new Map<
    number | string,
    { resolve: (r: AdapterResponse) => void; reject: (e: Error) => void }
  >();
  private ready: Promise<ReadyLine['result']>;
  private closed = false;
  private opts: AdapterClientOptions;

  constructor(opts: AdapterClientOptions = {}) {
    this.opts = opts;
    this.ready = this.spawn();
  }

  /** 等服务就绪（可 await 以获取版本信息）；失败时抛结构化错误 */
  ensureReady(): Promise<ReadyLine['result']> {
    return this.ready;
  }

  private async spawn(): Promise<ReadyLine['result']> {
    const python = this.opts.python ?? process.env.CLASSIC_DUEL_PYTHON ?? 'python';
    const args = ['-X', 'utf8', this.opts.serviceScript ?? SERVICE_SCRIPT];
    if (this.opts.dll) args.push('--dll', this.opts.dll);
    if (this.opts.cdb) args.push('--cdb', this.opts.cdb);
    if (this.opts.scripts) args.push('--scripts', this.opts.scripts);
    const proc = spawn(python, args, { cwd: REPO_ROOT, windowsHide: true });
    this.proc = proc;

    const fail = (err: Error): void => {
      for (const p of this.pending.values()) p.reject(err);
      this.pending.clear();
    };
    proc.on('error', (err) => {
      fail(new AdapterClientError(
        'SPAWN_FAILED',
        `无法启动服务 (${python}): ${err.message}`));
    });

    // JSON Lines：一行一个 JSON（服务 stdout 只承载协议行，诊断走 stderr）
    const rl = createInterface({ input: proc.stdout });
    let readyResolve!: (r: ReadyLine['result']) => void;
    let readyReject!: (e: Error) => void;
    const readyPromise = new Promise<ReadyLine['result']>((res, rej) => {
      readyResolve = res;
      readyReject = rej;
    });
    this.ready = readyPromise;
    let first = true;
    let stderrBuf = '';
    proc.stderr.on('data', (d: Buffer) => {
      stderrBuf = (stderrBuf + d.toString('utf8')).slice(-4000);
    });
    rl.on('line', (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let msg: AdapterResponse;
      try {
        msg = JSON.parse(trimmed) as AdapterResponse;
      } catch (e) {
        fail(new AdapterClientError('PROTOCOL_VIOLATION',
                                    `非 JSON 行: ${trimmed.slice(0, 120)}`));
        return;
      }
      if (first) {
        first = false;
        if (msg.ok && msg.result && (msg.result as ReadyLine['result']).ready) {
          readyResolve(msg.result as ReadyLine['result']);
        } else {
          readyReject(new AdapterClientError(
            msg.error?.code ?? 'SERVICE_FATAL',
            msg.error?.message ?? '服务启动失败'));
        }
        return;
      }
      const p = this.pending.get(msg.id);
      if (!p) return; // 未知 id（不应发生；忽略保持健壮）
      this.pending.delete(msg.id);
      p.resolve(msg);
    });
    proc.on('exit', (code) => {
      fail(new AdapterClientError(
        'SERVICE_EXITED',
        `服务进程退出 code=${code}${stderrBuf ? ` stderr: ${stderrBuf.trim()}` : ''}`));
    });
    return readyPromise;
  }

  private async request<T>(req: { cmd: string } & Record<string, unknown>): Promise<T> {
    if (this.closed) {
      throw new AdapterClientError('CLIENT_CLOSED', '客户端已关闭');
    }
    await this.ready;
    const id = this.nextId++;
    const body = JSON.stringify({ ...req, id }) + '\n';
    const res = await new Promise<AdapterResponse>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      try {
        this.proc!.stdin.write(body);
      } catch (e) {
        this.pending.delete(id);
        reject(new AdapterClientError('PIPE_BROKEN', `写入失败: ${String(e)}`));
      }
    });
    if (!res.ok || res.result === undefined) {
      throw new AdapterClientError(res.error?.code ?? 'UNKNOWN_ERROR',
                                   res.error?.message ?? '无 result');
    }
    return res.result as T;
  }

  newDuel(req: Omit<NewDuelRequest, 'id' | 'cmd'>): Promise<NewDuelResult> {
    return this.request<NewDuelResult>({ cmd: 'new_duel', ...req });
  }

  getState(req: Omit<GetStateRequest, 'id' | 'cmd'>): Promise<GetStateResult> {
    return this.request<GetStateResult>({ cmd: 'get_state', ...req });
  }

  respond(req: Omit<RespondRequest, 'id' | 'cmd'>): Promise<RespondResult> {
    return this.request<RespondResult>({ cmd: 'respond', ...req });
  }

  /** 终止服务（stdin EOF -> 服务干净退出） */
  close(): void {
    this.closed = true;
    this.proc?.stdin.end();
  }

  /** 强杀（测试兜底；正常路径用 close） */
  kill(): void {
    this.closed = true;
    this.proc?.kill();
  }
}
