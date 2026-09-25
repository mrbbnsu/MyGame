import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CLASSIC_RULES } from '../src/core/config.ts';
import { makeRng } from '../src/core/rng.ts';
import { createGameState, opponentOf } from '../src/core/state.ts';
import { makeInstance, tributeCount } from '../src/core/card.ts';

test('phase0: 经典规则默认值', () => {
  assert.equal(CLASSIC_RULES.lp, 8000);
  assert.equal(CLASSIC_RULES.firstTurnDraw, false);
  assert.equal(CLASSIC_RULES.specialSummonLimit, 3);
  assert.equal(CLASSIC_RULES.handLimit, 6);
});

test('phase0: 种子化 RNG 可复现', () => {
  const a = makeRng(42);
  const b = makeRng(42);
  const seqA = Array.from({ length: 10 }, () => a.next());
  const seqB = Array.from({ length: 10 }, () => b.next());
  assert.deepEqual(seqA, seqB);
  const arr1 = a.shuffle([1, 2, 3, 4, 5, 6, 7, 8]);
  const arr2 = b.shuffle([1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(arr1, arr2);
});

test('phase0: 状态模型可结构化克隆（AI 搜索前提）', () => {
  const st = createGameState([[{ id: 1, name: 'A', cardType: 'MONSTER', level: 4, atk: 100, def: 100 }], []], CLASSIC_RULES);
  const clone = structuredClone(st);
  assert.deepEqual(clone, st);
  assert.equal(opponentOf(0), 1);
  assert.equal(tributeCount(4), 0);
  assert.equal(tributeCount(5), 1);
  assert.equal(tributeCount(7), 2);
  assert.equal(makeInstance({ id: 2, name: 'B', cardType: 'MONSTER' }, 9).uid, 9);
});
