/**
 * 战斗规则测试（工单 WO-001 §6 engine_battle 清单，12 例）。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDuel } from '../src/engine/index.ts';
import type { Duel } from '../src/engine/index.ts';
import { resolveAttack } from '../src/engine/battle.ts';
import type { CardDef } from '../src/core/card.ts';
import { mk, deckWith, deploy, passToMain1, attackActionsOf, assertApplyThrows } from './helpers.ts';

const ATK_HI = mk('高攻战士', 4, 1800, 1000);
const ATK_LO = mk('低攻战士', 4, 1500, 1200);
const FOE_1500 = mk('敌兵1500', 4, 1500, 999);
const FOE_1800 = mk('敌将1800', 4, 1800, 1200);
const DEF_WEAK = mk('盾兵1000', 4, 800, 1000);
const DEF_STRONG = mk('重盾兵2000', 4, 500, 2000);
const DEF_EQ = mk('均衡盾1800', 4, 600, 1800);
const DEF_FLIP = mk('暗盾2400', 4, 400, 2400);
const DIRECT = mk('直击兵1500', 4, 1500, 800);
const FILLER0 = mk('我方弹药', 4, 100, 100);
const FILLER1 = mk('敌方弹药', 4, 100, 100);

function battleDuel(myDefs: CardDef[], foeDefs: CardDef[]): Duel {
  const duel = createDuel({
    deckDefs: [deckWith([...myDefs, FILLER0], 20), deckWith([...foeDefs, FILLER1], 20)],
  });
  passToMain1(duel, 0); // 第 2 个自己的回合（先攻第一回合不能进战斗）
  return duel;
}

test('test_attack_vs_attack_higher_wins', () => {
  const duel = battleDuel([ATK_HI], [FOE_1500]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, FOE_1500.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.ok(duel.state.players[1].graveyard.some((c) => c.uid === b.uid), '低攻方被破坏送墓');
  assert.equal(duel.state.players[1].lp, 8000 - 300, '差值伤害扣给败方');
  assert.ok(duel.state.players[0].monsterZones.some((z) => z?.uid === a.uid), '攻击方存活');
});

test('test_attack_vs_attack_lower_loses', () => {
  const duel = battleDuel([ATK_LO], [FOE_1800]);
  const a = deploy(duel, 0, ATK_LO.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, FOE_1800.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.ok(duel.state.players[0].graveyard.some((c) => c.uid === a.uid), '攻击方被破坏');
  assert.equal(duel.state.players[0].lp, 8000 - 300, '反冲伤害扣攻击方');
  assert.ok(duel.state.players[1].monsterZones.some((z) => z?.uid === b.uid), '守方存活');
});

test('test_attack_vs_attack_tie_both_destroyed', () => {
  const duel = battleDuel([ATK_LO], [FOE_1500]);
  const a = deploy(duel, 0, ATK_LO.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, FOE_1500.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.ok(duel.state.players[0].graveyard.some((c) => c.uid === a.uid), '同攻同归：攻击方入墓');
  assert.ok(duel.state.players[1].graveyard.some((c) => c.uid === b.uid), '同攻同归：守方入墓');
  assert.equal(duel.state.players[0].lp, 8000, '同攻无伤害');
  assert.equal(duel.state.players[1].lp, 8000);
});

test('test_attack_vs_defense_destroy_no_damage', () => {
  const duel = battleDuel([ATK_HI], [DEF_WEAK]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, DEF_WEAK.id, 'FACE_UP_DEFENSE');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.ok(duel.state.players[1].graveyard.some((c) => c.uid === b.uid), 'ATK>DEF 守方被破坏');
  assert.equal(duel.state.players[1].lp, 8000, '无贯穿时无战斗伤害');
  assert.equal(duel.state.players[0].lp, 8000);
});

test('test_attack_vs_defense_lower_attacker_takes_damage', () => {
  const duel = battleDuel([ATK_HI], [DEF_STRONG]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, DEF_STRONG.id, 'FACE_UP_DEFENSE');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.equal(duel.state.players[0].lp, 8000 - 200, 'ATK<DEF 攻击方受差值伤害');
  assert.ok(duel.state.players[0].monsterZones.some((z) => z?.uid === a.uid), '攻击方不被破坏');
  assert.ok(duel.state.players[1].monsterZones.some((z) => z?.uid === b.uid), '守方存活');
});

test('test_attack_vs_defense_equal_nothing', () => {
  const duel = battleDuel([ATK_HI], [DEF_EQ]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, DEF_EQ.id, 'FACE_UP_DEFENSE');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.equal(duel.state.players[0].lp, 8000);
  assert.equal(duel.state.players[1].lp, 8000);
  assert.ok(duel.state.players[0].monsterZones.some((z) => z?.uid === a.uid));
  assert.ok(duel.state.players[1].monsterZones.some((z) => z?.uid === b.uid));
});

test('test_attack_face_down_flips_first', () => {
  const duel = battleDuel([ATK_HI], [DEF_FLIP]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, DEF_FLIP.id, 'FACE_DOWN_DEFENSE');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  const target = duel.state.players[1].monsterZones.find((z) => z?.uid === b.uid);
  assert.ok(target, '目标仍在场上');
  assert.equal(target?.position, 'FACE_UP_DEFENSE', '盖放怪被攻击先翻成正面防守');
  assert.equal(duel.state.players[0].lp, 8000 - 600, '按 DEF=2400 结算差值伤害');
  assert.equal(duel.state.players[1].lp, 8000);
});

test('test_direct_attack_empty_field', () => {
  const duel = battleDuel([DIRECT], []);
  const a = deploy(duel, 0, DIRECT.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: null });
  assert.equal(duel.state.players[1].lp, 8000 - 1500, '直接攻击扣全额 ATK');
});

test('test_direct_attack_blocked_with_monster', () => {
  const duel = battleDuel([DIRECT], [DEF_WEAK]);
  const a = deploy(duel, 0, DIRECT.id, 'FACE_UP_ATTACK');
  deploy(duel, 1, DEF_WEAK.id, 'FACE_DOWN_DEFENSE'); // 盖放怪也算占用（D7）
  duel.apply({ type: 'ENTER_BATTLE' });
  const attacks = attackActionsOf(duel);
  assert.ok(attacks.length > 0);
  assert.ok(attacks.every((x) => x.targetUid !== null), '对方场上有怪 → 不许直接攻击');
  assertApplyThrows(duel, { type: 'ATTACK', attackerUid: a.uid, targetUid: null }, '伪造直接攻击必须抛错');
});

test('test_monster_attacks_once_per_turn', () => {
  const duel = battleDuel([ATK_HI], [FOE_1500]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, FOE_1500.id, 'FACE_UP_ATTACK');
  duel.apply({ type: 'ENTER_BATTLE' });
  duel.apply({ type: 'ATTACK', attackerUid: a.uid, targetUid: b.uid });
  assert.equal(attackActionsOf(duel).length, 0, '攻击过后本回合不能再攻击');
  assertApplyThrows(duel, { type: 'ATTACK', attackerUid: a.uid, targetUid: null }, '重复攻击宣言必须抛错');
});

test('test_defense_position_monster_cannot_attack', () => {
  const duel = battleDuel([DEF_WEAK], []);
  const a = deploy(duel, 0, DEF_WEAK.id, 'FACE_UP_DEFENSE');
  duel.apply({ type: 'ENTER_BATTLE' });
  assert.equal(attackActionsOf(duel).length, 0, '防守表示不能攻击宣言');
  assertApplyThrows(duel, { type: 'ATTACK', attackerUid: a.uid, targetUid: null }, '防守怪攻击必须抛错');
});

test('test_pierce_option', () => {
  // 直接调 resolveAttack 传 {pierce:true}：破坏守备怪并造成超出 DEF 部分的伤害
  const duel = battleDuel([ATK_HI], [DEF_WEAK]);
  const a = deploy(duel, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b = deploy(duel, 1, DEF_WEAK.id, 'FACE_UP_DEFENSE');
  resolveAttack(duel.state, a.uid, b.uid, { pierce: true });
  assert.ok(duel.state.players[1].graveyard.some((c) => c.uid === b.uid));
  assert.equal(duel.state.players[1].lp, 8000 - 800, '贯穿伤害 = ATK - DEF');
  assert.equal(
    duel.state.players[0].monsterZones.find((z) => z?.uid === a.uid)?.attackedThisTurn,
    true,
  );

  // 对照组：默认无贯穿，破坏但无伤害
  const duel2 = battleDuel([ATK_HI], [DEF_WEAK]);
  const a2 = deploy(duel2, 0, ATK_HI.id, 'FACE_UP_ATTACK');
  const b2 = deploy(duel2, 1, DEF_WEAK.id, 'FACE_UP_DEFENSE');
  resolveAttack(duel2.state, a2.uid, b2.uid);
  assert.ok(duel2.state.players[1].graveyard.some((c) => c.uid === b2.uid));
  assert.equal(duel2.state.players[1].lp, 8000);
});
