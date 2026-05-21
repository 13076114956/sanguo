from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from game.data.models import AwakeningLevel, HeroData, HeroQuality, HeroRole, HeroStats, SKILL_SLOT_KEYS, SkillData, SkillEffectData, aggregate_equipment_slot_bonuses
from game.utility.math_utils import MathUtils


@dataclass(slots=True)
class CalculatedHeroStats:
    base: HeroStats
    final: HeroStats


@dataclass(slots=True)
class HeroLevelUpPlan:
    requested_levels: int
    actual_levels: int
    target_level: int
    spent_hero_exp: int
    spent_copper: int


class HeroDevelopmentService:
    """武将等级与属性计算服务。"""

    MAX_SKILL_LEVEL = 4
    MIN_LEVEL_UP_EXP_COST = 500
    MIN_LEVEL_UP_COIN_COST = 60
    LEVEL_UP_EXP_GROWTH_RATE = 0.1
    LEVEL_UP_COIN_STEP = 15

    def calculate_stats(self, hero: HeroData) -> CalculatedHeroStats:
        level_factor = (hero.level - 1) * 0.05
        quality_factor = hero.hero_quality.quality_factor
        awakening_factor = hero.awakening_level.awakening_factor
        base = HeroStats(
            hp=hero.base_stats.hp * (1 + level_factor) * (1 + quality_factor) * (1 + awakening_factor),
            attack=hero.base_stats.attack * (1 + level_factor) * (1 + quality_factor) * (1 + awakening_factor),
            defense=hero.base_stats.defense * (1 + level_factor) * (1 + quality_factor) * (1 + awakening_factor),
            speed=hero.base_stats.speed * (1 + quality_factor * 0.3 + awakening_factor * 0.15),
            crit_rate=MathUtils.percent(hero.base_stats.crit_rate),
            crit_damage=MathUtils.clamp(hero.base_stats.crit_damage, 0.5, 3.0),
            armor_break=MathUtils.percent(hero.base_stats.armor_break),
            effect_hit=MathUtils.percent(hero.base_stats.effect_hit),
            effect_resist=MathUtils.percent(hero.base_stats.effect_resist),
        )
        final = HeroStats(
            hp=self._apply_bonus(base.hp, hero, "hp"),
            attack=self._apply_bonus(base.attack, hero, "attack"),
            defense=self._apply_bonus(base.defense, hero, "defense"),
            speed=self._apply_bonus(base.speed, hero, "speed"),
            crit_rate=MathUtils.percent(self._apply_bonus(base.crit_rate, hero, "crit_rate")),
            crit_damage=MathUtils.clamp(self._apply_bonus(base.crit_damage, hero, "crit_damage"), 0.5, 3.0),
            armor_break=MathUtils.percent(self._apply_bonus(base.armor_break, hero, "armor_break")),
            effect_hit=MathUtils.percent(self._apply_bonus(base.effect_hit, hero, "effect_hit")),
            effect_resist=MathUtils.percent(self._apply_bonus(base.effect_resist, hero, "effect_resist")),
        )
        return CalculatedHeroStats(base=base, final=final)

    def level_up(self, hero: HeroData, levels: int = 1) -> HeroData:
        target_level = min(hero.level + max(0, levels), hero.hero_quality.level_cap)
        hero.level = target_level
        return hero

    def level_up_cost(self, hero: HeroData, target_level: int | None = None) -> tuple[int, int]:
        next_level = target_level or (hero.level + 1)
        if next_level <= hero.level:
            raise ValueError("目标等级必须高于当前等级")
        if next_level > hero.hero_quality.level_cap:
            raise ValueError(f"目标等级超过上限：{hero.hero_quality.level_cap}")
        exp_cost = int(round(self.MIN_LEVEL_UP_EXP_COST * ((1 + self.LEVEL_UP_EXP_GROWTH_RATE) ** (next_level - 2))))
        multiplier = 1.0 + hero.hero_quality.quality_factor
        copper_cost = int(round((self.MIN_LEVEL_UP_COIN_COST + (next_level - 1) * self.LEVEL_UP_COIN_STEP) * multiplier))
        return max(1, exp_cost), max(1, copper_cost)

    def plan_level_ups(
        self,
        hero: HeroData,
        *,
        available_hero_exp: int,
        available_copper: int,
        requested_levels: int | None = None,
    ) -> HeroLevelUpPlan:
        remaining_levels = max(0, hero.hero_quality.level_cap - hero.level)
        normalized_requested = remaining_levels if requested_levels is None else max(0, requested_levels)
        planned_levels = min(remaining_levels, normalized_requested)
        spent_hero_exp = 0
        spent_copper = 0
        actual_levels = 0
        for offset in range(1, planned_levels + 1):
            target_level = hero.level + offset
            exp_cost, copper_cost = self.level_up_cost(hero, target_level)
            if spent_hero_exp + exp_cost > available_hero_exp or spent_copper + copper_cost > available_copper:
                break
            spent_hero_exp += exp_cost
            spent_copper += copper_cost
            actual_levels += 1
        return HeroLevelUpPlan(
            requested_levels=normalized_requested,
            actual_levels=actual_levels,
            target_level=hero.level + actual_levels,
            spent_hero_exp=spent_hero_exp,
            spent_copper=spent_copper,
        )

    def validate_level_cap(self, hero: HeroData) -> bool:
        return hero.level <= hero.hero_quality.level_cap

    def resolve_base_skill_level(self, hero: HeroData) -> int:
        return min(self.MAX_SKILL_LEVEL, max(1, hero.level // 60))

    def resolve_skill_level(self, hero: HeroData, skill_slot: str | None = None) -> int:
        skill_level = self.resolve_base_skill_level(hero)
        if skill_slot is None or skill_level < self.MAX_SKILL_LEVEL:
            return skill_level
        if hero.has_rare_treasure or skill_slot not in hero.rare_treasure_locked_skill_slots:
            return skill_level
        return self.MAX_SKILL_LEVEL - 1

    def materialize_skill(self, skill: SkillData, hero: HeroData, skill_slot: str) -> SkillData:
        skill_level = self.resolve_skill_level(hero, skill_slot)
        materialized = SkillData(
            skill_id=skill.skill_id,
            name=skill.name,
            skill_type=skill.skill_type,
            target_type=skill.target_type,
            damage_coefficient=skill.damage_by_level.get(skill_level, skill.damage_coefficient),
            target_side=skill.target_side,
            trigger_timing=skill.trigger_timing,
            energy_cost=skill.energy_cost,
            hit_count=skill.hit_count_by_level.get(skill_level, skill.hit_count),
            retarget_per_hit=skill.retarget_per_hit,
            level=skill_level,
            effects=[deepcopy(effect) for effect in skill.effects_by_level.get(skill_level, skill.effects)],
            params=deepcopy(skill.params),
            damage_by_level=dict(skill.damage_by_level),
            hit_count_by_level=dict(skill.hit_count_by_level),
            effects_by_level={level: [deepcopy(effect) for effect in effects] for level, effects in skill.effects_by_level.items()},
            round_start_effects=[deepcopy(effect) for effect in skill.round_start_effects_by_level.get(skill_level, skill.round_start_effects)],
            round_start_effects_by_level={level: [deepcopy(effect) for effect in effects] for level, effects in skill.round_start_effects_by_level.items()},
        )
        return materialized

    def prepare_hero_for_battle(self, hero: HeroData) -> HeroData:
        return HeroData(
            id=hero.id,
            version=hero.version,
            metadata=dict(hero.metadata),
            template_id=hero.template_id,
            name=hero.name,
            camp=hero.camp,
            profession=hero.profession,
            role=hero.role,
            hero_quality=hero.hero_quality,
            awakening_level=hero.awakening_level,
            level=hero.level,
            base_stats=hero.base_stats.copy(),
            passive_skill_3=self.materialize_skill(hero.passive_skill_3, hero, "passive_3"),
            passive_skills=[self.materialize_skill(skill, hero, f"passive_{index + 1}") for index, skill in enumerate(hero.passive_skills)],
            ultimate_skill=self.materialize_skill(hero.ultimate_skill, hero, "ultimate"),
            bonds=list(hero.bonds),
            equipment_slots=[slot.copy() for slot in hero.equipment_slots],
            equipment_bonus=dict(hero.equipment_bonus),
            rune_bonus=dict(hero.rune_bonus),
            artifact_bonus=dict(hero.artifact_bonus),
            bond_bonus=dict(hero.bond_bonus),
            technology_bonus=dict(hero.technology_bonus),
            has_rare_treasure=hero.has_rare_treasure,
            rare_treasure_locked_skill_slots=list(hero.rare_treasure_locked_skill_slots),
            rare_treasure_nodes=[node.copy() for node in hero.rare_treasure_nodes],
            obtained_from=hero.obtained_from,
            acquired_at=hero.acquired_at,
        )

    def create_card_from_template(self, template: HeroData, *, card_id: str | None = None, obtained_from: str = "summon") -> HeroData:
        template_id = template.template_id or template.id
        acquired_at = datetime.now(UTC).isoformat()
        return HeroData(
            id=card_id or f"{template_id}_card_{acquired_at.replace(':', '').replace('-', '').replace('+00:00', 'Z').replace('.', '')}",
            version=template.version,
            metadata=dict(template.metadata),
            template_id=template_id,
            name=template.name,
            camp=template.camp,
            profession=template.profession,
            role=template.role,
            hero_quality=template.hero_quality,
            awakening_level=template.hero_quality.default_awakening,
            level=1,
            base_stats=template.base_stats.copy(),
            passive_skill_3=template.passive_skill_3,
            passive_skills=list(template.passive_skills),
            ultimate_skill=template.ultimate_skill,
            bonds=list(template.bonds),
            equipment_slots=[slot.copy() for slot in template.equipment_slots],
            equipment_bonus=dict(template.equipment_bonus),
            rune_bonus=dict(template.rune_bonus),
            artifact_bonus=dict(template.artifact_bonus),
            bond_bonus=dict(template.bond_bonus),
            technology_bonus=dict(template.technology_bonus),
            has_rare_treasure=template.has_rare_treasure,
            rare_treasure_locked_skill_slots=list(template.rare_treasure_locked_skill_slots),
            rare_treasure_nodes=[node.copy() for node in template.rare_treasure_nodes],
            obtained_from=obtained_from,
            acquired_at=acquired_at,
        )

    def create_stage_enemy_from_template(
        self,
        template: HeroData,
        *,
        stage_id: str,
        position: int,
        level: int,
        stat_multiplier: float = 1.0,
    ) -> HeroData:
        enemy = HeroData(
            id=f"{stage_id}_{position}_{template.id}",
            version=template.version,
            metadata=dict(template.metadata),
            template_id=template.template_id or template.id,
            name=template.name,
            camp=template.camp,
            profession=template.profession,
            role=template.role,
            hero_quality=template.hero_quality,
            awakening_level=template.awakening_level,
            level=level,
            base_stats=HeroStats(
                hp=template.base_stats.hp * stat_multiplier,
                attack=template.base_stats.attack * stat_multiplier,
                defense=template.base_stats.defense * stat_multiplier,
                speed=template.base_stats.speed * max(1.0, stat_multiplier * 0.15),
                crit_rate=template.base_stats.crit_rate,
                crit_damage=template.base_stats.crit_damage,
                armor_break=template.base_stats.armor_break,
                effect_hit=template.base_stats.effect_hit,
                effect_resist=template.base_stats.effect_resist,
            ),
            passive_skill_3=deepcopy(template.passive_skill_3),
            passive_skills=[deepcopy(skill) for skill in template.passive_skills],
            ultimate_skill=deepcopy(template.ultimate_skill),
            bonds=list(template.bonds),
            equipment_slots=[slot.copy() for slot in template.equipment_slots],
            has_rare_treasure=template.has_rare_treasure,
            rare_treasure_locked_skill_slots=list(template.rare_treasure_locked_skill_slots),
            rare_treasure_nodes=[node.copy() for node in template.rare_treasure_nodes],
            obtained_from="stage_enemy",
            acquired_at="",
        )
        return enemy

    def visible_heroes(self, heroes: list[HeroData]) -> list[HeroData]:
        best_by_template: dict[str, HeroData] = {}
        for hero in heroes:
            current = best_by_template.get(hero.template_id)
            if current is None or self._hero_priority(hero) > self._hero_priority(current):
                best_by_template[hero.template_id] = hero
        return list(best_by_template.values())

    def resolve_best_card(self, heroes: list[HeroData], template_or_card_id: str) -> HeroData | None:
        exact = next((hero for hero in heroes if hero.id == template_or_card_id), None)
        if exact is not None:
            return exact
        candidates = [hero for hero in heroes if hero.template_id == template_or_card_id]
        if not candidates:
            return None
        return max(candidates, key=self._hero_priority)

    def can_fuse_awakening(self, left: HeroData, right: HeroData) -> bool:
        return (
            left.id != right.id
            and left.template_id == right.template_id
            and left.awakening_level == right.awakening_level
            and left.awakening_level.order < left.hero_quality.max_awakening.order
        )

    def fuse_awakening(self, heroes: list[HeroData], left_id: str, right_id: str) -> tuple[list[HeroData], HeroData]:
        left = next((hero for hero in heroes if hero.id == left_id), None)
        right = next((hero for hero in heroes if hero.id == right_id), None)
        if left is None or right is None:
            raise ValueError("用于合成的武将卡不存在")
        if not self.can_fuse_awakening(left, right):
            raise ValueError("武将觉醒等级只能同名同阶两两合成")
        next_awakening = list(AwakeningLevel)[left.awakening_level.order + 1]
        fused_card = HeroData(
            id=f"{left.template_id}_fused_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            version=left.version,
            metadata=dict(left.metadata),
            template_id=left.template_id,
            name=left.name,
            camp=left.camp,
            profession=left.profession,
            role=left.role,
            hero_quality=left.hero_quality,
            awakening_level=next_awakening,
            level=1,
            base_stats=left.base_stats.copy(),
            passive_skill_3=left.passive_skill_3,
            passive_skills=list(left.passive_skills),
            ultimate_skill=left.ultimate_skill,
            bonds=list(left.bonds),
            equipment_slots=[],
            equipment_bonus={},
            rune_bonus={},
            artifact_bonus={},
            bond_bonus={},
            technology_bonus={},
            has_rare_treasure=False,
            rare_treasure_locked_skill_slots=list(left.rare_treasure_locked_skill_slots or SKILL_SLOT_KEYS[:2]),
            rare_treasure_nodes=[],
            obtained_from="fusion",
            acquired_at=datetime.now(UTC).isoformat(),
        )
        remaining = [hero for hero in heroes if hero.id not in {left_id, right_id}]
        remaining.append(fused_card)
        return remaining, fused_card

    @staticmethod
    def _hero_priority(hero: HeroData) -> tuple[int, int, str, str]:
        return (hero.awakening_level.order, hero.level, hero.acquired_at, hero.id)

    @staticmethod
    def _apply_bonus(value: float, hero: HeroData, stat_name: str) -> float:
        equipment_bonus = aggregate_equipment_slot_bonuses(hero.equipment_slots) or hero.equipment_bonus
        total_bonus = sum(
            container.get(stat_name, 0.0)
            for container in (
                equipment_bonus,
                hero.rune_bonus,
                hero.artifact_bonus,
                hero.bond_bonus,
                hero.technology_bonus,
            )
        )
        return value * (1 + total_bonus)


def quality_from_name(name: str) -> HeroQuality:
    return HeroQuality(name)


def awakening_from_name(name: str) -> AwakeningLevel:
    return AwakeningLevel(name)

