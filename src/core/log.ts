/**
 * 基础日志系统：分级输出到 stderr，默认静默（测试/生产不打扰）。
 * 用法：LOG.enabled = true; LOG.info('engine', '...')。
 */
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_ORDER: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 };

export interface Logger {
  enabled: boolean;
  minLevel: LogLevel;
  debug(tag: string, msg: string): void;
  info(tag: string, msg: string): void;
  warn(tag: string, msg: string): void;
  error(tag: string, msg: string): void;
}

export const LOG: Logger = {
  enabled: false,
  minLevel: 'info',
  debug(tag, msg) { write('debug', this, tag, msg); },
  info(tag, msg) { write('info', this, tag, msg); },
  warn(tag, msg) { write('warn', this, tag, msg); },
  error(tag, msg) { write('error', this, tag, msg); },
};

function write(level: LogLevel, logger: Logger, tag: string, msg: string): void {
  if (!logger.enabled) return;
  if (LEVEL_ORDER[level] < LEVEL_ORDER[logger.minLevel]) return;
  console.error(`[${new Date().toISOString()}][${level.toUpperCase()}][${tag}] ${msg}`);
}
