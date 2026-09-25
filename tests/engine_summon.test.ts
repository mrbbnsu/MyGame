/**
 * 召唤规则测试（工单 WO-001 §6 engine_summon 清单，11 例）。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDuel } from '../src/engine/index.ts';
import type { GameAction } from '../src/engine/actions.ts';
import {
  mk,
  deckWith,
  deploy,
  pullToHand,
  passToMain1,
  summonActionsOf,
  assertApplyThrows,
} from './helpers.ts';

const SOLDIER = mk('士兵', 4, 1800, 1000);
const SCOUT = mk('侦察兵', 4, 1500, 1200);
const DEMON = mk('恶魔', 5, 2000, 1500);
const DRAGON = mk('巨龙', 7, 2500, 2000);
const FILLER = mk('弹药', 4, 100, 100);

const DECK0 = deckWith([SOLDIER, SCOUT, DEMON, DRAGON, FILLER], 20);
const DECK1 = deckWith([FILLER], 20);

function newDuel() {
  return createDuel({ deckDefs: [DECK0, DECK1] });
}

test('test_normal_summon_face_up_attack', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  const handBefore = duel.state.players[0].hand.length;
  const action: GameAction = { type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_UP_ATTACK', tributes: [] };
  assert.ok(duel.legalActions().some((a) => a.type === 'NORMAL_SUMMON' && a.uid === c.uid), '召唤动作应在合法列表里');
  duel.apply(action);
  const p = duel.state.players[0];
  const onField = p.monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(onField?.position, 'FACE_UP_ATTACK');
  assert.equal(p.hand.length, handBefore - 1, '手牌应减一');
  assert.equal(p.normalSummonUsed, true);
});

test('test_normal_summon_face_up_defense', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_UP_DEFENSE', tributes: [] });
  const onField = duel.state.players[0].monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(onField?.position, 'FACE_UP_DEFENSE', 'v1 特有：正面防守召唤合法');
  assert.equal(duel.state.players[0].normalSummonUsed, true);
});

test('test_set_monster_face_down_defense', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_DOWN_DEFENSE', tributes: [] });
  const onField = duel.state.players[0].monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(onField?.position, 'FACE_DOWN_DEFENSE');
  assert.equal(duel.state.players[0].normalSummonUsed, true, '盖放占用通常召唤次数');
});

test('test_one_normal_summon_per_turn', () => {
  const duel = newDuel();
  const a = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: a.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  const b = pullToHand(duel, 0, SCOUT.id); // 另一只 4 星
  assert.equal(duel.legalActions().some((x) => x.type === 'NORMAL_SUMMON'), false, '已召唤后不应再有 NORMAL_SUMMON');
  assertApplyThrows(
    duel,
    { type: 'NORMAL_SUMMON', uid: b.uid, position: 'FACE_UP_ATTACK', tributes: [] },
    '每回合只许通常召唤一次',
  );
});

test('test_tribute_summon_lv5_needs_1', () => {
  const duel = newDuel();
  const s = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: s.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  passToMain1(duel, 0); // → 自己的第 2 回合（全局第 3 回合）
  const d = pullToHand(duel, 0, DEMON.id);
  const acts = summonActionsOf(duel, d.uid);
  assert.ok(acts.length > 0, 'Lv5 应有合法召唤动作');
  assert.ok(acts.every((a) => a.tributes.length === 1), 'Lv5 恰需 1 祭品');
  assert.ok(acts.every((a) => a.tributes[0] === s.uid), '场上只有这一只怪可当祭品');
  duel.apply(acts.find((a) => a.position === 'FACE_UP_ATTACK')!);
  const p = duel.state.players[0];
  const onField = p.monsterZones.find((z) => z?.uid === d.uid);
  assert.equal(onField?.position, 'FACE_UP_ATTACK');
  assert.ok(p.monsterZones.every((z) => z === null || z.uid === d.uid), '祭品已离场');
  assert.ok(p.graveyard.some((c) => c.uid === s.uid), '祭品入墓');
});

test('test_tribute_summon_lv7_needs_2', () => {
  // 场上 2 怪：Lv7 可召，祭品恰为两只
  const duel = newDuel();
  const s1 = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: s1.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  passToMain1(duel, 0);
  const s2 = pullToHand(duel, 0, SCOUT.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: s2.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  passToMain1(duel, 0);
  const d = pullToHand(duel, 0, DRAGON.id);
  const acts = summonActionsOf(duel, d.uid);
  assert.ok(acts.length > 0, '场上 2 怪时 Lv7 可召');
  assert.ok(acts.every((a) => a.tributes.length === 2), 'Lv7 恰需 2 祭品');
  const tributes = acts[0]!.tributes;
  assert.deepEqual(
    [...tributes].sort((x, y) => x - y),
    [s1.uid, s2.uid].sort((x, y) => x - y),
  );
  duel.apply({ type: 'NORMAL_SUMMON', uid: d.uid, position: 'FACE_UP_ATTACK', tributes });
  const p = duel.state.players[0];
  assert.ok(p.monsterZones.every((z) => z === null || z.uid === d.uid), '两只祭品都已离场');
  assert.ok(p.graveyard.some((c) => c.uid === s1.uid) && p.graveyard.some((c) => c.uid === s2.uid));

  // 场上仅 1 怪：Lv7 无合法召唤动作
  const duel2 = newDuel();
  const s = pullToHand(duel2, 0, SOLDIER.id);
  duel2.apply({ type: 'NORMAL_SUMMON', uid: s.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  passToMain1(duel2, 0);
  const d2 = pullToHand(duel2, 0, DRAGON.id);
  assert.equal(summonActionsOf(duel2, d2.uid).length, 0, '祭品不足时不应生成召唤动作');
});

test('test_tribute_insufficient_illegal', () => {
  const duel = newDuel();
  const s = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: s.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  passToMain1(duel, 0);
  const d = pullToHand(duel, 0, DRAGON.id);
  assert.equal(summonActionsOf(duel, d.uid).length, 0);
  const forged: GameAction = { type: 'NORMAL_SUMMON', uid: d.uid, position: 'FACE_UP_ATTACK', tributes: [s.uid] };
  assertApplyThrows(duel, forged, '伪造祭品数不符的动作必须抛错');
});

test('test_monster_zone_full_blocks_summon', () => {
  const duel = newDuel();
  for (const d of [SOLDIER, SCOUT, DEMON, DRAGON, FILLER]) {
    deploy(duel, 0, d.id, 'FACE_UP_ATTACK');
  }
  const c = pullToHand(duel, 0, FILLER.id); // 5 怪占满后手上仍有 4 星
  assert.equal(duel.legalActions().some((a) => a.type === 'NORMAL_SUMMON'), false);
  assertApplyThrows(
    duel,
    { type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_UP_ATTACK', tributes: [] },
    '怪兽区满时召唤必须抛错',
  );
});

test('test_flip_summon_not_same_turn_as_set', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_DOWN_DEFENSE', tributes: [] });
  assert.equal(duel.legalActions().some((a) => a.type === 'FLIP_SUMMON' && a.uid === c.uid), false);
  assertApplyThrows(duel, { type: 'FLIP_SUMMON', uid: c.uid }, '盖放当回合不许反转召唤');
});

test('test_flip_summon_next_turn_ok', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_DOWN_DEFENSE', tributes: [] });
  passToMain1(duel, 0); // 下一个自己的回合
  assert.ok(duel.legalActions().some((a) => a.type === 'FLIP_SUMMON' && a.uid === c.uid));
  duel.apply({ type: 'FLIP_SUMMON', uid: c.uid });
  const m = duel.state.players[0].monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(m?.position, 'FACE_UP_ATTACK', '反转召唤翻成正面攻击表示');
});

test('test_change_position_rules', () => {
  const duel = newDuel();
  const c = pullToHand(duel, 0, SOLDIER.id);
  duel.apply({ type: 'NORMAL_SUMMON', uid: c.uid, position: 'FACE_UP_ATTACK', tributes: [] });
  // 召唤回合不可变更
  assert.equal(duel.legalActions().some((a) => a.type === 'CHANGE_POSITION' && a.uid === c.uid), false);
  assertApplyThrows(duel, { type: 'CHANGE_POSITION', uid: c.uid }, '召唤回合不可变更表示');

  duel.apply({ type: 'ADVANCE_PHASE' }); // 先走出本回合 MAIN1
  passToMain1(duel, 0); // 自己的第 2 回合
  duel.apply({ type: 'CHANGE_POSITION', uid: c.uid });
  let m = duel.state.players[0].monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(m?.position, 'FACE_UP_DEFENSE');
  assert.equal(
    duel.legalActions().some((a) => a.type === 'CHANGE_POSITION' && a.uid === c.uid),
    false,
    '变更后当回合不可再变',
  );

  duel.apply({ type: 'ADVANCE_PHASE' });
  passToMain1(duel, 0); // 第 3 回合：转回攻击并攻击
  duel.apply({ type: 'CHANGE_POSITION', uid: c.uid });
  m = duel.state.players[0].monsterZones.find((z) => z?.uid === c.uid);
  assert.equal(m?.position, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  const attacks = duel.legalActions().filter((a) => a.type === 'ATTACK');
  assert.ok(attacks.length > 0, '对方场上无怪 → 可直接攻击');
  duel.apply({ type: 'ATTACK', attackerUid: c.uid, targetUid: null });
  assert.equal(
    duel.legalActions().some((a) => a.type === 'CHANGE_POSITION' && a.uid === c.uid),
    false,
    '攻击过的怪兽当回合不可变更表示',
  );
  assertApplyThrows(duel, { type: 'CHANGE_POSITION', uid: c.uid }, '攻击后变更表示必须抛错');
});
