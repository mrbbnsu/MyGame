/**
 * 统一区域移动 API —— 一切卡牌移动的唯一入口（任务书 §14/§20/§21 红线）。
 * 抽牌、召唤、祭品、破坏、弃牌……全部只经 moveCard；
 * 引擎其余文件不得直接增删任何区域数组或写怪兽/魔陷槽位。
 */
import type { CardInstance } from '../core/card.ts';
import type { GameState, PlayerState } from '../core/state.ts';
import type { ZoneKind, ZoneRef } from '../core/zones.ts';
import { zoneName } from '../core/zones.ts';

/** 从来源区取出指定卡（存在性校验，取不到即 throw）。 */
function takeFrom(state: GameState, uid: number, from: ZoneRef): CardInstance {
  const p = state.players[from.player];
  let card: CardInstance;
  switch (from.kind) {
    case 'MONSTER': {
      const idx = from.index ?? p.monsterZones.findIndex((z) => z?.uid === uid);
      if (idx < 0 || idx >= p.monsterZones.length || p.monsterZones[idx]?.uid !== uid) {
        throw new Error(`moveCard: 怪兽 uid=${uid} 不在 ${zoneName(from)}`);
      }
      card = p.monsterZones[idx]!;
      p.monsterZones[idx] = null;
      break;
    }
    case 'SPELL_TRAP': {
      const idx = from.index ?? p.spellTrapZones.findIndex((z) => z?.uid === uid);
      if (idx < 0 || idx >= p.spellTrapZones.length || p.spellTrapZones[idx]?.uid !== uid) {
        throw new Error(`moveCard: 卡 uid=${uid} 不在 ${zoneName(from)}`);
      }
      card = p.spellTrapZones[idx]!;
      p.spellTrapZones[idx] = null;
      break;
    }
    case 'FIELD': {
      if (p.fieldZone?.uid !== uid) {
        throw new Error(`moveCard: 卡 uid=${uid} 不在 ${zoneName(from)}`);
      }
      card = p.fieldZone;
      p.fieldZone = null;
      break;
    }
    default: {
      const list = listZone(p, from.kind);
      const i = list.findIndex((c) => c.uid === uid);
      if (i < 0) {
        throw new Error(`moveCard: 卡 uid=${uid} 不在 ${zoneName(from)}`);
      }
      card = list[i]!;
      list.splice(i, 1);
    }
  }
  if (from.kind === 'MONSTER') {
    // D16：怪兽离场清空战斗期字段，保证未来复活语义干净
    delete card.position;
    delete card.summonedTurn;
    delete card.attackedThisTurn;
    delete card.positionChangedThisTurn;
  }
  return card;
}

function listZone(p: PlayerState, kind: ZoneKind): CardInstance[] {
  switch (kind) {
    case 'DECK': return p.deck;
    case 'HAND': return p.hand;
    case 'GRAVEYARD': return p.graveyard;
    case 'BANISHED': return p.banished;
    case 'EXTRA': return p.extraDeck;
    default: throw new Error(`moveCard: ${kind} 不是列表区`);
  }
}

/**
 * 把 uid 指定的卡从 from 移到 to，返回该卡实例。
 * to 为槽位区（MONSTER/SPELL_TRAP）且未给 index 时放入第一个空位；放入被占槽位即 throw。
 */
export function moveCard(state: GameState, uid: number, from: ZoneRef, to: ZoneRef): CardInstance {
  const card = takeFrom(state, uid, from);
  const dst = state.players[to.player];
  switch (to.kind) {
    case 'MONSTER': {
      const idx = to.index ?? dst.monsterZones.findIndex((z) => z === null);
      if (idx < 0 || idx >= dst.monsterZones.length) {
        throw new Error(`moveCard: ${zoneName(to)} 无空位`);
      }
      if (dst.monsterZones[idx] !== null) {
        throw new Error(`moveCard: ${zoneName(to)} 已被占用`);
      }
      dst.monsterZones[idx] = card;
      break;
    }
    case 'SPELL_TRAP': {
      const idx = to.index ?? dst.spellTrapZones.findIndex((z) => z === null);
      if (idx < 0 || idx >= dst.spellTrapZones.length) {
        throw new Error(`moveCard: ${zoneName(to)} 无空位`);
      }
      if (dst.spellTrapZones[idx] !== null) {
        throw new Error(`moveCard: ${zoneName(to)} 已被占用`);
      }
      dst.spellTrapZones[idx] = card;
      break;
    }
    case 'FIELD': {
      if (dst.fieldZone !== null) {
        throw new Error(`moveCard: ${zoneName(to)} 已被占用`);
      }
      dst.fieldZone = card;
      break;
    }
    case 'DECK': dst.deck.push(card); break;
    case 'HAND': dst.hand.push(card); break;
    case 'GRAVEYARD': dst.graveyard.push(card); break;
    case 'BANISHED': dst.banished.push(card); break;
    case 'EXTRA': dst.extraDeck.push(card); break;
  }
  return card;
}
