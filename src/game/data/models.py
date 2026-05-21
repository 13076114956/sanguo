from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .base import BaseData


class Camp(str, Enum):
    WEI = "魏"
    SHU = "蜀"
    WU = "吴"
    QUN = "群"
    GOD = "神"
    DEMON = "魔"


class Profession(str, Enum):
    TANK = "坦克"
    PHYSICAL = "物理输出"
    MAGICAL = "法术输出"
    HEALER = "治疗"
    CONTROL = "控制"


class HeroRole(str, Enum):
    VANGUARD = "先锋"
    ASSASSIN = "奇袭"
    MAGE = "法师"
    SUPPORT = "辅助"


class HeroQuality(str, Enum):
    B = "B"
    A = "A"
    S = "S"
    S_PLUS = "S+"

    @property
    def level_cap(self) -> int:
        return {
            HeroQuality.B: 180,
            HeroQuality.A: 240,
            HeroQuality.S: 340,
            HeroQuality.S_PLUS: 340,
        }[self]

    @property
    def default_awakening(self) -> "AwakeningLevel":
        return {
            HeroQuality.B: AwakeningLevel.RARE,
            HeroQuality.A: AwakeningLevel.RARE,
            HeroQuality.S: AwakeningLevel.EXCELLENT,
            HeroQuality.S_PLUS: AwakeningLevel.EXCELLENT,
        }[self]

    @property
    def max_awakening(self) -> "AwakeningLevel":
        return {
            HeroQuality.B: AwakeningLevel.LEGEND,
            HeroQuality.A: AwakeningLevel.LEGEND,
            HeroQuality.S: AwakeningLevel.ETERNAL,
            HeroQuality.S_PLUS: AwakeningLevel.ETERNAL,
        }[self]

    @property
    def quality_factor(self) -> float:
        return {
            HeroQuality.B: 0.00,
            HeroQuality.A: 0.08,
            HeroQuality.S: 0.18,
            HeroQuality.S_PLUS: 0.28,
        }[self]


class AwakeningLevel(str, Enum):
    RARE = "稀有"
    RARE_PLUS = "稀有+"
    EXCELLENT = "卓越"
    EXCELLENT_PLUS = "卓越+"
    EPIC = "史诗"
    LEGEND = "传说"
    LEGEND_PLUS = "传说+"
    MYTH = "神话"
    MYTH_PLUS = "神话+"
    TRANSCENDENT = "超越"
    TRANSCENDENT_PLUS = "超越+"
    ETERNAL = "永恒"

    @property
    def order(self) -> int:
        return list(AwakeningLevel).index(self)

    @property
    def color(self) -> str:
        return {
            AwakeningLevel.RARE: "蓝色",
            AwakeningLevel.RARE_PLUS: "蓝色",
            AwakeningLevel.EXCELLENT: "紫色",
            AwakeningLevel.EXCELLENT_PLUS: "紫色",
            AwakeningLevel.EPIC: "金色",
            AwakeningLevel.LEGEND: "橙色",
            AwakeningLevel.LEGEND_PLUS: "橙色",
            AwakeningLevel.MYTH: "天蓝色",
            AwakeningLevel.MYTH_PLUS: "天蓝色",
            AwakeningLevel.TRANSCENDENT: "粉色",
            AwakeningLevel.TRANSCENDENT_PLUS: "粉色",
            AwakeningLevel.ETERNAL: "金色",
        }[self]

    @property
    def awakening_factor(self) -> float:
        return {
            AwakeningLevel.RARE: 0.00,
            AwakeningLevel.RARE_PLUS: 0.05,
            AwakeningLevel.EXCELLENT: 0.12,
            AwakeningLevel.EXCELLENT_PLUS: 0.18,
            AwakeningLevel.EPIC: 0.26,
            AwakeningLevel.LEGEND: 0.36,
            AwakeningLevel.LEGEND_PLUS: 0.48,
            AwakeningLevel.MYTH: 0.62,
            AwakeningLevel.MYTH_PLUS: 0.78,
            AwakeningLevel.TRANSCENDENT: 0.96,
            AwakeningLevel.TRANSCENDENT_PLUS: 1.16,
            AwakeningLevel.ETERNAL: 1.38,
        }[self]


LegacyAwakeningQuality = AwakeningLevel


def legacy_quality_to_hero_quality(name: str) -> HeroQuality:
    if name in {HeroQuality.B.value, HeroQuality.A.value, HeroQuality.S.value, HeroQuality.S_PLUS.value}:
        return HeroQuality(name)
    if name in {AwakeningLevel.LEGEND.value, AwakeningLevel.LEGEND_PLUS.value, AwakeningLevel.MYTH.value, AwakeningLevel.MYTH_PLUS.value, AwakeningLevel.TRANSCENDENT.value, AwakeningLevel.TRANSCENDENT_PLUS.value, AwakeningLevel.ETERNAL.value}:
        return HeroQuality.S_PLUS
    if name in {AwakeningLevel.EXCELLENT.value, AwakeningLevel.EXCELLENT_PLUS.value, AwakeningLevel.EPIC.value}:
        return HeroQuality.S
    if name in {AwakeningLevel.RARE.value, AwakeningLevel.RARE_PLUS.value}:
        return HeroQuality.A
    return HeroQuality.S


def clamp_awakening_for_quality(hero_quality: HeroQuality, awakening_level: AwakeningLevel) -> AwakeningLevel:
    if awakening_level.order < hero_quality.default_awakening.order:
        return hero_quality.default_awakening
    if awakening_level.order > hero_quality.max_awakening.order:
        return hero_quality.max_awakening
    return awakening_level


class StatusCategory(str, Enum):
    BUFF = "buff"
    DEBUFF = "debuff"
    NEUTRAL = "neutral"


class StatusTag(str, Enum):
    CONTROL = "control"
    DAMAGE_OVER_TIME = "damage_over_time"
    ATTRIBUTE = "attribute"
    PROTECT = "protect"
    SPECIAL = "special"


DOT_EFFECT_TYPES = {"burn", "poison", "bleed"}
CONTROL_EFFECT_TYPES = {"stun", "silence", "freeze", "taunt"}
PROTECT_EFFECT_TYPES = {"shield", "invincible", "untargetable", "damage_share", "shield_regen", "cao_cao_alliance"}
MARK_EFFECT_TYPES = {"lightning_mark", "incoming_damage_bonus", "guan_yu_wu_sheng_mark"}
ATTRIBUTE_EFFECT_TYPES = {"attack_bonus", "defense_bonus", "speed_bonus", "damage_reduction", "crit_rate_bonus", "crit_damage_bonus"}
BUFF_EFFECT_TYPES = {"shield", "invincible", "untargetable", "damage_share", "shield_regen", "conditional_damage_reduction", "frontline_damage_bonus", "gain_stack_when_column_front_enemy_damaged", "guan_yu_wuhun_guard", "guan_yu_divine_form", "guan_yu_war_intent", "guo_jia_chess_shadow", "guo_jia_shadow_crit_bonus", "guo_jia_shadow_focus", "guo_jia_survive_once_used", "cao_cao_alliance", "cao_cao_guard_mode", "cao_cao_fatal_immunity_cooldown"}
DEBUFF_EFFECT_TYPES = DOT_EFFECT_TYPES | CONTROL_EFFECT_TYPES | MARK_EFFECT_TYPES


def get_status_category(effect_type: str, value: float = 0.0) -> StatusCategory:
    if effect_type in BUFF_EFFECT_TYPES:
        return StatusCategory.BUFF
    if effect_type in DEBUFF_EFFECT_TYPES:
        return StatusCategory.DEBUFF
    if effect_type in ATTRIBUTE_EFFECT_TYPES:
        return StatusCategory.DEBUFF if value < 0 else StatusCategory.BUFF
    return StatusCategory.NEUTRAL


def get_status_tags(effect_type: str) -> tuple[StatusTag, ...]:
    tags: list[StatusTag] = []
    if effect_type in DOT_EFFECT_TYPES:
        tags.append(StatusTag.DAMAGE_OVER_TIME)
    if effect_type in CONTROL_EFFECT_TYPES:
        tags.append(StatusTag.CONTROL)
    if effect_type in PROTECT_EFFECT_TYPES:
        tags.append(StatusTag.PROTECT)
    if effect_type in ATTRIBUTE_EFFECT_TYPES:
        tags.append(StatusTag.ATTRIBUTE)
    if effect_type in {"taunt", "invincible", "untargetable", "wind_spirit", "survive_once", "lightning_mark", "incoming_damage_bonus", "damage_share", "shield_regen", "conditional_damage_reduction", "frontline_damage_bonus", "gain_stack_when_column_front_enemy_damaged", "guan_yu_wuhun_guard", "guan_yu_divine_form", "guan_yu_war_intent", "guan_yu_wu_sheng_mark", "guo_jia_chess_shadow", "guo_jia_shadow_crit_bonus", "guo_jia_shadow_focus", "guo_jia_survive_once_used", "cao_cao_alliance", "cao_cao_guard_mode", "cao_cao_fatal_immunity_cooldown"}:
        tags.append(StatusTag.SPECIAL)
    return tuple(tags)


@dataclass(slots=True)
class HeroStats:
    hp: float
    attack: float
    defense: float
    speed: float
    crit_rate: float
    crit_damage: float
    armor_break: float
    effect_hit: float
    effect_resist: float

    def copy(self) -> "HeroStats":
        return HeroStats(**self.to_dict())

    def to_dict(self) -> dict[str, float]:
        return {
            "hp": self.hp,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "crit_rate": self.crit_rate,
            "crit_damage": self.crit_damage,
            "armor_break": self.armor_break,
            "effect_hit": self.effect_hit,
            "effect_resist": self.effect_resist,
        }


EQUIPMENT_SLOT_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("weapon", "武器"),
    ("helmet", "头盔"),
    ("armor", "铠甲"),
    ("boots", "战靴"),
)
SKILL_SLOT_KEYS = ("passive_1", "passive_2", "passive_3", "ultimate")
# 仅用于兼容旧配置/旧存档读取；新数据统一写为 passive_3。
LEGACY_SKILL_SLOT_KEY_ALIASES: dict[str, str] = {"normal_attack": "passive_3"}
SKILL_SLOT_HASH_KEYS: dict[str, str] = {
    "passive_1": "passive_1",
    "passive_2": "passive_2",
    # 保留旧 normal_attack 哈希输入，避免已有奇珍锁位结果在迁移后重排。
    "passive_3": "normal_attack",
    "ultimate": "ultimate",
}
SKILL_SLOT_DISPLAY_NAMES: dict[str, str] = {
    # 仅用于兼容旧日志/旧槽位展示，不作为新的写出键名。
    "normal_attack": "被动三",
    "passive_1": "被动一",
    "passive_2": "被动二",
    "passive_3": "被动三",
    "ultimate": "必杀",
}
RARE_TREASURE_LINKED_NODE_INDEXES: tuple[int, int] = (3, 9)


def normalize_skill_slot_key(slot_key: str | None) -> str | None:
    if slot_key is None:
        return None
    # 旧 normal_attack 槽位在读取时归一到 passive_3；内部只使用新键名。
    normalized = LEGACY_SKILL_SLOT_KEY_ALIASES.get(slot_key, slot_key)
    return normalized if normalized in SKILL_SLOT_KEYS else None


@dataclass(slots=True)
class EquipmentSlotData:
    slot_key: str
    slot_name: str
    item_id: str = ""
    item_name: str = ""
    quality: str = ""
    level: int = 0
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def copy(self) -> "EquipmentSlotData":
        return EquipmentSlotData(
            slot_key=self.slot_key,
            slot_name=self.slot_name,
            item_id=self.item_id,
            item_name=self.item_name,
            quality=self.quality,
            level=self.level,
            stat_bonuses=dict(self.stat_bonuses),
            description=self.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_key": self.slot_key,
            "slot_name": self.slot_name,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "quality": self.quality,
            "level": self.level,
            "stat_bonuses": dict(self.stat_bonuses),
            "description": self.description,
        }

    @property
    def is_equipped(self) -> bool:
        return bool(self.item_id or self.item_name or self.stat_bonuses or self.quality or self.level > 0)


@dataclass(slots=True)
class RareTreasureNodeData:
    node_id: str
    node_name: str
    index: int
    is_unlocked: bool = False
    linked_skill_slot: str | None = None
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def copy(self) -> "RareTreasureNodeData":
        return RareTreasureNodeData(
            node_id=self.node_id,
            node_name=self.node_name,
            index=self.index,
            is_unlocked=self.is_unlocked,
            linked_skill_slot=self.linked_skill_slot,
            stat_bonuses=dict(self.stat_bonuses),
            description=self.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "index": self.index,
            "is_unlocked": self.is_unlocked,
            "linked_skill_slot": self.linked_skill_slot,
            "stat_bonuses": dict(self.stat_bonuses),
            "description": self.description,
        }


def default_equipment_slots() -> list[EquipmentSlotData]:
    return [EquipmentSlotData(slot_key=slot_key, slot_name=slot_name) for slot_key, slot_name in EQUIPMENT_SLOT_DEFINITIONS]


def _build_default_rare_treasure_node(template_id: str, index: int, *, linked_skill_slot: str | None = None, unlocked: bool = False) -> RareTreasureNodeData:
    linked_suffix = f"，解锁 {SKILL_SLOT_DISPLAY_NAMES.get(linked_skill_slot, linked_skill_slot)} 4 级" if linked_skill_slot else ""
    return RareTreasureNodeData(
        node_id=f"{template_id}_rare_treasure_{index}",
        node_name=f"专属奇珍 {index}",
        index=index,
        is_unlocked=unlocked,
        linked_skill_slot=linked_skill_slot,
        description=f"专属奇珍节点 {index}{linked_suffix}",
    )


def equipment_slot_from_dict(data: dict[str, Any]) -> EquipmentSlotData:
    return EquipmentSlotData(
        slot_key=data.get("slot_key", ""),
        slot_name=data.get("slot_name", data.get("slot_key", "装备位")),
        item_id=data.get("item_id", ""),
        item_name=data.get("item_name", ""),
        quality=data.get("quality", ""),
        level=int(data.get("level", 0) or 0),
        stat_bonuses={key: float(value) for key, value in data.get("stat_bonuses", {}).items()},
        description=data.get("description", ""),
    )


def rare_treasure_node_from_dict(data: dict[str, Any]) -> RareTreasureNodeData:
    linked_skill_slot = normalize_skill_slot_key(data.get("linked_skill_slot"))
    return RareTreasureNodeData(
        node_id=data.get("node_id", ""),
        node_name=data.get("node_name", f"专属奇珍 {data.get('index', 1)}"),
        index=int(data.get("index", 1) or 1),
        is_unlocked=bool(data.get("is_unlocked", False)),
        linked_skill_slot=linked_skill_slot,
        stat_bonuses={key: float(value) for key, value in data.get("stat_bonuses", {}).items()},
        description=data.get("description", ""),
    )


def normalize_equipment_slots(slots: list[EquipmentSlotData] | tuple[EquipmentSlotData, ...] | None) -> list[EquipmentSlotData]:
    slot_by_key: dict[str, EquipmentSlotData] = {}
    for slot in slots or []:
        if slot.slot_key and slot.slot_key not in slot_by_key:
            slot_by_key[slot.slot_key] = slot.copy()
    normalized: list[EquipmentSlotData] = []
    for slot_key, slot_name in EQUIPMENT_SLOT_DEFINITIONS:
        current = slot_by_key.get(slot_key)
        if current is None:
            normalized.append(EquipmentSlotData(slot_key=slot_key, slot_name=slot_name))
            continue
        current.slot_name = current.slot_name or slot_name
        normalized.append(current)
    return normalized


def aggregate_equipment_slot_bonuses(slots: list[EquipmentSlotData] | tuple[EquipmentSlotData, ...] | None) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for slot in slots or []:
        for stat_name, bonus in slot.stat_bonuses.items():
            aggregated[stat_name] = aggregated.get(stat_name, 0.0) + float(bonus)
    return aggregated


def normalize_rare_treasure_nodes(
    template_id: str,
    locked_skill_slots: list[str] | tuple[str, ...],
    nodes: list[RareTreasureNodeData] | tuple[RareTreasureNodeData, ...] | None,
    *,
    has_rare_treasure: bool,
) -> list[RareTreasureNodeData]:
    linked_skill_by_index = {
        RARE_TREASURE_LINKED_NODE_INDEXES[index]: locked_skill_slots[index]
        for index in range(min(len(locked_skill_slots), len(RARE_TREASURE_LINKED_NODE_INDEXES)))
    }
    node_by_index: dict[int, RareTreasureNodeData] = {}
    for node in nodes or []:
        if 1 <= node.index <= 9 and node.index not in node_by_index:
            node_by_index[node.index] = node.copy()
    normalized: list[RareTreasureNodeData] = []
    for index in range(1, 10):
        linked_skill_slot = linked_skill_by_index.get(index)
        current = node_by_index.get(index) or _build_default_rare_treasure_node(
            template_id,
            index,
            linked_skill_slot=linked_skill_slot,
            unlocked=has_rare_treasure,
        )
        current.node_id = current.node_id or f"{template_id}_rare_treasure_{index}"
        current.node_name = current.node_name or f"专属奇珍 {index}"
        current.linked_skill_slot = current.linked_skill_slot or linked_skill_slot
        if not current.description:
            current.description = _build_default_rare_treasure_node(
                template_id,
                index,
                linked_skill_slot=current.linked_skill_slot,
                unlocked=current.is_unlocked,
            ).description
        if has_rare_treasure:
            current.is_unlocked = True
        normalized.append(current)
    return normalized


@dataclass(slots=True)
class SkillEffectData:
    effect_type: str
    value: float
    duration: int = 0
    chance: float = 1.0
    status_filter: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_type": self.effect_type,
            "value": self.value,
            "duration": self.duration,
            "chance": self.chance,
            "status_filter": self.status_filter,
            "params": dict(self.params),
        }


@dataclass(slots=True)
class SkillData:
    skill_id: str
    name: str
    skill_type: str
    target_type: str
    damage_coefficient: float
    target_side: str = "enemy"
    trigger_timing: str = "行动时自动"
    energy_cost: int = 0
    hit_count: int = 1
    retarget_per_hit: bool = False
    level: int = 1
    effects: list[SkillEffectData] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    damage_by_level: dict[int, float] = field(default_factory=dict)
    hit_count_by_level: dict[int, int] = field(default_factory=dict)
    effects_by_level: dict[int, list[SkillEffectData]] = field(default_factory=dict)
    round_start_effects: list[SkillEffectData] = field(default_factory=list)
    round_start_effects_by_level: dict[int, list[SkillEffectData]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "skill_type": self.skill_type,
            "target_type": self.target_type,
            "damage_coefficient": self.damage_coefficient,
            "target_side": self.target_side,
            "trigger_timing": self.trigger_timing,
            "energy_cost": self.energy_cost,
            "hit_count": self.hit_count,
            "retarget_per_hit": self.retarget_per_hit,
            "level": self.level,
            "effects": [effect.to_dict() for effect in self.effects],
            "params": dict(self.params),
            "damage_by_level": {str(level): value for level, value in self.damage_by_level.items()},
            "hit_count_by_level": {str(level): value for level, value in self.hit_count_by_level.items()},
            "effects_by_level": {str(level): [effect.to_dict() for effect in effects] for level, effects in self.effects_by_level.items()},
            "round_start_effects": [effect.to_dict() for effect in self.round_start_effects],
            "round_start_effects_by_level": {str(level): [effect.to_dict() for effect in effects] for level, effects in self.round_start_effects_by_level.items()},
        }


def default_passive_skill(slot: int) -> SkillData:
    return SkillData(
        skill_id=f"default_passive_{slot}",
        name=f"被动技能{slot}",
        skill_type="被动",
        target_type="自身",
        damage_coefficient=0.0,
        target_side="self",
        trigger_timing="战斗开始",
        energy_cost=0,
    )


def is_generic_basic_attack_skill(skill: SkillData) -> bool:
    return (
        skill.skill_type == "普攻"
        and skill.target_type == "单体"
        and skill.target_side == "enemy"
        and skill.trigger_timing == "行动时自动"
        and abs(skill.damage_coefficient - 1.0) < 1e-9
        and skill.energy_cost == 0
        and skill.hit_count == 1
        and not skill.retarget_per_hit
        and not skill.effects
        and not skill.params
        and not skill.damage_by_level
        and not skill.hit_count_by_level
        and not skill.effects_by_level
        and not skill.round_start_effects
        and not skill.round_start_effects_by_level
    )


def default_passive_skill_3(hero_id: str = "default") -> SkillData:
    skill = default_passive_skill(3)
    skill.skill_id = f"{hero_id}_passive_3"
    return skill


def normalize_passive_skill_3_slot(skill: SkillData, *, hero_id: str = "default") -> SkillData:
    normalized = deepcopy(skill)
    if is_generic_basic_attack_skill(normalized):
        return default_passive_skill_3(hero_id)
    normalized.skill_type = "被动"
    return normalized


def default_basic_attack_skill(hero_id: str = "default") -> SkillData:
    return SkillData(
        skill_id=f"{hero_id}_basic_attack",
        name="普通一击",
        skill_type="普攻",
        target_type="单体",
        damage_coefficient=1.0,
        target_side="enemy",
        trigger_timing="行动时自动",
        energy_cost=0,
    )


def default_ultimate_skill(hero_id: str = "default") -> SkillData:
    return SkillData(
        skill_id=f"{hero_id}_ultimate",
        name="必杀技",
        skill_type="必杀",
        target_type="单体",
        damage_coefficient=1.5,
        target_side="enemy",
        trigger_timing="怒气满自动",
        energy_cost=100,
    )


def default_rare_treasure_locked_skill_slots(seed_text: str) -> list[str]:
    weighted_slots = sorted(
        SKILL_SLOT_KEYS,
        key=lambda slot: hashlib.sha256(f"{seed_text}:{SKILL_SLOT_HASH_KEYS.get(slot, slot)}".encode("utf-8")).hexdigest(),
    )
    return list(weighted_slots[:2])


def normalize_rare_treasure_locked_skill_slots(seed_text: str, slots: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized: list[str] = []
    for slot in slots or []:
        mapped_slot = normalize_skill_slot_key(slot)
        if mapped_slot is not None and mapped_slot not in normalized:
            normalized.append(mapped_slot)
    for fallback in default_rare_treasure_locked_skill_slots(seed_text):
        if fallback not in normalized:
            normalized.append(fallback)
        if len(normalized) == 2:
            break
    return normalized[:2]


@dataclass(slots=True)
class BondEffectData:
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    damage_reduction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stat_bonuses": dict(self.stat_bonuses),
            "damage_reduction": self.damage_reduction,
        }


@dataclass(slots=True)
class BondData:
    bond_id: str
    name: str
    hero_ids: list[str]
    effect: BondEffectData

    def to_dict(self) -> dict[str, Any]:
        return {
            "bond_id": self.bond_id,
            "name": self.name,
            "hero_ids": list(self.hero_ids),
            "effect": self.effect.to_dict(),
        }


@dataclass(slots=True)
class HeroData(BaseData):
    template_id: str = ""
    name: str = ""
    camp: Camp = Camp.SHU
    profession: Profession = Profession.PHYSICAL
    role: HeroRole = HeroRole.ASSASSIN
    hero_quality: HeroQuality = HeroQuality.S
    awakening_level: AwakeningLevel = AwakeningLevel.EXCELLENT
    level: int = 1
    base_stats: HeroStats = field(default_factory=lambda: HeroStats(1000, 100, 50, 100, 0.1, 0.5, 0.0, 0.0, 0.0))
    passive_skill_3: SkillData = field(default_factory=default_passive_skill_3)
    passive_skills: list[SkillData] = field(default_factory=lambda: [default_passive_skill(1), default_passive_skill(2)])
    ultimate_skill: SkillData = field(default_factory=default_ultimate_skill)
    bonds: list[BondData] = field(default_factory=list)
    equipment_slots: list[EquipmentSlotData] = field(default_factory=default_equipment_slots)
    equipment_bonus: dict[str, float] = field(default_factory=dict)
    rune_bonus: dict[str, float] = field(default_factory=dict)
    artifact_bonus: dict[str, float] = field(default_factory=dict)
    bond_bonus: dict[str, float] = field(default_factory=dict)
    technology_bonus: dict[str, float] = field(default_factory=dict)
    has_rare_treasure: bool = False
    rare_treasure_locked_skill_slots: list[str] = field(default_factory=list)
    rare_treasure_nodes: list[RareTreasureNodeData] = field(default_factory=list)
    obtained_from: str = "template"
    acquired_at: str = ""

    def __post_init__(self) -> None:
        if not self.template_id:
            self.template_id = self.id
        self.awakening_level = clamp_awakening_for_quality(self.hero_quality, self.awakening_level)
        self.level = max(1, min(self.level, self.hero_quality.level_cap))
        self.passive_skills = list(self.passive_skills[:2])
        while len(self.passive_skills) < 2:
            self.passive_skills.append(default_passive_skill(len(self.passive_skills) + 1))
        self.refresh_structured_progression()


    def refresh_structured_progression(self) -> None:
        self.rare_treasure_locked_skill_slots = normalize_rare_treasure_locked_skill_slots(self.template_id or self.id, self.rare_treasure_locked_skill_slots)
        self.equipment_slots = normalize_equipment_slots(self.equipment_slots)
        slot_bonus = aggregate_equipment_slot_bonuses(self.equipment_slots)
        self.equipment_bonus = slot_bonus or dict(self.equipment_bonus)
        self.rare_treasure_nodes = normalize_rare_treasure_nodes(
            self.template_id or self.id,
            self.rare_treasure_locked_skill_slots,
            self.rare_treasure_nodes,
            has_rare_treasure=self.has_rare_treasure,
        )
        if self.rare_treasure_nodes and all(node.is_unlocked for node in self.rare_treasure_nodes):
            self.has_rare_treasure = True

    def current_equipment_bonus(self) -> dict[str, float]:
        slot_bonus = aggregate_equipment_slot_bonuses(self.equipment_slots)
        return slot_bonus or dict(self.equipment_bonus)

    def to_dict(self) -> dict[str, Any]:
        data = BaseData.to_dict(self)
        data.update(
            {
                "template_id": self.template_id,
                "camp": self.camp.value,
                "profession": self.profession.value,
                "role": self.role.value,
                "hero_quality": self.hero_quality.value,
                "awakening_level": self.awakening_level.value,
                "base_stats": self.base_stats.to_dict(),
                "passive_skill_3": self.passive_skill_3.to_dict(),
                "passive_skills": [skill.to_dict() for skill in self.passive_skills],
                "ultimate_skill": self.ultimate_skill.to_dict(),
                "bonds": [bond.to_dict() for bond in self.bonds],
                "equipment_slots": [slot.to_dict() for slot in self.equipment_slots],
                "equipment_bonus": dict(self.equipment_bonus),
                "rune_bonus": dict(self.rune_bonus),
                "artifact_bonus": dict(self.artifact_bonus),
                "bond_bonus": dict(self.bond_bonus),
                "technology_bonus": dict(self.technology_bonus),
                "has_rare_treasure": self.has_rare_treasure,
                "rare_treasure_locked_skill_slots": list(self.rare_treasure_locked_skill_slots),
                "rare_treasure_nodes": [node.to_dict() for node in self.rare_treasure_nodes],
                "obtained_from": self.obtained_from,
                "acquired_at": self.acquired_at,
            }
        )
        return data


@dataclass(slots=True)
class FormationData(BaseData):
    name: str = "默认阵容"
    positions: dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = BaseData.to_dict(self)
        data["positions"] = {str(key): value for key, value in self.positions.items()}
        return data


@dataclass(slots=True)
class PlayerProfileData(BaseData):
    name: str = "主公"
    level: int = 1
    exp: int = 0
    power: int = 0
    currencies: dict[str, int] = field(default_factory=lambda: {"元宝": 0, "铜币": 0, "武将经验": 0})


@dataclass(slots=True)
class PlayerData(BaseData):
    profile: PlayerProfileData = field(default_factory=lambda: PlayerProfileData(id="profile"))
    heroes: list[HeroData] = field(default_factory=list)
    formations: list[FormationData] = field(default_factory=list)
    stage_progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=lambda: {"battle_speed": 1, "auto_battle": True})
    stamina: int = 100
    stamina_last_updated_at: str = ""
    idle_last_claimed_at: str = ""
    daily_reset_at: str = ""
    stamina_purchase_times_today: int = 0
    quick_idle_used_today: int = 0

    def __post_init__(self) -> None:
        self.stamina = max(0, min(100, int(self.stamina)))
        self.stamina_last_updated_at = self.stamina_last_updated_at or ""
        self.idle_last_claimed_at = self.idle_last_claimed_at or ""
        self.daily_reset_at = self.daily_reset_at or ""
        self.stamina_purchase_times_today = max(0, int(self.stamina_purchase_times_today))
        self.quick_idle_used_today = max(0, int(self.quick_idle_used_today))

    def to_dict(self) -> dict[str, Any]:
        data = BaseData.to_dict(self)
        data.update(
            {
                "profile": self.profile.to_dict(),
                "heroes": [hero.to_dict() for hero in self.heroes],
                "formations": [formation.to_dict() for formation in self.formations],
            }
        )
        return data


def hero_from_dict(data: dict[str, Any]) -> HeroData:
    passive_skills = [skill_from_dict(skill) for skill in data.get("passive_skills", [])]
    passive_skill_3 = normalize_passive_skill_3_slot(
        skill_from_dict(
            data.get("passive_skill_3")
            # 兼容旧 normal_attack_skill 读取；to_dict 只会写出 passive_skill_3。
            or data.get("normal_attack_skill")
            or default_passive_skill_3(data["id"]).to_dict()
        ),
        hero_id=data["id"],
    )
    ultimate_source = data.get("ultimate_skill") or data.get("active_skill") or default_ultimate_skill(data["id"]).to_dict()
    raw_quality = data.get("hero_quality") or data.get("quality") or HeroQuality.S.value
    hero_quality = HeroQuality(raw_quality) if raw_quality in {quality.value for quality in HeroQuality} else legacy_quality_to_hero_quality(raw_quality)
    raw_awakening = data.get("awakening_level") or (data.get("quality") if data.get("quality") not in {quality.value for quality in HeroQuality} else None) or hero_quality.default_awakening.value
    awakening_level = AwakeningLevel(raw_awakening)
    return HeroData(
        id=data["id"],
        version=data.get("version", 1),
        metadata=data.get("metadata", {}),
        template_id=data.get("template_id", data["id"]),
        name=data["name"],
        camp=Camp(data["camp"]),
        profession=Profession(data["profession"]),
        role=HeroRole(data.get("role", _default_role_from_profession(Profession(data["profession"])).value)),
        hero_quality=hero_quality,
        awakening_level=awakening_level,
        level=data.get("level", 1),
        base_stats=HeroStats(**data["base_stats"]),
        passive_skill_3=passive_skill_3,
        passive_skills=passive_skills,
        ultimate_skill=skill_from_dict(ultimate_source),
        bonds=[bond_from_dict(bond) for bond in data.get("bonds", [])],
        equipment_slots=[equipment_slot_from_dict(slot) for slot in data.get("equipment_slots", [])],
        equipment_bonus=data.get("equipment_bonus", {}),
        rune_bonus=data.get("rune_bonus", {}),
        artifact_bonus=data.get("artifact_bonus", {}),
        bond_bonus=data.get("bond_bonus", {}),
        technology_bonus=data.get("technology_bonus", {}),
        has_rare_treasure=bool(data.get("has_rare_treasure", False)),
        rare_treasure_locked_skill_slots=list(data.get("rare_treasure_locked_skill_slots", [])),
        rare_treasure_nodes=[rare_treasure_node_from_dict(node) for node in data.get("rare_treasure_nodes", [])],
        obtained_from=data.get("obtained_from", "template"),
        acquired_at=data.get("acquired_at", ""),
    )


def _default_role_from_profession(profession: Profession) -> HeroRole:
    return {
        Profession.TANK: HeroRole.VANGUARD,
        Profession.PHYSICAL: HeroRole.ASSASSIN,
        Profession.MAGICAL: HeroRole.MAGE,
        Profession.HEALER: HeroRole.SUPPORT,
        Profession.CONTROL: HeroRole.MAGE,
    }[profession]


def skill_from_dict(data: dict[str, Any]) -> SkillData:
    skill_type = data["skill_type"]
    trigger_timing = data.get("trigger_timing")
    if trigger_timing == "手动":
        if skill_type == "普攻":
            trigger_timing = "行动时自动"
        elif skill_type in {"主动", "必杀"}:
            trigger_timing = "怒气满自动"
    if trigger_timing is None:
        if skill_type == "被动":
            trigger_timing = "战斗开始"
        elif skill_type == "普攻":
            trigger_timing = "行动时自动"
        elif skill_type in {"主动", "必杀"}:
            trigger_timing = "怒气满自动"
        else:
            trigger_timing = "行动时自动"
    return SkillData(
        skill_id=data["skill_id"],
        name=data["name"],
        skill_type=skill_type,
        target_type=data["target_type"],
        damage_coefficient=data["damage_coefficient"],
        target_side=data.get("target_side", "self" if data.get("target_type") == "自身" else "enemy"),
        trigger_timing=trigger_timing,
        energy_cost=data.get("energy_cost", 100 if skill_type in {"主动", "必杀"} else 0),
        hit_count=max(1, int(data.get("hit_count", 1))),
        retarget_per_hit=bool(data.get("retarget_per_hit", False)),
        level=data.get("level", 1),
        effects=[SkillEffectData(**effect) for effect in data.get("effects", [])],
        params=data.get("params", {}),
        damage_by_level={int(level): value for level, value in data.get("damage_by_level", {}).items()},
        hit_count_by_level={int(level): int(value) for level, value in data.get("hit_count_by_level", {}).items()},
        effects_by_level={int(level): [SkillEffectData(**effect) for effect in effects] for level, effects in data.get("effects_by_level", {}).items()},
        round_start_effects=[SkillEffectData(**effect) for effect in data.get("round_start_effects", [])],
        round_start_effects_by_level={int(level): [SkillEffectData(**effect) for effect in effects] for level, effects in data.get("round_start_effects_by_level", {}).items()},
    )


def bond_from_dict(data: dict[str, Any]) -> BondData:
    return BondData(
        bond_id=data["bond_id"],
        name=data["name"],
        hero_ids=list(data.get("hero_ids", [])),
        effect=BondEffectData(
            stat_bonuses=data.get("effect", {}).get("stat_bonuses", {}),
            damage_reduction=data.get("effect", {}).get("damage_reduction", 0.0),
        ),
    )


def formation_from_dict(data: dict[str, Any]) -> FormationData:
    positions = {int(key): value for key, value in data.get("positions", {}).items()}
    return FormationData(
        id=data["id"],
        version=data.get("version", 1),
        metadata=data.get("metadata", {}),
        name=data.get("name", "默认阵容"),
        positions=positions,
    )


def player_profile_from_dict(data: dict[str, Any]) -> PlayerProfileData:
    return PlayerProfileData(
        id=data["id"],
        version=data.get("version", 1),
        metadata=data.get("metadata", {}),
        name=data.get("name", "主公"),
        level=data.get("level", 1),
        exp=data.get("exp", 0),
        power=data.get("power", 0),
        currencies={"元宝": 0, "铜币": 0, "武将经验": 0, **data.get("currencies", {})},
    )


def player_from_dict(data: dict[str, Any]) -> PlayerData:
    return PlayerData(
        id=data["id"],
        version=data.get("version", 1),
        metadata=data.get("metadata", {}),
        profile=player_profile_from_dict(data["profile"]),
        heroes=[hero_from_dict(hero) for hero in data.get("heroes", [])],
        formations=[formation_from_dict(formation) for formation in data.get("formations", [])],
        stage_progress=data.get("stage_progress", {}),
        settings=data.get("settings", {"battle_speed": 1, "auto_battle": True}),
        stamina=data.get("stamina", 100),
        stamina_last_updated_at=data.get("stamina_last_updated_at", ""),
        idle_last_claimed_at=data.get("idle_last_claimed_at", ""),
        daily_reset_at=data.get("daily_reset_at", ""),
        stamina_purchase_times_today=data.get("stamina_purchase_times_today", 0),
        quick_idle_used_today=data.get("quick_idle_used_today", 0),
    )

