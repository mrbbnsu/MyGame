/**
 * 回合/阶段/胜负测试（工单 WO-001 §6 engine_turn 清单，6 例）。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CLASSIC_RULES } from '../src/core/config.ts';
import { createDuel } from '../src/engine/index.ts';
import type { GameAction } from '../src/engine/actions.ts';
import { mk, deckWith, deploy, pullExtraToHand, passToMain1, assertApplyThrows } from './helpers.ts';

const F0 = mk('我方怪', 4, 1000, 800);
const F1 = mk('敌方怪', 4, 900, 900);
const BIG = mk('重击兵1500', 4, 1500, 500);
const ADVANCE: GameAction = { type: 'ADVANCE_PHASE' };

test('test_first_turn_no_draw_no_battle', () => {
  const duel = createDuel({ deckDefs: [deckWith([F0], 20), deckWith([F1], 20)] });
  assert.equal(duel.state.turnCount, 1);
  assert.equal(duel.state.phase, 'MAIN1');
  assert.equal(duel.state.players[0].hand.length, 5, '起手 5 张');
  assert.equal(duel.state.players[1].hand.length, 5, '起手 5 张');
  assert.equal(duel.legalActions().some((a) => a.type === 'ENTER_BATTLE'), false, '先攻第一回合无 ENTER_BATTLE');
  assertApplyThrows(duel, { type: 'ENTER_BATTLE' }, '先攻第一回合不能进战斗阶段');
});

test('test_second_player_draws', () => {
  const duel = createDuel({ deckDefs: [deckWith([F0], 20), deckWith([F1], 20)] });
  passToMain1(duel, 1);
  assert.equal(duel.state.turnCount, 2);
  assert.equal(duel.state.turnPlayer, 1);
  assert.equal(duel.state.players[1].hand.length, 6, '后手第一回合抽 1 → 手牌 6');
});

test('test_hand_limit_discard_at_end', () => {
  const rules = { ...CLASSIC_RULES, handLimit: 5 };
  const duel = createDuel({ deckDefs: [deckWith([F0], 20), deckWith([F1], 20)], rules });
  pullExtraToHand(duel, 0, F0.id); // 手牌 5 → 6 > 上限 5
  duel.apply(ADVANCE); // MAIN1→MAIN2
  duel.apply(ADVANCE); // MAIN2→END
  assert.equal(duel.state.phase, 'END');
  assert.equal(duel.state.pendingHandLimit, true, '超限置 pendingHandLimit');
  const acts = duel.legalActions();
  assert.ok(acts.length > 0);
  assert.ok(acts.every((a) => a.type === 'DISCARD'), '此状态下只准 DISCARD');
  duel.apply(acts[0]!);
  assert.equal(duel.state.pendingHandLimit, false, '弃到 ≤ 上限自动进入下一回合');
  assert.equal(duel.state.turnCount, 2);
  assert.equal(duel.state.turnPlayer, 1);
  assert.equal(duel.state.phase, 'MAIN1');
  assert.equal(duel.state.players[0].hand.length, 5);
});

test('test_deck_out_loses', () => {
  // 6 张卡组（5 起手 + 1）：自己第 2 回合抽空卡组，第 3 回合抽牌时卡组为空 → 对方胜
  const duel = createDuel({ deckDefs: [deckWith([F0], 6), deckWith([F1], 20)] });
  duel.apply(ADVANCE);
  duel.apply(ADVANCE);
  duel.apply(ADVANCE); // → 对方第 2 回合
  passToMain1(duel, 0); // → 自己第 2 回合，抽走最后 1 张
  assert.equal(duel.state.players[0].deck.length, 0, '卡组抽空');
  assert.equal(duel.state.winner, null, '抽走最后一张不判负');

  duel.apply(ADVANCE); // MAIN1→MAIN2
  duel.apply(ADVANCE); // MAIN2→END（对方下回合手牌将超限，此处自己 6 张未超）
  duel.apply(ADVANCE); // → 对方第 4 回合 MAIN1
  duel.apply(ADVANCE); // MAIN1→MAIN2
  duel.apply(ADVANCE); // MAIN2→END：对方手牌 7 > 6
  assert.equal(duel.state.pendingHandLimit, true);
  const discards = duel.legalActions();
  assert.ok(discards.length > 0 && discards.every((a) => a.type === 'DISCARD'));
  duel.apply(discards[0]!); // 弃到 6 → 自动进入自己第 3 回合 → 抽牌时卡组为空
  assert.equal(duel.state.winner, 1, '卡组抽空判负');
  assert.equal(duel.state.endReason, 'DECK_OUT');
  assert.ok(duel.over);
  assert.deepEqual(duel.legalActions(), [], '结束后 legalActions 必须为空');
  assertApplyThrows(duel, ADVANCE, '结束后再 apply 必须抛错');
});

test('test_lp_zero_loses_and_no_actions_after', () => {
  const rules = { ...CLASSIC_RULES, lp: 1000 };
  const duel = createDuel({ deckDefs: [deckWith([BIG, F0], 20), deckWith([F1], 20)], rules });
  passToMain1(duel, 0);
  const a = deploy(duel, 0, BIG.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: null }); // 1500 直击 > 1000 LP
  assert.equal(duel.state.winner, 0);
  assert.equal(duel.state.endReason, 'LP_ZERO');
  assert.ok(duel.over);
  assert.deepEqual(duel.legalActions(), [], '结束后 legalActions 必须为空');
  assertApplyThrows(duel, ADVANCE, '结束后再 apply 必须抛错');
});

test('test_deterministic_same_seed', () => {
  const deck0 = deckWith([F0, mk('甲', 4, 1200, 900), mk('乙', 4, 1100, 1000)], 20);
  const deck1 = deckWith([F1, mk('丙', 4, 1300, 700)], 20);
  const d1 = createDuel({ deckDefs: [deck0, deck1], seed: 4242 });
  const d2 = createDuel({ deckDefs: [deck0, deck1], seed: 4242 });
  let steps = 0;
  while (!d1.over && steps < 200) {
    const pick = d1.legalActions()[0]!;
    d1.apply(pick);
    d2.apply(pick);
    steps++;
    assert.equal(
      JSON.stringify(d1.state),
      JSON.stringify(d2.state),
      `同 seed 第 ${steps} 步后状态必须一致`,
    );
  }
  assert.ok(steps > 0);
  assert.equal(d1.over, d2.over);
});
