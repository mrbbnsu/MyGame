/**
 * 可注入的确定性随机源。引擎/测试都需要可复现的对局。
 */
export interface Rng {
  /** [0, 1) */
  next(): number;
  /** 原地 Fisher-Yates 洗牌 */
  shuffle<T>(arr: T[]): T[];
}

/** mulberry32：小而稳的种子化 PRNG */
export function makeRng(seed: number): Rng {
  let a = seed >>> 0;
  const next = (): number => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    shuffle<T>(arr: T[]): T[] {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
      return arr;
    },
  };
}
