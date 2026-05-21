from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from game.data.models import StatusCategory, StatusTag, Camp, HeroData, HeroStats, SkillData, SkillEffectData, default_basic_attack_skill, get_status_category, get_status_tags
from game.develop.hero_service import HeroDevelopmentService
from game.utility.math_utils import MathUtils
from game.utility.random_utils import RandomService


@dataclass(slots=True)
class StatusEffect:
    effect_type: str
    duration: int
    value: float
    source_unit_id: str
    source_skill_id: str = ""
    category: str = StatusCategory.NEUTRAL.value
    tags: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BattleUnit:
    unit_id: str
    hero_id: str
    name: str
    camp: Camp
    position: int
    stats: HeroStats
    passive_skill_3: SkillData
    passive_skills: list[SkillData]
    ultimate_skill: SkillData
    current_hp: float
    max_hp: float
    current_energy: int = 50
    max_energy: int = 100
    status_effects: list[StatusEffect] = field(default_factory=list)
    total_damage_dealt: float = 0.0
    total_damage_taken: float = 0.0
    side: str = "ally"
    last_skill_type: str = ""
    extra_turns: int = 0
    extra_turns_gained_this_round: int = 0
    team_action_count_this_round: int = 0
    team_action_triggers_this_round: int = 0

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def _status_total(self, effect_type: str) -> float:
        return sum(effect.value for effect in self.status_effects if effect.effect_type == effect_type)

    def damage_reduction(self) -> float:
        hp_ratio = (self.current_hp / self.max_hp) if self.max_hp > 0 else 0.0
        conditional_reduction = max(
            (
                effect.value
                for effect in self.status_effects
                if effect.effect_type == "conditional_damage_reduction"
                and hp_ratio <= float(effect.params.get("max_hp_ratio", 1.0))
            ),
            default=0.0,
        )
        guan_yu_guard_reduction = self._status_total("guan_yu_wuhun_guard") * 0.1
        guan_yu_divine_reduction = sum(float(effect.params.get("damage_reduction", 0.0)) for effect in self.status_effects if effect.effect_type == "guan_yu_divine_form")
        return self._status_total("damage_reduction") + conditional_reduction + guan_yu_guard_reduction + guan_yu_divine_reduction

    def speed_modifier(self) -> float:
        special_bonus = sum(float(effect.params.get("speed_bonus", 0.0)) for effect in self.status_effects)
        return self._status_total("speed_bonus") + special_bonus

    def attack_modifier(self) -> float:
        guan_yu_divine_attack = sum(float(effect.params.get("attack_bonus", 0.0)) for effect in self.status_effects if effect.effect_type == "guan_yu_divine_form")
        special_bonus = sum(float(effect.params.get("attack_bonus", 0.0)) for effect in self.status_effects if effect.effect_type != "guan_yu_divine_form")
        stack_bonus = sum(effect.value * float(effect.params.get("attack_bonus_per_stack", 0.0)) for effect in self.status_effects)
        return self._status_total("attack_bonus") + self._status_total("kill_attack_bonus") + guan_yu_divine_attack + special_bonus + stack_bonus

    def defense_modifier(self) -> float:
        special_bonus = sum(float(effect.params.get("defense_bonus", 0.0)) for effect in self.status_effects)
        return self._status_total("defense_bonus") + special_bonus

    def crit_rate_modifier(self) -> float:
        guan_yu_guard_crit = self._status_total("guan_yu_wuhun_guard") * 0.2
        guan_yu_divine_crit = sum(float(effect.params.get("crit_rate_bonus", 0.0)) for effect in self.status_effects if effect.effect_type == "guan_yu_divine_form")
        return self._status_total("crit_rate_bonus") + guan_yu_guard_crit + guan_yu_divine_crit

    def crit_damage_modifier(self) -> float:
        return self._status_total("crit_damage_bonus") + self._status_total("guo_jia_shadow_crit_bonus")

    def skill_damage_modifier(self, skill: SkillData) -> float:
        if skill.skill_type == "普攻":
            return 0.0
        return self._status_total("skill_damage_bonus")

    def can_act(self) -> bool:
        blocked = {"stun", "freeze"}
        return self.is_alive and not any(effect.effect_type in blocked for effect in self.status_effects)

    def can_cast_skill(self) -> bool:
        return self.can_act() and not any(effect.effect_type == "silence" for effect in self.status_effects)


@dataclass(slots=True)
class BattleLogEntry:
    round_index: int
    actor: str
    action: str
    target: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BattleResult:
    winner: str
    rounds: int
    stars: int
    timed_out: bool
    logs: list[BattleLogEntry]
    damage_statistics: dict[str, float]
    rewards: dict[str, int]


class TurnOrderResolver:
    def resolve(self, units: list[BattleUnit]) -> list[BattleUnit]:
        alive_units = [unit for unit in units if unit.is_alive]
        return sorted(alive_units, key=lambda unit: (-(unit.stats.speed * (1 + unit.speed_modifier())), unit.position))


class DamageCalculator:
    COUNTER_MAP = {
        Camp.WEI: Camp.SHU,
        Camp.SHU: Camp.WU,
        Camp.WU: Camp.WEI,
        Camp.QUN: Camp.QUN,
    }

    def __init__(self, random_service: RandomService | None = None) -> None:
        self.random_service = random_service or RandomService()

    def calculate(self, attacker: BattleUnit, defender: BattleUnit, skill: SkillData) -> tuple[float, bool, float]:
        attack_value = attacker.stats.attack * (1 + attacker.attack_modifier())
        defense_value = defender.stats.defense * (1 + defender.defense_modifier())
        bonus_armor_break = 0.0
        bonus_armor_break_status = skill.params.get("bonus_armor_break_from_status")
        if bonus_armor_break_status:
            bonus_armor_break = attacker._status_total(str(bonus_armor_break_status)) * float(skill.params.get("armor_break_per_stack", 0.0))
            defense_value *= 1 - MathUtils.clamp(bonus_armor_break, 0.0, 1.0)
        base_damage = attack_value * skill.damage_coefficient
        base_damage *= 1 + attacker.skill_damage_modifier(skill)
        for effect in skill.effects:
            if effect.effect_type == "bonus_damage_per_stack":
                stack_name = effect.params.get("stack_name", effect.status_filter or "")
                if stack_name:
                    base_damage *= 1 + attacker._status_total(stack_name) * effect.value
        for passive in attacker.passive_skills:
            for effect in passive.effects:
                if effect.effect_type != "damage_multiplier_by_target_hp":
                    continue
                required_skill_id = effect.params.get("required_skill_id")
                if required_skill_id and required_skill_id != skill.skill_id:
                    continue
                hp_ratio = (defender.current_hp / defender.max_hp) if defender.max_hp > 0 else 0.0
                multiplier = 1.0
                for rule in effect.params.get("thresholds", []):
                    if hp_ratio <= float(rule.get("max_hp_ratio", 1.0)):
                        multiplier = max(multiplier, float(rule.get("multiplier", 1.0)))
                base_damage *= multiplier
        is_true_damage = skill.params.get("damage_mode") == "true"
        defense_reduction = 0.0 if is_true_damage else (defense_value / (defense_value + attack_value * 1.5) if (defense_value + attack_value * 1.5) > 0 else 0.0)
        crit_rate = MathUtils.percent(attacker.stats.crit_rate + attacker.crit_rate_modifier())
        crit_damage = MathUtils.clamp(attacker.stats.crit_damage + attacker.crit_damage_modifier(), 0.5, 3.0)
        is_critical = self.random_service.roll() < crit_rate
        critical_bonus = crit_damage if is_critical else 0.0
        counter_bonus = self._camp_counter_bonus(attacker.camp, defender.camp)
        damage_reduction = 0.0 if is_true_damage else MathUtils.percent(defender.damage_reduction())
        frontline_damage_bonus = attacker._status_total("frontline_damage_bonus") if defender.position <= 3 else 0.0
        incoming_damage_bonus = defender._status_total("incoming_damage_bonus")
        final_damage = base_damage * (1 - defense_reduction) * (1 + critical_bonus) * (1 + counter_bonus) * (1 - damage_reduction) * (1 + frontline_damage_bonus) * (1 + incoming_damage_bonus)
        return max(1.0, final_damage), is_critical, counter_bonus

    def _camp_counter_bonus(self, attacker_camp: Camp, defender_camp: Camp) -> float:
        if attacker_camp in {Camp.GOD, Camp.DEMON} or defender_camp in {Camp.GOD, Camp.DEMON}:
            return 0.0
        return 0.25 if self.COUNTER_MAP.get(attacker_camp) == defender_camp else 0.0


class BattleEngine:
    MAX_ROUNDS = 30
    HARMFUL_EFFECTS = {"burn", "poison", "bleed", "stun", "silence", "freeze", "taunt"}
    MODIFIER_EFFECTS = {"attack_bonus", "defense_bonus", "speed_bonus", "damage_reduction", "crit_rate_bonus", "crit_damage_bonus", "frontline_damage_bonus", "skill_damage_bonus"}
    REFRESHABLE_EFFECTS = {"stun", "silence", "freeze", "taunt", "invincible", "untargetable", "lightning_mark", "damage_share", "shield_regen", "heal_over_time", "control_immunity", "frontline_damage_bonus", "cao_cao_alliance", "cao_cao_fatal_immunity_cooldown", "anger_mark", "wood_mark", "heal_on_receive_attack", "pending_revive", "revive_cooldown", "delayed_heal"}
    OVERRIDABLE_EFFECTS = {"burn", "poison", "bleed", *MODIFIER_EFFECTS}
    STACKABLE_EFFECTS = {"shield"}
    REMOVABLE_STATUS_FILTERS = {"buff", "debuff", "control", "damage_over_time", "attribute", "protect", "special"}

    def __init__(self, random_service: RandomService | None = None) -> None:
        self.random_service = random_service or RandomService()
        self.hero_service = HeroDevelopmentService()
        self.turn_order_resolver = TurnOrderResolver()
        self.damage_calculator = DamageCalculator(self.random_service)
        self._log_context_stack: list[dict[str, Any]] = []
        self._cast_sequence = 0

    def _next_cast_id(self) -> str:
        self._cast_sequence += 1
        return f"cast_{self._cast_sequence}"

    def _push_log_context(self, context: dict[str, Any] | None) -> None:
        if not context:
            self._log_context_stack.append({})
            return
        self._log_context_stack.append({key: value for key, value in context.items() if value is not None})

    def _pop_log_context(self) -> None:
        if self._log_context_stack:
            self._log_context_stack.pop()

    def _build_cast_log_context(self, actor: BattleUnit, skill: SkillData, targets: list[BattleUnit]) -> dict[str, Any]:
        target_positions = tuple(sorted({target.position for target in targets}))
        target_unit_ids = tuple(target.unit_id for target in targets)
        target_count = len(targets)
        group_mode = "single"
        if target_count > 1:
            if skill.target_side == "enemy":
                group_mode = "enemy_multi"
            elif skill.target_side in {"ally", "self"}:
                group_mode = "ally_support"
            else:
                group_mode = "multi"
        return {
            "cast_id": self._next_cast_id(),
            "cast_skill_id": skill.skill_id,
            "cast_skill_name": skill.name,
            "cast_skill_type": skill.skill_type,
            "cast_target_side": skill.target_side,
            "cast_target_type": skill.target_type,
            "cast_target_count": target_count,
            "cast_target_positions": target_positions,
            "cast_target_unit_ids": target_unit_ids,
            "cast_group_mode": group_mode,
            "cast_actor_unit_id": actor.unit_id,
            "cast_actor_side": actor.side,
            "cast_actor_position": actor.position,
        }

    def _build_log_metadata(
        self,
        *,
        actor: BattleUnit | None = None,
        target: BattleUnit | None = None,
        event_kind: str,
        metadata: dict[str, Any] | None = None,
        hp_delta: float | None = None,
        energy_delta: float | None = None,
        status_delta: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for context in self._log_context_stack:
            payload.update(context)
        payload.update(metadata or {})
        payload.setdefault("event_kind", event_kind)
        if actor is not None:
            payload.setdefault("actor_unit_id", actor.unit_id)
            payload.setdefault("actor_side", actor.side)
            payload.setdefault("actor_position", actor.position)
            payload.setdefault("actor_hp_after", round(actor.current_hp, 2))
            payload.setdefault("actor_energy_after", int(actor.current_energy))
        if target is not None:
            payload.setdefault("target_unit_id", target.unit_id)
            payload.setdefault("target_side", target.side)
            payload.setdefault("target_position", target.position)
            payload.setdefault("target_hp_after", round(target.current_hp, 2))
            payload.setdefault("target_energy_after", int(target.current_energy))
        if hp_delta is not None:
            payload["hp_delta"] = round(hp_delta, 2)
        if energy_delta is not None:
            payload["energy_delta"] = round(energy_delta, 2)
        if status_delta is not None:
            payload["status_delta"] = status_delta
        return payload

    def _append_log(
        self,
        logs: list[BattleLogEntry],
        *,
        round_index: int,
        actor: BattleUnit | None,
        action: str,
        target: BattleUnit | None,
        value: float,
        event_kind: str,
        metadata: dict[str, Any] | None = None,
        hp_delta: float | None = None,
        energy_delta: float | None = None,
        status_delta: str | None = None,
        actor_name: str | None = None,
        target_name: str | None = None,
    ) -> None:
        logs.append(
            BattleLogEntry(
                round_index=round_index,
                actor=actor_name or (actor.name if actor is not None else "未知单位"),
                action=action,
                target=target_name or (target.name if target is not None else actor_name or "未知单位"),
                value=round(value, 2),
                metadata=self._build_log_metadata(
                    actor=actor,
                    target=target,
                    event_kind=event_kind,
                    metadata=metadata,
                    hp_delta=hp_delta,
                    energy_delta=energy_delta,
                    status_delta=status_delta,
                ),
            )
        )

    def create_units(self, heroes: list[HeroData], formation: dict[int, str], side: str) -> list[BattleUnit]:
        units: list[BattleUnit] = []
        for position, hero_ref in sorted(formation.items()):
            if not hero_ref:
                continue
            hero = self.hero_service.resolve_best_card(heroes, hero_ref)
            if hero is None:
                continue
            battle_hero = self.hero_service.prepare_hero_for_battle(hero)
            stats = self.hero_service.calculate_stats(battle_hero).final
            units.append(
                BattleUnit(
                    unit_id=f"{side}_{position}_{battle_hero.id}",
                    hero_id=battle_hero.id,
                    name=battle_hero.name,
                    camp=battle_hero.camp,
                    position=position,
                    stats=stats,
                    passive_skill_3=battle_hero.passive_skill_3,
                    passive_skills=list(battle_hero.passive_skills),
                    ultimate_skill=battle_hero.ultimate_skill,
                    current_hp=stats.hp,
                    max_hp=stats.hp,
                    current_energy=int(battle_hero.metadata.get("start_energy", 50)),
                    side=side,
                )
            )
        return units

    def run_battle(
        self,
        ally_heroes: list[HeroData],
        ally_formation: dict[int, str],
        enemy_heroes: list[HeroData],
        enemy_formation: dict[int, str],
        rewards: dict[str, int] | None = None,
    ) -> BattleResult:
        ally_units = self.create_units(ally_heroes, ally_formation, side="ally")
        enemy_units = self.create_units(enemy_heroes, enemy_formation, side="enemy")
        all_units = ally_units + enemy_units
        logs: list[BattleLogEntry] = []

        self._trigger_battle_start_passives(all_units, ally_units, enemy_units, logs)

        for round_index in range(1, self.MAX_ROUNDS + 1):
            for unit in all_units:
                unit.extra_turns_gained_this_round = 0
                unit.team_action_count_this_round = 0
                unit.team_action_triggers_this_round = 0
            self._process_pending_revives(all_units, logs, round_index)
            self._trigger_round_start_passives(all_units, ally_units, enemy_units, logs, round_index)
            if not any(unit.is_alive for unit in ally_units):
                return self._build_result("enemy", round_index, False, logs, ally_units, enemy_units, rewards)
            if not any(unit.is_alive for unit in enemy_units):
                return self._build_result("ally", round_index, False, logs, ally_units, enemy_units, rewards)
            order = self.turn_order_resolver.resolve(all_units)
            for actor in order:
                self._trigger_pre_action_status_reactions(actor, logs, round_index)
                if not actor.can_act():
                    continue
                allies = ally_units if actor.side == "ally" else enemy_units
                enemies = enemy_units if actor.side == "ally" else ally_units
                living_enemies = [unit for unit in enemies if unit.is_alive]
                if not living_enemies:
                    winner = actor.side
                    return self._build_result(winner, round_index - 1, False, logs, ally_units, enemy_units, rewards)

                self._trigger_actor_passives(actor, "行动前", ally_units, enemy_units, logs, round_index)
                if not actor.can_act():
                    continue

                while actor.can_act():
                    skill = self._select_action_skill(actor)
                    if skill is None:
                        break
                    if not self._execute_skill(actor, skill, allies, enemies, logs, round_index):
                        break
                    actor.last_skill_type = skill.skill_type
                    self._settle_energy_after_action(actor, skill)
                    self._trigger_passive_skill_3_after_basic_action(actor, skill, allies, enemies, logs, round_index)
                    self._trigger_actor_passives(actor, "行动后", ally_units, enemy_units, logs, round_index)
                    self._trigger_team_action_passives(actor, skill, ally_units, enemy_units, logs, round_index)
                    self._trigger_guo_jia_shadow_on_action(actor, ally_units, enemy_units, logs, round_index)
                    if not any(unit.is_alive for unit in enemies):
                        winner = actor.side
                        return self._build_result(winner, round_index, False, logs, ally_units, enemy_units, rewards)
                    if actor.extra_turns <= 0:
                        break
                    actor.extra_turns -= 1
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action="再行动",
                        target=actor,
                        value=actor.extra_turns,
                        event_kind="system",
                        metadata={"skill_type": "状态", "effect_type": "extra_turn"},
                        status_delta="extra_turn",
                    )
            self._tick_status_effects(all_units, logs, round_index)
            if not any(unit.is_alive for unit in ally_units):
                return self._build_result("enemy", round_index, False, logs, ally_units, enemy_units, rewards)
            if not any(unit.is_alive for unit in enemy_units):
                return self._build_result("ally", round_index, False, logs, ally_units, enemy_units, rewards)

        return self._build_result("enemy", self.MAX_ROUNDS, True, logs, ally_units, enemy_units, rewards)

    def _select_action_skill(self, actor: BattleUnit) -> SkillData | None:
        if actor.can_cast_skill() and actor.current_energy >= actor.ultimate_skill.energy_cost and not self._is_skill_blocked(actor, actor.ultimate_skill):
            return actor.ultimate_skill
        return self._resolve_turn_basic_attack_skill(actor)

    @staticmethod
    def _iter_passive_skill_slots(actor: BattleUnit) -> list[SkillData]:
        return [*actor.passive_skills, actor.passive_skill_3]

    @staticmethod
    def _passive_skill_3_mode(skill: SkillData) -> str:
        # 新配置统一使用 passive_skill_3_mode；旧 normal_slot_mode 仅保留读兼容。
        explicit_mode = str(skill.params.get("passive_skill_3_mode") or skill.params.get("normal_slot_mode", "")).strip()
        if explicit_mode:
            return explicit_mode
        if skill.trigger_timing in {"战斗开始", "回合开始"}:
            return "timed"
        if skill.params.get("reactive_trigger"):
            return "reactive"
        if skill.trigger_timing != "行动时自动":
            return "passive"
        if skill.params.get("basic_attack_fallback"):
            return "fallback"
        return "after_basic_attack"

    def _resolve_turn_basic_attack_skill(self, actor: BattleUnit) -> SkillData:
        return default_basic_attack_skill(actor.hero_id)

    def _skill_blocking_reasons(self, actor: BattleUnit, skill: SkillData) -> list[str]:
        blocked_tags = set(skill.params.get("blocked_by_tags", []))
        if skill.params.get("blocked_by_control"):
            blocked_tags.add(StatusTag.CONTROL.value)
        blocked_effect_types = set(skill.params.get("blocked_by_effect_types", []))
        reasons: set[str] = set()
        for effect in actor.status_effects:
            if effect.effect_type in blocked_effect_types:
                reasons.add(effect.effect_type)
            for tag in effect.tags:
                if tag in blocked_tags:
                    reasons.add(tag)
        return sorted(reasons)

    def _is_skill_blocked(self, actor: BattleUnit, skill: SkillData) -> bool:
        return bool(self._skill_blocking_reasons(actor, skill))

    def _trigger_battle_start_passives(
        self,
        all_units: list[BattleUnit],
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
    ) -> None:
        for actor in self.turn_order_resolver.resolve(all_units):
            self._trigger_actor_passives(actor, "战斗开始", ally_units, enemy_units, logs, round_index=0)
            self._trigger_battle_start_passive_skill_3(actor, ally_units, enemy_units, logs)
        self._trigger_cao_cao_guard_mode_for_team(ally_units, logs, round_index=0)
        self._trigger_cao_cao_guard_mode_for_team(enemy_units, logs, round_index=0)

    def _trigger_battle_start_passive_skill_3(
        self,
        actor: BattleUnit,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
    ) -> None:
        if not actor.is_alive or actor.passive_skill_3.trigger_timing != "战斗开始":
            return
        allies = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        self._execute_skill(actor, actor.passive_skill_3, allies, enemies, logs, round_index=0)

    def _trigger_round_start_passives(
        self,
        all_units: list[BattleUnit],
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        for actor in self.turn_order_resolver.resolve(all_units):
            self._trigger_actor_passives(actor, "回合开始", ally_units, enemy_units, logs, round_index)
            self._trigger_round_start_passive_skill_3(actor, ally_units, enemy_units, logs, round_index)
            self._trigger_round_start_ultimate_effects(actor, ally_units, enemy_units, logs, round_index)

    def _process_pending_revives(self, units: list[BattleUnit], logs: list[BattleLogEntry], round_index: int) -> None:
        living_lookup = {unit.unit_id: unit for unit in units if unit.is_alive}
        for unit in units:
            pending = next((effect for effect in unit.status_effects if effect.effect_type == "pending_revive"), None)
            if pending is None:
                continue
            if pending.duration > 1:
                pending.duration -= 1
                continue
            source = living_lookup.get(str(pending.params.get("source_unit_id", "")))
            heal_ratio = float(pending.params.get("heal_ratio", pending.value))
            scale = str(pending.params.get("heal_scale", "source_max_hp"))
            base_value = (source.max_hp if source is not None else unit.max_hp) if scale == "source_max_hp" else (source.stats.attack if source is not None else unit.stats.attack)
            heal_amount = max(1.0, base_value * heal_ratio)
            unit.current_hp = min(unit.max_hp, heal_amount)
            unit.status_effects = [effect for effect in unit.status_effects if effect is not pending]
            cooldown_rounds = int(pending.params.get("cooldown_rounds", 0))
            if cooldown_rounds > 0:
                unit.status_effects.append(
                    StatusEffect(
                        "revive_cooldown",
                        cooldown_rounds,
                        1.0,
                        str(pending.params.get("source_unit_id", unit.unit_id)),
                        category=get_status_category("revive_cooldown", 1.0).value,
                        tags=tuple(tag.value for tag in get_status_tags("revive_cooldown")),
                    )
                )
            self._append_log(
                logs,
                round_index=round_index,
                actor=source or unit,
                action=str(pending.params.get("action_name", "重整旗鼓")),
                target=unit,
                value=heal_amount,
                event_kind="heal",
                metadata={"skill_type": "被动", "effect_type": "pending_revive"},
                hp_delta=heal_amount,
            )

    def _trigger_pre_action_status_reactions(self, actor: BattleUnit, logs: list[BattleLogEntry], round_index: int) -> None:
        if not actor.is_alive:
            return
        for effect in actor.status_effects:
            if effect.effect_type != "wood_mark":
                continue
            control_chance = float(effect.params.get("attack_trigger_control_chance", 0.0))
            if control_chance <= 0 or self.random_service.roll() >= control_chance:
                continue
            self._apply_status_effect(
                actor,
                StatusEffect(
                    "stun",
                    1,
                    1.0,
                    effect.source_unit_id,
                    effect.source_skill_id,
                    category=get_status_category("stun", 1.0).value,
                    tags=tuple(tag.value for tag in get_status_tags("stun")),
                ),
                logs,
                round_index,
                actor_name=actor.name,
                skill_name="木之印记",
                skill_type="状态",
            )
            self._append_log(
                logs,
                round_index=round_index,
                actor=actor,
                action="木之印记缠绕",
                target=actor,
                value=1.0,
                event_kind="status",
                metadata={"skill_type": "状态", "effect_type": "wood_mark"},
                status_delta="wood_mark",
            )
            break

    def _trigger_round_start_passive_skill_3(
        self,
        actor: BattleUnit,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not actor.is_alive or actor.passive_skill_3.trigger_timing != "回合开始":
            return
        allies = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        if not any(unit.is_alive for unit in enemies):
            return
        self._execute_skill(actor, actor.passive_skill_3, allies, enemies, logs, round_index)

    def _trigger_round_start_ultimate_effects(
        self,
        actor: BattleUnit,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not actor.is_alive or not actor.ultimate_skill.round_start_effects:
            return
        allies = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        for effect in actor.ultimate_skill.round_start_effects:
            target_scope = effect.params.get("target_scope")
            if target_scope == "enemies" or effect.effect_type == "percent_hp_damage":
                for target in [unit for unit in enemies if unit.is_alive]:
                    self._apply_single_effect(actor, target, actor.ultimate_skill, effect, logs, round_index, allies=allies, enemies=enemies)
                continue
            self._apply_single_effect(actor, actor, actor.ultimate_skill, effect, logs, round_index, allies=allies, enemies=enemies)

    def _trigger_actor_passives(
        self,
        actor: BattleUnit,
        timing: str,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not actor.is_alive:
            return
        allies = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        skills_to_check = [skill for skill in actor.passive_skills if skill.trigger_timing == timing]
        passive_skill_3 = actor.passive_skill_3
        if passive_skill_3.trigger_timing == timing and timing not in {"行动时自动", "回合开始", "战斗开始"}:
            skills_to_check.append(passive_skill_3)
        if passive_skill_3.params.get("reactive_trigger") == timing and passive_skill_3 not in skills_to_check:
            skills_to_check.append(passive_skill_3)
        for skill in skills_to_check:
            if skill.trigger_timing not in {timing, "被动"} and skill is not actor.passive_skill_3:
                continue
            required_last_skill_type = skill.params.get("requires_last_skill_type")
            if required_last_skill_type and actor.last_skill_type != required_last_skill_type:
                continue
            self._execute_skill(actor, skill, allies, enemies, logs, round_index)

    @staticmethod
    def _iter_reactive_skills(actor: BattleUnit, trigger: str) -> list[SkillData]:
        skills = list(actor.passive_skills)
        passive_skill_3 = actor.passive_skill_3
        passive_skill_3_trigger = str(passive_skill_3.params.get("reactive_trigger", ""))
        if passive_skill_3.trigger_timing == trigger or passive_skill_3_trigger == trigger:
            skills.append(passive_skill_3)
        return skills

    def _trigger_passive_skill_3_after_basic_action(
        self,
        actor: BattleUnit,
        action_skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not actor.is_alive or action_skill.skill_type != "普攻":
            return
        passive_skill_3 = actor.passive_skill_3
        if passive_skill_3.trigger_timing != "行动时自动":
            return
        if self._passive_skill_3_mode(passive_skill_3) != "after_basic_attack":
            return
        self._execute_skill(actor, passive_skill_3, allies, enemies, logs, round_index)

    @staticmethod
    def _clone_skill(skill: SkillData, *, skill_type: str | None = None, name: str | None = None) -> SkillData:
        return SkillData(
            skill_id=skill.skill_id,
            name=name or skill.name,
            skill_type=skill_type or skill.skill_type,
            target_type=skill.target_type,
            damage_coefficient=skill.damage_coefficient,
            target_side=skill.target_side,
            trigger_timing=skill.trigger_timing,
            energy_cost=skill.energy_cost,
            hit_count=skill.hit_count,
            retarget_per_hit=skill.retarget_per_hit,
            level=skill.level,
            effects=[deepcopy(effect) for effect in skill.effects],
            params=deepcopy(skill.params),
            damage_by_level=dict(skill.damage_by_level),
            hit_count_by_level=dict(skill.hit_count_by_level),
            effects_by_level={level: [deepcopy(effect) for effect in effects] for level, effects in skill.effects_by_level.items()},
            round_start_effects=[deepcopy(effect) for effect in skill.round_start_effects],
            round_start_effects_by_level={level: [deepcopy(effect) for effect in effects] for level, effects in skill.round_start_effects_by_level.items()},
        )

    def _select_units_from_pool(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        pool: list[BattleUnit],
        *,
        selection: str,
        count: int,
        row_filter: str | None = None,
        exclude_actor: bool = False,
    ) -> list[BattleUnit]:
        filtered = [unit for unit in pool if unit.is_alive]
        if exclude_actor:
            filtered = [unit for unit in filtered if unit.unit_id != actor.unit_id]
        if row_filter == "frontline":
            filtered = [unit for unit in filtered if unit.position <= 3]
        elif row_filter == "backline":
            filtered = [unit for unit in filtered if unit.position >= 4]
        elif row_filter == "same_row":
            filtered = [unit for unit in filtered if (unit.position <= 3) == (actor.position <= 3)]
        if not filtered:
            return []
        normalized_count = max(1, min(count, len(filtered)))
        if selection == "highest_attack":
            ordered = sorted(filtered, key=lambda unit: (unit.stats.attack, -unit.position), reverse=True)
            return ordered[:normalized_count]
        if selection == "lowest_hp":
            return sorted(filtered, key=lambda unit: (unit.current_hp, unit.position))[:normalized_count]
        if selection == "current_target":
            return [target] if target in filtered else ([filtered[0]] if filtered else [])
        if selection == "self":
            return [actor] if actor in filtered else ([filtered[0]] if filtered else [])
        if selection == "random":
            return self._pick_random_targets(filtered, normalized_count)
        return filtered[:normalized_count]

    def _build_follow_up_attack_skill(
        self,
        actor: BattleUnit,
        *,
        name: str,
        damage_coefficient: float,
        target_type: str,
        effects: list[SkillEffectData] | None = None,
        params: dict[str, Any] | None = None,
    ) -> SkillData:
        return SkillData(
            skill_id=f"{actor.hero_id}_{name}_follow_up",
            name=name,
            skill_type="追击",
            target_type=target_type,
            damage_coefficient=damage_coefficient,
            target_side="enemy",
            effects=[deepcopy(effect) for effect in (effects or [])],
            params=deepcopy(params or {}),
        )

    def _resolve_targets(
        self,
        actor: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
    ) -> list[BattleUnit]:
        if skill.target_side == "self":
            return [actor] if actor.is_alive else []
        pool = [unit for unit in (allies if skill.target_side == "ally" else enemies) if unit.is_alive]
        if skill.target_side == "enemy":
            targetable_pool = self._filter_targetable_units(pool)
            if targetable_pool:
                pool = targetable_pool
            taunt_target = self._resolve_taunt_target(actor, enemies)
            if taunt_target is not None:
                return [taunt_target]
        return self._select_targets(skill.target_type, pool, actor)

    @staticmethod
    def _filter_targetable_units(units: list[BattleUnit]) -> list[BattleUnit]:
        targetable = [unit for unit in units if not any(effect.effect_type == "untargetable" for effect in unit.status_effects)]
        return targetable or units

    def _resolve_taunt_target(self, actor: BattleUnit, enemies: list[BattleUnit]) -> BattleUnit | None:
        taunt_effects = [effect for effect in actor.status_effects if effect.effect_type == "taunt"]
        for effect in taunt_effects:
            taunter = next((unit for unit in enemies if unit.unit_id == effect.source_unit_id and unit.is_alive), None)
            if taunter is not None:
                return taunter
        return None

    def _select_targets(self, target_type: str, units: list[BattleUnit], actor: BattleUnit | None = None) -> list[BattleUnit]:
        if target_type == "自身" and actor and actor.is_alive:
            return [actor]
        if not units:
            return []
        if target_type == "同列首个" and actor:
            column = self._column_index(actor.position)
            same_column = sorted((unit for unit in units if self._column_index(unit.position) == column), key=lambda unit: unit.position)
            if same_column:
                return [same_column[0]]
            return [sorted(units, key=lambda unit: unit.position)[0]]
        if target_type == "随机单体":
            return [self.random_service.choice(units)]
        if target_type.startswith("随机") and target_type.endswith("人"):
            count_text = target_type.removeprefix("随机").removesuffix("人")
            if count_text.isdigit():
                return self._pick_random_targets(units, int(count_text))
        if target_type.startswith("前排随机") and target_type.endswith("名"):
            count_text = target_type.removeprefix("前排随机").removesuffix("名")
            frontline = [unit for unit in units if unit.position <= 3]
            pool = frontline or units
            if count_text.isdigit():
                return self._pick_random_targets(pool, int(count_text))
        if target_type == "全体":
            return units
        if target_type == "前排":
            frontline = [unit for unit in units if unit.position <= 3]
            return frontline or units[:1]
        if target_type == "后排":
            backline = [unit for unit in units if unit.position >= 4]
            return backline or units[:1]
        if target_type == "后排3名":
            backline = [unit for unit in units if unit.position >= 4]
            ordered = sorted(backline or units, key=lambda unit: unit.position)
            return ordered[:3]
        if target_type == "同排友军" and actor:
            same_row = [unit for unit in units if (unit.position <= 3) == (actor.position <= 3)]
            return same_row or units
        if target_type == "血量最低":
            return [min(units, key=lambda unit: (unit.current_hp, unit.position))]
        if target_type == "血量最低2名":
            return sorted(units, key=lambda unit: (unit.current_hp, unit.position))[:2]
        if target_type == "生命百分比最低":
            return [min(units, key=lambda unit: ((unit.current_hp / unit.max_hp) if unit.max_hp > 0 else 0.0, unit.position))]
        if target_type == "生命百分比最低2名":
            return sorted(units, key=lambda unit: ((unit.current_hp / unit.max_hp) if unit.max_hp > 0 else 0.0, unit.position))[:2]
        if target_type == "血量最高":
            return [max(units, key=lambda unit: (unit.current_hp, -unit.position))]
        return [units[0]]

    def _pick_random_targets(self, units: list[BattleUnit], count: int) -> list[BattleUnit]:
        count = max(1, min(count, len(units)))
        pool = list(units)
        result: list[BattleUnit] = []
        while pool and len(result) < count:
            picked = self.random_service.choice(pool)
            result.append(picked)
            pool.remove(picked)
        return result

    @staticmethod
    def _column_index(position: int) -> int:
        return ((position - 1) % 3) + 1

    @staticmethod
    def _frontline_position_for(position: int) -> int:
        return ((position - 1) % 3) + 1

    def _is_conditional_random_frontline_mode(self, skill: SkillData, enemies: list[BattleUnit]) -> bool:
        minimum_frontline = skill.params.get("convert_to_random_hits_if_frontline_below")
        if minimum_frontline is None:
            return False
        activation_level = int(skill.params.get("convert_to_random_hits_activation_level", 4))
        if skill.level < activation_level:
            return False
        frontline = [unit for unit in enemies if unit.is_alive and unit.position <= 3]
        return len(frontline) < int(minimum_frontline)

    def _resolve_skill_hit_count(self, actor: BattleUnit, skill: SkillData, enemies: list[BattleUnit]) -> int:
        hit_count = skill.hit_count
        if self._is_conditional_random_frontline_mode(skill, enemies):
            hit_count = int(skill.params.get("converted_hit_count", hit_count))
        bonus_stack_name = skill.params.get("bonus_hit_count_from_status")
        if bonus_stack_name:
            hit_count += int(actor._status_total(str(bonus_stack_name)))
        return max(1, hit_count)

    def _execute_skill(
        self,
        actor: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> bool:
        blocking_reasons = self._skill_blocking_reasons(actor, skill)
        if blocking_reasons:
            self._append_log(
                logs,
                round_index=round_index,
                actor=actor,
                action=f"{skill.name}受控未释放",
                target=actor,
                value=0.0,
                event_kind="blocked",
                metadata={"skill_type": skill.skill_type, "blocked": True, "blocked_by": blocking_reasons},
            )
            return False
        locked_targets = self._resolve_targets(actor, skill, allies, enemies)
        if not locked_targets:
            return False
        resolved_targets: list[BattleUnit] = []
        resolved_target_ids: set[str] = set()
        total_hits = self._resolve_skill_hit_count(actor, skill, enemies)
        self._push_log_context(self._build_cast_log_context(actor, skill, locked_targets))
        try:
            for hit_index in range(1, total_hits + 1):
                targets = self._resolve_targets_for_hit(actor, skill, allies, enemies, locked_targets)
                if not targets:
                    break
                first_target = targets[0]
                self._push_log_context({"cast_hit_index": hit_index, "cast_total_hits": total_hits})
                try:
                    for target in targets:
                        if target.unit_id not in resolved_target_ids:
                            resolved_target_ids.add(target.unit_id)
                            resolved_targets.append(target)
                        self._apply_skill_hit(
                            actor,
                            target,
                            skill,
                            allies,
                            enemies,
                            logs,
                            round_index,
                            hit_index=hit_index,
                            total_hits=total_hits,
                            apply_effects=(bool(skill.params.get("apply_effects_each_hit")) or hit_index == total_hits)
                            and (not bool(skill.params.get("apply_effects_on_first_target_only")) or target is first_target),
                        )
                finally:
                    self._pop_log_context()
                if skill.retarget_per_hit:
                    locked_targets = []
            self._handle_after_skill_resolution(actor, skill, resolved_targets, allies, enemies, logs, round_index)
        finally:
            self._pop_log_context()
        return True

    def _handle_after_skill_resolution(
        self,
        actor: BattleUnit,
        skill: SkillData,
        resolved_targets: list[BattleUnit],
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        skill_tags = set(skill.params.get("skill_tags", []))
        self._trigger_energy_gain_passives(actor, skill_tags, logs, round_index, source_skill_name=skill.name)
        self._trigger_conditional_after_skill_effects(actor, skill, resolved_targets, allies, enemies, logs, round_index)
        self._trigger_cao_cao_after_skill_resolution(actor, skill, resolved_targets, allies, logs, round_index)
        self._apply_status_on_skill_targets(actor, skill, resolved_targets, logs, round_index)
        self._apply_post_cast_random_statuses(actor, skill, allies, enemies, logs, round_index)
        consume_status_name = skill.params.get("consume_status_on_cast")
        if consume_status_name:
            self._consume_status_by_effect_type(actor, str(consume_status_name), logs, round_index, actor_name=actor.name, skill_name=skill.name, skill_type=skill.skill_type)

    def _trigger_conditional_after_skill_effects(
        self,
        actor: BattleUnit,
        skill: SkillData,
        resolved_targets: list[BattleUnit],
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not resolved_targets:
            return
        first_target = resolved_targets[0]
        for effect in skill.effects:
            if effect.effect_type != "backline_burst_if_first_target_backline" or first_target.position < 4:
                continue
            backline_targets = [unit for unit in enemies if unit.is_alive and unit.position >= 4]
            for target in backline_targets:
                actual_damage, absorbed, blocked_by_invincible = self._apply_damage(
                    actor,
                    target,
                    actor.stats.attack * effect.value,
                    logs,
                    round_index,
                    skill_name=effect.params.get("action_name", effect.effect_type),
                    skill_type="追击",
                    allies=allies,
                    opponents=enemies,
                )
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action=str(effect.params.get("action_name", "战意爆发")),
                    target=target,
                    value=actual_damage,
                    event_kind="damage",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible},
                    hp_delta=-actual_damage,
                    energy_delta=10 if actual_damage > 0 else 0.0,
                )

    def _consume_status_by_effect_type(
        self,
        target: BattleUnit,
        effect_type: str,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        actor_name: str,
        skill_name: str,
        skill_type: str,
    ) -> None:
        removed = [effect for effect in target.status_effects if effect.effect_type == effect_type]
        if not removed:
            return
        target.status_effects = [effect for effect in target.status_effects if effect.effect_type != effect_type]
        self._append_log(
            logs,
            round_index=round_index,
            actor=None,
            action=f"消耗{effect_type}",
            target=target,
            value=sum(effect.value for effect in removed),
            event_kind="status",
            metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": effect_type, "removed": True},
            status_delta=effect_type,
            actor_name=actor_name,
        )

    def _trigger_energy_gain_passives(
        self,
        actor: BattleUnit,
        skill_tags: set[str],
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        source_skill_name: str,
    ) -> None:
        if not actor.is_alive or not skill_tags:
            return
        for passive in self._iter_passive_skill_slots(actor):
            for effect in passive.effects:
                if effect.effect_type != "gain_energy_on_skill_tag":
                    continue
                required_tag = effect.params.get("required_skill_tag")
                if required_tag and required_tag not in skill_tags:
                    continue
                before = actor.current_energy
                actor.current_energy = min(actor.max_energy, actor.current_energy + int(effect.value))
                restored = actor.current_energy - before
                if restored > 0:
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action="能量恢复",
                        target=actor,
                        value=restored,
                        event_kind="energy",
                        metadata={"source_skill": passive.name, "skill_type": passive.skill_type, "triggered_by_skill": source_skill_name, "effect_type": effect.effect_type},
                        energy_delta=restored,
                    )

    def _apply_status_on_skill_targets(
        self,
        actor: BattleUnit,
        skill: SkillData,
        resolved_targets: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not resolved_targets:
            return
        skill_tags = set(skill.params.get("skill_tags", []))
        for passive in self._iter_passive_skill_slots(actor):
            for effect in passive.effects:
                if effect.effect_type != "apply_status_on_skill_targets":
                    continue
                required_skill_id = effect.params.get("required_skill_id")
                required_skill_type = effect.params.get("required_skill_type")
                required_skill_tag = effect.params.get("required_skill_tag")
                if required_skill_id and skill.skill_id != required_skill_id:
                    continue
                if required_skill_type and skill.skill_type != required_skill_type:
                    continue
                if required_skill_tag and required_skill_tag not in skill_tags:
                    continue
                status_effect_type = effect.params.get("status_effect_type")
                if not status_effect_type:
                    continue
                status_value = float(effect.params.get("status_value", effect.value))
                status_duration = int(effect.params.get("status_duration", effect.duration))
                status_params = dict(effect.params.get("status_params", {}))
                guaranteed_first_target = bool(effect.params.get("guaranteed_first_target", False))
                for index, target in enumerate(resolved_targets):
                    if not target.is_alive:
                        continue
                    chance = 1.0 if guaranteed_first_target and index == 0 else effect.chance
                    proxy_effect = SkillEffectData(
                        effect_type=status_effect_type,
                        value=status_value,
                        duration=status_duration,
                        chance=chance,
                        params={"applied_status": status_effect_type},
                    )
                    if chance < 1.0 and self.random_service.roll() >= chance:
                        continue
                    if not self._effect_hits(actor, target, proxy_effect, skill):
                        self._append_log(
                            logs,
                            round_index=round_index,
                            actor=actor,
                            action=f"{status_effect_type}被抵抗",
                            target=target,
                            value=0.0,
                            event_kind="status",
                            metadata={"source_skill": passive.name, "skill_type": passive.skill_type, "effect_type": status_effect_type, "resisted": True},
                            status_delta=status_effect_type,
                        )
                        continue
                    status_effect = self._build_status_effect(actor, skill, status_effect_type, status_duration, status_value, status_params)
                    self._apply_status_effect(target, status_effect, logs, round_index, actor.name, passive.name, passive.skill_type)

    def _apply_post_cast_random_statuses(
        self,
        actor: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        for effect in skill.effects:
            if effect.effect_type != "apply_random_status_to_side":
                continue
            target_side = effect.params.get("target_side", "enemy")
            target_pool = allies if target_side == "ally" else enemies
            alive_pool = [unit for unit in target_pool if unit.is_alive]
            if not alive_pool:
                continue
            status_effect_type = effect.params.get("status_effect_type")
            if not status_effect_type:
                continue
            count = max(1, int(effect.params.get("count", 1)))
            status_value = float(effect.params.get("status_value", effect.value))
            status_duration = int(effect.params.get("status_duration", effect.duration))
            status_params = dict(effect.params.get("status_params", {}))
            for target in self._pick_random_targets(alive_pool, count):
                proxy_effect = SkillEffectData(
                    effect_type=status_effect_type,
                    value=status_value,
                    duration=status_duration,
                    chance=effect.chance,
                    params={"applied_status": status_effect_type},
                )
                if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                    continue
                if not self._effect_hits(actor, target, proxy_effect, skill):
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action=f"{status_effect_type}被抵抗",
                        target=target,
                        value=0.0,
                        event_kind="status",
                        metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": status_effect_type, "resisted": True},
                        status_delta=status_effect_type,
                    )
                    continue
                status_effect = self._build_status_effect(actor, skill, status_effect_type, status_duration, status_value, status_params)
                self._apply_status_effect(target, status_effect, logs, round_index, actor.name, skill.name, skill.skill_type)

    def _resolve_targets_for_hit(
        self,
        actor: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        locked_targets: list[BattleUnit],
    ) -> list[BattleUnit]:
        if self._is_conditional_random_frontline_mode(skill, enemies):
            frontline = [unit for unit in self._filter_targetable_units(enemies) if unit.is_alive and unit.position <= 3]
            pool = frontline or self._filter_targetable_units([unit for unit in enemies if unit.is_alive])
            if not pool:
                return []
            return [self.random_service.choice(pool)]
        alive_locked_targets = [target for target in locked_targets if target.is_alive]
        if skill.retarget_per_hit or not alive_locked_targets:
            return self._resolve_targets(actor, skill, allies, enemies)
        return alive_locked_targets

    def _apply_skill_hit(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        hit_index: int = 1,
        total_hits: int = 1,
        apply_effects: bool = True,
    ) -> None:
        actual_damage = 0.0
        critical = False
        counter_bonus = 0.0
        absorbed = 0.0
        blocked_by_invincible = False
        target_was_alive = target.is_alive
        if skill.damage_coefficient > 0 and skill.target_side == "enemy":
            damage, critical, counter_bonus = self.damage_calculator.calculate(actor, target, skill)
            actual_damage, absorbed, blocked_by_invincible = self._apply_damage(
                actor,
                target,
                damage,
                logs,
                round_index,
                skill_name=skill.name,
                skill_type=skill.skill_type,
                allies=allies,
                opponents=enemies,
                invincible_pierce_ratio=float(skill.params.get("invincible_pierce_ratio", 0.0)),
            )
            if target_was_alive and not target.is_alive and actual_damage > 0:
                self._handle_kill_triggers(actor, skill, target, logs, round_index, allies=allies, enemies=enemies)
            if critical and actual_damage > 0 and not bool(skill.params.get("disable_mark_critical_trigger")):
                self._trigger_critical_mark_burst(actor, target, skill, allies, enemies, logs, round_index)
        self._append_log(
            logs,
            round_index=round_index,
            actor=actor,
            action=skill.name,
            target=target,
            value=actual_damage,
            event_kind="damage" if actual_damage > 0 else "skill",
            metadata={
                "skill_type": skill.skill_type,
                "target_side": skill.target_side,
                "critical": critical,
                "counter_bonus": counter_bonus,
                "absorbed": round(absorbed, 2),
                "invincible": blocked_by_invincible,
                "hit_index": hit_index,
                "total_hits": total_hits,
                "skill_id": skill.skill_id,
            },
            hp_delta=-actual_damage if actual_damage > 0 else 0.0,
            energy_delta=10 if actual_damage > 0 and skill.target_side == "enemy" else 0.0,
        )
        if blocked_by_invincible:
            self._append_log(
                logs,
                round_index=round_index,
                actor=target,
                action="无敌免伤",
                target=target,
                value=0.0,
                event_kind="status",
                metadata={"skill_type": "状态", "effect_type": "invincible"},
                status_delta="invincible",
            )
        if apply_effects:
            self._apply_skill_effects(actor, target, skill, logs, round_index, allies=allies, enemies=enemies)
        if actual_damage > 0 and skill.target_side == "enemy":
            self._trigger_reactive_marks(actor, target, allies, enemies, logs, round_index)

    def _trigger_critical_mark_burst(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        skill: SkillData,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if bool(skill.params.get("disable_mark_bonus")):
            return
        mark = next((effect for effect in target.status_effects if effect.effect_type == "guan_yu_wu_sheng_mark"), None)
        if mark is None:
            return
        source_attack = float(mark.params.get("source_attack", actor.stats.attack))
        bonus_ratio = float(mark.params.get("critical_bonus_ratio", mark.value))
        actual_damage, absorbed, blocked_by_invincible = self._apply_damage(
            actor,
            target,
            source_attack * bonus_ratio,
            logs,
            round_index,
            skill_name="武圣印记",
            skill_type="印记",
            allies=allies,
            opponents=enemies,
        )
        self._append_log(
            logs,
            round_index=round_index,
            actor=actor,
            action="武圣印记",
            target=target,
            value=actual_damage,
            event_kind="damage",
            metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": "guan_yu_wu_sheng_mark", "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible},
            hp_delta=-actual_damage,
            energy_delta=10 if actual_damage > 0 else 0.0,
        )

    def _settle_energy_after_action(self, actor: BattleUnit, skill: SkillData) -> None:
        if skill.energy_cost > 0 and actor.current_energy >= skill.energy_cost:
            actor.current_energy = 0
            return
        if skill.skill_type == "普攻":
            actor.current_energy = min(actor.max_energy, actor.current_energy + 20)

    @staticmethod
    def _has_status(target: BattleUnit, effect_type: str) -> bool:
        return any(effect.effect_type == effect_type for effect in target.status_effects)

    def _build_status_effect(
        self,
        actor: BattleUnit,
        skill: SkillData,
        effect_type: str,
        duration: int,
        value: float,
        params: dict[str, Any] | None = None,
    ) -> StatusEffect:
        merged_params = dict(params or {})
        merged_params.setdefault("source_attack", actor.stats.attack)
        return StatusEffect(
            effect_type=effect_type,
            duration=duration,
            value=value,
            source_unit_id=actor.unit_id,
            source_skill_id=skill.skill_id,
            category=get_status_category(effect_type, value).value,
            tags=tuple(tag.value for tag in get_status_tags(effect_type)),
            params=merged_params,
        )

    def _consume_shield(self, target: BattleUnit, damage: float) -> float:
        remaining_damage = max(0.0, damage)
        absorbed = 0.0
        next_effects: list[StatusEffect] = []
        for effect in target.status_effects:
            if effect.effect_type != "shield":
                next_effects.append(effect)
                continue
            if remaining_damage <= 0:
                next_effects.append(effect)
                continue
            blocked = min(effect.value, remaining_damage)
            absorbed += blocked
            remaining_damage -= blocked
            left = effect.value - blocked
            if left > 1e-6:
                next_effects.append(
                    StatusEffect(
                        effect.effect_type,
                        effect.duration,
                        left,
                        effect.source_unit_id,
                        effect.source_skill_id,
                        effect.category,
                        effect.tags,
                        dict(effect.params),
                    )
                )
        target.status_effects = next_effects
        return absorbed

    def _status_matches_filter(self, effect: StatusEffect, status_filter: str | None) -> bool:
        if not status_filter:
            return True
        if status_filter == "buff":
            return effect.category == StatusCategory.BUFF.value
        if status_filter == "debuff":
            return effect.category == StatusCategory.DEBUFF.value
        if status_filter == "control":
            return StatusTag.CONTROL.value in effect.tags
        if status_filter == "damage_over_time":
            return StatusTag.DAMAGE_OVER_TIME.value in effect.tags
        if status_filter == "attribute":
            return StatusTag.ATTRIBUTE.value in effect.tags
        if status_filter == "protect":
            return StatusTag.PROTECT.value in effect.tags
        if status_filter == "special":
            return StatusTag.SPECIAL.value in effect.tags
        return effect.effect_type == status_filter

    def _clear_status_effects(
        self,
        target: BattleUnit,
        *,
        status_filter: str | None,
        count: int,
        actor_name: str,
        skill_name: str,
        skill_type: str,
        round_index: int,
        logs: list[BattleLogEntry],
        source_unit_id: str | None = None,
    ) -> list[StatusEffect]:
        removed: list[StatusEffect] = []
        next_effects: list[StatusEffect] = []
        for effect in target.status_effects:
            if len(removed) >= count:
                next_effects.append(effect)
                continue
            if source_unit_id is not None and effect.source_unit_id != source_unit_id:
                next_effects.append(effect)
                continue
            if not self._status_matches_filter(effect, status_filter):
                next_effects.append(effect)
                continue
            removed.append(effect)
            self._append_log(
                logs,
                round_index=round_index,
                actor=None,
                action=f"清除{effect.effect_type}",
                target=target,
                value=effect.value,
                event_kind="status",
                metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": effect.effect_type, "removed": True},
                status_delta=effect.effect_type,
                actor_name=actor_name,
            )
        target.status_effects = next_effects
        return removed

    def _effect_hits(self, actor: BattleUnit, target: BattleUnit, effect: SkillEffectData, skill: SkillData) -> bool:
        effect_type = str(effect.params.get("applied_status", effect.effect_type))
        harmful = effect_type in self.HARMFUL_EFFECTS or get_status_category(effect_type, effect.value) == StatusCategory.DEBUFF
        if not harmful:
            return True
        if effect_type in {"stun", "silence", "freeze", "taunt"} and self._has_status(target, "control_immunity"):
            return False
        hit_rate = MathUtils.clamp(1.0 + actor.stats.effect_hit - target.stats.effect_resist, 0.0, 1.0)
        if hit_rate >= 1.0:
            return True
        if hit_rate <= 0.0:
            return False
        return self.random_service.roll() < hit_rate

    def _apply_status_effect(
        self,
        target: BattleUnit,
        status_effect: StatusEffect,
        logs: list[BattleLogEntry],
        round_index: int,
        actor_name: str,
        skill_name: str,
        skill_type: str,
    ) -> None:
        same_type = [effect for effect in target.status_effects if effect.effect_type == status_effect.effect_type]
        if status_effect.effect_type == "shield":
            target.status_effects.append(status_effect)
            self._append_log(
                logs,
                round_index=round_index,
                actor=None,
                action="shield生效",
                target=target,
                value=status_effect.value,
                event_kind="status",
                metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": status_effect.effect_type},
                status_delta=status_effect.effect_type,
                actor_name=actor_name,
            )
            return
        if status_effect.effect_type in self.REFRESHABLE_EFFECTS and same_type:
            kept: list[StatusEffect] = []
            replaced = False
            for effect in target.status_effects:
                if effect.effect_type == status_effect.effect_type and not replaced:
                    kept.append(status_effect)
                    replaced = True
                elif effect.effect_type != status_effect.effect_type:
                    kept.append(effect)
            target.status_effects = kept
            self._append_log(
                logs,
                round_index=round_index,
                actor=None,
                action=f"{status_effect.effect_type}刷新",
                target=target,
                value=status_effect.value,
                event_kind="status",
                metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": status_effect.effect_type},
                status_delta=status_effect.effect_type,
                actor_name=actor_name,
            )
            return
        if status_effect.effect_type in self.OVERRIDABLE_EFFECTS and same_type:
            strongest = max(same_type, key=lambda item: abs(item.value))
            if abs(status_effect.value) < abs(strongest.value):
                return
            target.status_effects = [effect for effect in target.status_effects if effect is not strongest]
            target.status_effects.append(status_effect)
            self._append_log(
                logs,
                round_index=round_index,
                actor=None,
                action=f"{status_effect.effect_type}覆盖",
                target=target,
                value=status_effect.value,
                event_kind="status",
                metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": status_effect.effect_type},
                status_delta=status_effect.effect_type,
                actor_name=actor_name,
            )
            return
        if status_effect.effect_type == "survive_once" and same_type:
            target.status_effects = [effect for effect in target.status_effects if effect.effect_type != "survive_once"]
        target.status_effects.append(status_effect)
        self._append_log(
            logs,
            round_index=round_index,
            actor=None,
            action=f"{status_effect.effect_type}生效",
            target=target,
            value=status_effect.value,
            event_kind="status",
            metadata={"source_skill": skill_name, "skill_type": skill_type, "effect_type": status_effect.effect_type},
            status_delta=status_effect.effect_type,
            actor_name=actor_name,
        )

    def _grant_stack_status(
        self,
        target: BattleUnit,
        *,
        actor: BattleUnit,
        skill: SkillData,
        effect_type: str,
        amount: float,
        duration: int,
        max_stacks: float | None = None,
        logs: list[BattleLogEntry],
        round_index: int,
        actor_name: str,
        action_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        existing = next((effect for effect in target.status_effects if effect.effect_type == effect_type), None)
        if existing is None:
            status_effect = self._build_status_effect(actor, skill, effect_type, duration, amount, params or {})
            target.status_effects.append(status_effect)
            self._append_log(
                logs,
                round_index=round_index,
                actor=actor,
                action=action_name,
                target=target,
                value=status_effect.value,
                event_kind="status",
                metadata={"skill_type": skill.skill_type, "effect_type": effect_type, "source_skill": skill.name},
                status_delta=effect_type,
                actor_name=actor_name,
            )
            return
        old_value = existing.value
        old_duration = existing.duration
        old_params = dict(existing.params)
        existing.value += amount
        if max_stacks is not None:
            existing.value = min(existing.value, max_stacks)
        if duration >= 0:
            existing.duration = max(existing.duration, duration)
        existing.params.update(params or {})
        if abs(existing.value - old_value) < 1e-9 and existing.duration == old_duration and existing.params == old_params:
            return
        self._append_log(
            logs,
            round_index=round_index,
            actor=actor,
            action=action_name,
            target=target,
            value=existing.value,
            event_kind="status",
            metadata={"skill_type": skill.skill_type, "effect_type": effect_type, "source_skill": skill.name},
            status_delta=effect_type,
            actor_name=actor_name,
        )

    def _resolve_damage_share_link(
        self,
        target: BattleUnit,
        actor: BattleUnit,
        allies: list[BattleUnit] | None,
        opponents: list[BattleUnit] | None,
    ) -> tuple[StatusEffect | None, BattleUnit | None]:
        team = (allies if target.side == actor.side else opponents) or []
        for effect in target.status_effects:
            if effect.effect_type != "damage_share":
                continue
            protector_id = effect.params.get("link_unit_id")
            protector = next((unit for unit in team if unit.unit_id == protector_id and unit.is_alive), None)
            if protector is not None:
                return effect, protector
        return None, None

    def _trigger_survive_once(
        self,
        target: BattleUnit,
        survive_effect: StatusEffect,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        allies: list[BattleUnit] | None,
    ) -> None:
        params = dict(survive_effect.params)
        trigger_skill = SkillData("survive_once", "绝境续命", "状态", "自身", 0.0, target_side="self")
        invincible_duration = int(params.get("invincible_duration", 0))
        untargetable_duration = int(params.get("untargetable_duration", 0))
        shield_ratio = float(params.get("shield_ratio", 0.0))
        heal_attack_ratio = float(params.get("heal_attack_ratio", 0.0))
        used_marker = params.get("used_marker_effect_type")
        if invincible_duration > 0:
            self._apply_status_effect(target, self._build_status_effect(target, trigger_skill, "invincible", invincible_duration, 1.0, {}), logs, round_index, target.name, "绝境续命", "状态")
        alive_allies = [unit for unit in (allies or []) if unit.is_alive]
        if untargetable_duration > 0 and len(alive_allies) > 1:
            self._apply_status_effect(target, self._build_status_effect(target, trigger_skill, "untargetable", untargetable_duration, 1.0, {}), logs, round_index, target.name, "绝境续命", "状态")
        if shield_ratio > 0:
            self._apply_status_effect(target, self._build_status_effect(target, trigger_skill, "shield", invincible_duration or 1, target.stats.attack * shield_ratio, {}), logs, round_index, target.name, "绝境续命", "状态")
        if heal_attack_ratio > 0:
            target.current_hp = min(target.max_hp, target.current_hp + target.stats.attack * heal_attack_ratio)
        if used_marker:
            self._apply_status_effect(target, self._build_status_effect(target, trigger_skill, str(used_marker), -1, 1.0, {}), logs, round_index, target.name, "绝境续命", "状态")
        self._append_log(
            logs,
            round_index=round_index,
            actor=target,
            action="绝境续命",
            target=target,
            value=target.current_hp,
            event_kind="status",
            metadata={"skill_type": "状态", "effect_type": "survive_once"},
            hp_delta=0.0,
            status_delta="survive_once",
        )

    def _trigger_hp_threshold_passives(
        self,
        target: BattleUnit,
        attacker: BattleUnit,
        remaining_hp: float,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        target_allies: list[BattleUnit],
        target_enemies: list[BattleUnit],
    ) -> None:
        current_ratio = (max(0.0, remaining_hp) / target.max_hp) if target.max_hp > 0 else 0.0
        for reactive_skill in self._iter_reactive_skills(target, "生命降低后"):
            for effect in reactive_skill.effects:
                if effect.effect_type == "retreat_on_low_hp_once":
                    threshold = float(effect.params.get("hp_threshold", 0.0))
                    marker = str(effect.params.get("used_marker", "retreat_on_low_hp_once_used"))
                    if remaining_hp <= 0 or current_ratio > threshold or self._has_status(target, marker):
                        continue
                    target.status_effects.append(
                        StatusEffect(
                            marker,
                            -1,
                            1.0,
                            target.unit_id,
                            reactive_skill.skill_id,
                            category=get_status_category(marker, 1.0).value,
                            tags=tuple(tag.value for tag in get_status_tags(marker)),
                        )
                    )
                    invincible_duration = int(effect.params.get("invincible_duration", 1))
                    if invincible_duration > 0:
                        self._apply_status_effect(target, self._build_status_effect(target, reactive_skill, "invincible", invincible_duration, 1.0, {}), logs, round_index, target.name, reactive_skill.name, reactive_skill.skill_type)
                    if bool(effect.params.get("become_untargetable", True)):
                        self._apply_status_effect(target, self._build_status_effect(target, reactive_skill, "untargetable", invincible_duration, 1.0, {}), logs, round_index, target.name, reactive_skill.name, reactive_skill.skill_type)
                    self._apply_status_effect(target, self._build_status_effect(target, reactive_skill, "stun", invincible_duration, 1.0, {}), logs, round_index, target.name, reactive_skill.name, reactive_skill.skill_type)
                    heal_ratio = float(effect.params.get("heal_ratio", 0.0))
                    if heal_ratio > 0:
                        target.status_effects.append(
                            StatusEffect(
                                "delayed_heal",
                                invincible_duration,
                                heal_ratio,
                                target.unit_id,
                                reactive_skill.skill_id,
                                category=get_status_category("delayed_heal", heal_ratio).value,
                                tags=tuple(tag.value for tag in get_status_tags("delayed_heal")),
                                params={"heal_scale": str(effect.params.get("heal_scale", "self_max_hp")), "action_name": str(effect.params.get("heal_action_name", "整装归来"))},
                            )
                        )
                elif effect.effect_type == "rescue_on_hp_threshold_or_death_once":
                    threshold = float(effect.params.get("hp_threshold", 0.0))
                    trigger_on_death = bool(effect.params.get("trigger_on_death", True))
                    marker = str(effect.params.get("used_marker", "rescue_on_hp_threshold_or_death_once_used"))
                    should_trigger = current_ratio <= threshold or (trigger_on_death and remaining_hp <= 0)
                    if not should_trigger or self._has_status(target, marker):
                        continue
                    target.status_effects.append(
                        StatusEffect(
                            marker,
                            -1,
                            1.0,
                            target.unit_id,
                            reactive_skill.skill_id,
                            category=get_status_category(marker, 1.0).value,
                            tags=tuple(tag.value for tag in get_status_tags(marker)),
                        )
                    )
                    rescue_effects = [deepcopy(item) for item in reactive_skill.effects if item.effect_type != "rescue_on_hp_threshold_or_death_once"]
                    if not rescue_effects:
                        continue
                    rescue_skill = SkillData(
                        skill_id=f"{reactive_skill.skill_id}_rescue",
                        name=str(effect.params.get("action_name", reactive_skill.name)),
                        skill_type="被动",
                        target_type="自身",
                        damage_coefficient=0.0,
                        target_side="ally",
                        effects=rescue_effects,
                    )
                    self._apply_skill_effects(target, target, rescue_skill, logs, round_index, allies=target_allies, enemies=target_enemies)

    def _trigger_ally_death_passives(
        self,
        fallen: BattleUnit,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if any(effect.effect_type == "pending_revive" for effect in fallen.status_effects):
            return
        if any(effect.effect_type == "revive_cooldown" for effect in fallen.status_effects):
            return
        for watcher in allies:
            if not watcher.is_alive or watcher.unit_id == fallen.unit_id:
                continue
            for reactive_skill in self._iter_reactive_skills(watcher, "友军阵亡后"):
                for effect in reactive_skill.effects:
                    if effect.effect_type != "revive_ally_next_round":
                        continue
                    usage_marker = str(effect.params.get("usage_marker", "revive_ally_next_round_used"))
                    limit = int(effect.params.get("max_triggers", 1))
                    if watcher._status_total(usage_marker) >= limit:
                        continue
                    delay_rounds = int(effect.params.get("delay_rounds", 1))
                    fallen.status_effects.append(
                        StatusEffect(
                            "pending_revive",
                            max(1, delay_rounds),
                            effect.value,
                            watcher.unit_id,
                            reactive_skill.skill_id,
                            category=get_status_category("pending_revive", effect.value).value,
                            tags=tuple(tag.value for tag in get_status_tags("pending_revive")),
                            params={
                                "source_unit_id": watcher.unit_id,
                                "heal_ratio": float(effect.params.get("heal_ratio", effect.value)),
                                "heal_scale": str(effect.params.get("heal_scale", "source_max_hp")),
                                "cooldown_rounds": int(effect.params.get("cooldown_rounds", 0)),
                                "action_name": str(effect.params.get("action_name", reactive_skill.name)),
                            },
                        )
                    )
                    self._grant_stack_status(
                        watcher,
                        actor=watcher,
                        skill=reactive_skill,
                        effect_type=usage_marker,
                        amount=1.0,
                        duration=-1,
                        max_stacks=limit,
                        logs=logs,
                        round_index=round_index,
                        actor_name=watcher.name,
                        action_name=str(effect.params.get("usage_action_name", "重整筹备")),
                    )
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=watcher,
                        action=str(effect.params.get("prepare_action_name", "准备复活")),
                        target=fallen,
                        value=effect.value,
                        event_kind="status",
                        metadata={"skill_type": reactive_skill.skill_type, "effect_type": effect.effect_type},
                        status_delta="pending_revive",
                    )
                    return

    def _trigger_receive_attack_heal_statuses(
        self,
        target: BattleUnit,
        allies: list[BattleUnit] | None,
        opponents: list[BattleUnit] | None,
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        roster = [*((allies or [])), *((opponents or []))]
        for effect in list(target.status_effects):
            if effect.effect_type != "heal_on_receive_attack":
                continue
            source = next((unit for unit in roster if unit.unit_id == effect.source_unit_id), None)
            if source is None:
                continue
            scale = str(effect.params.get("heal_scale", "source_max_hp"))
            base_value = source.max_hp if scale == "source_max_hp" else source.stats.attack
            heal_amount = max(0.0, base_value * effect.value)
            if heal_amount <= 0:
                continue
            before = target.current_hp
            target.current_hp = min(target.max_hp, target.current_hp + heal_amount)
            actual_heal = target.current_hp - before
            if actual_heal <= 0:
                continue
            self._append_log(
                logs,
                round_index=round_index,
                actor=source,
                action=str(effect.params.get("action_name", "受击治疗")),
                target=target,
                value=actual_heal,
                event_kind="heal",
                metadata={"skill_type": "状态", "effect_type": effect.effect_type},
                hp_delta=actual_heal,
            )

    def _trigger_anger_mark_burst(
        self,
        target: BattleUnit,
        attacker: BattleUnit,
        allies: list[BattleUnit] | None,
        opponents: list[BattleUnit] | None,
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        anger_effect = next((effect for effect in target.status_effects if effect.effect_type == "anger_mark"), None)
        if anger_effect is None:
            return
        hit_threshold = int(anger_effect.params.get("hit_threshold", 3))
        current_hits = int(anger_effect.params.get("hits_taken", 0)) + 1
        anger_effect.params["hits_taken"] = current_hits
        if current_hits < hit_threshold:
            return
        lost_hp = max(0.0, target.max_hp - target.current_hp)
        if lost_hp <= 0:
            target.status_effects = [effect for effect in target.status_effects if effect is not anger_effect]
            return
        source = next((unit for unit in [*((allies or [])), *((opponents or []))] if unit.unit_id == anger_effect.source_unit_id and unit.is_alive), None) or attacker
        damage_ratio = float(anger_effect.params.get("lost_hp_damage_ratio", anger_effect.value))
        actual_damage, absorbed, blocked = self._apply_damage(
            source,
            target,
            max(1.0, lost_hp * damage_ratio),
            logs,
            round_index,
            skill_name=str(anger_effect.params.get("action_name", "怒意标记")),
            skill_type="印记",
            ignore_defense=True,
            allies=allies,
            opponents=opponents,
        )
        self._append_log(
            logs,
            round_index=round_index,
            actor=source,
            action=str(anger_effect.params.get("action_name", "怒意标记")),
            target=target,
            value=actual_damage,
            event_kind="damage",
            metadata={"skill_type": "印记", "effect_type": "anger_mark", "absorbed": round(absorbed, 2), "invincible": blocked},
            hp_delta=-actual_damage,
            energy_delta=10 if actual_damage > 0 else 0.0,
        )
        target.status_effects = [effect for effect in target.status_effects if effect is not anger_effect]

    def _handle_kill_triggers(
        self,
        actor: BattleUnit,
        skill: SkillData,
        target: BattleUnit,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
    ) -> None:
        for passive in self._iter_passive_skill_slots(actor):
            for effect in passive.effects:
                if effect.effect_type == "gain_energy_and_heal_on_enemy_death":
                    before_energy = actor.current_energy
                    actor.current_energy = min(actor.max_energy, actor.current_energy + int(effect.value))
                    heal_amount = actor.stats.attack * float(effect.params.get("heal_attack_ratio", 0.0))
                    actor.current_hp = min(actor.max_hp, actor.current_hp + heal_amount)
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action="敌亡回能回血",
                        target=actor,
                        value=(actor.current_energy - before_energy) + heal_amount,
                        event_kind="heal",
                        metadata={"skill_type": passive.skill_type, "effect_type": effect.effect_type},
                        hp_delta=heal_amount,
                        energy_delta=actor.current_energy - before_energy,
                    )
                elif effect.effect_type == "gain_attack_bonus_on_kill":
                    current_stacks = len([item for item in actor.status_effects if item.effect_type == "kill_attack_bonus"])
                    max_stacks = int(effect.params.get("max_stacks", 999))
                    if current_stacks < max_stacks:
                        actor.status_effects.append(self._build_status_effect(actor, passive, "kill_attack_bonus", effect.duration, effect.value, effect.params))
                elif effect.effect_type == "gain_extra_turn_on_kill":
                    limit = effect.params.get("limit_per_round")
                    if limit is not None and actor.extra_turns_gained_this_round >= int(limit):
                        continue
                    actor.extra_turns += int(effect.value)
                    actor.extra_turns_gained_this_round += int(effect.value)
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action="击杀再行动",
                        target=actor,
                        value=actor.extra_turns,
                        event_kind="system",
                        metadata={"skill_type": passive.skill_type, "effect_type": effect.effect_type},
                        status_delta="extra_turn",
                    )
                elif effect.effect_type == "crit_rate_bonus_on_kill" and effect.value > 0:
                    actor.status_effects.append(self._build_status_effect(actor, passive, "crit_rate_bonus", effect.duration, effect.value, effect.params))
        kill_bonus_status = skill.params.get("kill_bonus_hit_count_status")
        if kill_bonus_status:
            mapping = skill.params.get("kill_bonus_hit_count_by_level", {})
            amount = int(mapping.get(str(skill.level), mapping.get(skill.level, 0)))
            if amount > 0:
                self._grant_stack_status(actor, actor=actor, skill=skill, effect_type=str(kill_bonus_status), amount=amount, duration=-1, logs=logs, round_index=round_index, actor_name=actor.name, action_name=str(skill.params.get("kill_bonus_action_name", "击杀成长")))

    def _trigger_receive_attack_passives(
        self,
        target: BattleUnit,
        attacker: BattleUnit,
        allies: list[BattleUnit] | None,
        opponents: list[BattleUnit] | None,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        source_skill_name: str,
        source_skill_type: str,
    ) -> None:
        target_allies = (allies if target.side == attacker.side else opponents) or [target]
        target_enemies = (opponents if target.side == attacker.side else allies) or [attacker]
        prioritized_enemies = [attacker, *[unit for unit in target_enemies if unit.unit_id != attacker.unit_id]]
        for reactive_skill in self._iter_reactive_skills(target, "受击后"):
            for effect in reactive_skill.effects:
                params = effect.params
                allowed_skill_types = set(params.get("allowed_skill_types", []))
                if allowed_skill_types and source_skill_type not in allowed_skill_types:
                    continue
                required_status = params.get("required_status_effect")
                if required_status and not self._has_status(target, str(required_status)):
                    continue
                forbidden_status = params.get("forbidden_status_effect")
                if forbidden_status and self._has_status(target, str(forbidden_status)):
                    continue
                if effect.effect_type == "gain_stack_on_receive_attack":
                    if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    self._grant_stack_status(
                        target,
                        actor=target,
                        skill=reactive_skill,
                        effect_type=str(params.get("stack_name")),
                        amount=effect.value,
                        duration=int(params.get("stack_duration", effect.duration)),
                        max_stacks=float(params.get("max_stacks", 999)),
                        logs=logs,
                        round_index=round_index,
                        actor_name=target.name,
                        action_name=str(params.get("action_name", effect.effect_type)),
                    )
                elif effect.effect_type == "transform_stack_to_status_on_threshold":
                    stack_name = str(params.get("stack_name"))
                    if target._status_total(stack_name) < float(params.get("threshold", 0)):
                        continue
                    clear_stack_name = str(params.get("clear_stack_name", stack_name))
                    target.status_effects = [item for item in target.status_effects if item.effect_type != clear_stack_name]
                    status_effect = self._build_status_effect(
                        target,
                        reactive_skill,
                        str(params.get("status_effect_type")),
                        int(params.get("status_duration", effect.duration)),
                        effect.value,
                        dict(params.get("status_params", {})),
                    )
                    self._apply_status_effect(target, status_effect, logs, round_index, target.name, reactive_skill.name, reactive_skill.skill_type)
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=target,
                        action=str(params.get("action_name", effect.effect_type)),
                        target=target,
                        value=status_effect.value,
                        event_kind="status",
                        metadata={"skill_type": reactive_skill.skill_type, "effect_type": effect.effect_type},
                        status_delta=str(params.get("status_effect_type", effect.effect_type)),
                    )
                elif effect.effect_type == "apply_status_to_attacker_on_receive_attack":
                    if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    proxy_effect = SkillEffectData(effect_type=str(params.get("status_effect_type")), value=float(params.get("status_value", effect.value)), duration=int(params.get("status_duration", effect.duration)), chance=1.0, params={"applied_status": str(params.get("status_effect_type"))})
                    if not self._effect_hits(target, attacker, proxy_effect, reactive_skill):
                        continue
                    status_effect = self._build_status_effect(target, reactive_skill, str(params.get("status_effect_type")), int(params.get("status_duration", effect.duration)), float(params.get("status_value", effect.value)), dict(params.get("status_params", {})))
                    self._apply_status_effect(attacker, status_effect, logs, round_index, target.name, reactive_skill.name, reactive_skill.skill_type)
                elif effect.effect_type == "follow_up_attack_on_receive_attack_stack_threshold":
                    stack_name = str(params.get("stack_name"))
                    if target._status_total(stack_name) < float(params.get("threshold", 0)):
                        continue
                    consumed_stack_name = str(params.get("consumed_stack_name", stack_name))
                    self._consume_status_by_effect_type(target, consumed_stack_name, logs, round_index, actor_name=target.name, skill_name=reactive_skill.name, skill_type=reactive_skill.skill_type)
                    follow_up_skill = SkillData(
                        skill_id=f"{reactive_skill.skill_id}_follow_up",
                        name=str(params.get("action_name", reactive_skill.name)),
                        skill_type="追击",
                        target_type=str(params.get("target_type", "随机单体")),
                        damage_coefficient=effect.value,
                        target_side="enemy",
                        hit_count=int(params.get("hit_count", 1)),
                        retarget_per_hit=bool(params.get("retarget_per_hit", False)),
                        params={key: value for key, value in params.items() if key.startswith("disable_")},
                    )
                    self._execute_skill(target, follow_up_skill, target_allies, prioritized_enemies, logs, round_index)
                elif effect.effect_type == "counterattack_on_receive_attack":
                    if not target.is_alive or not attacker.is_alive:
                        continue
                    if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    counter_skill = self._build_follow_up_attack_skill(
                        target,
                        name=str(params.get("action_name", reactive_skill.name)),
                        damage_coefficient=effect.value,
                        target_type="单体",
                        params={key: value for key, value in params.items() if key.startswith("disable_")},
                    )
                    self._execute_skill(target, counter_skill, target_allies, prioritized_enemies, logs, round_index)

    def _trigger_enemy_damage_watchers(
        self,
        target: BattleUnit,
        actor: BattleUnit,
        allies: list[BattleUnit] | None,
        opponents: list[BattleUnit] | None,
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        watching_team = (allies if target.side != actor.side else opponents) or []
        for watcher in watching_team:
            if not watcher.is_alive:
                continue
            for passive in self._iter_passive_skill_slots(watcher):
                for effect in passive.effects:
                    if effect.effect_type != "gain_stack_when_column_front_enemy_damaged":
                        continue
                    if target.position != self._frontline_position_for(watcher.position):
                        continue
                    if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    self._grant_stack_status(
                        watcher,
                        actor=watcher,
                        skill=passive,
                        effect_type=str(effect.params.get("stack_name")),
                        amount=effect.value,
                        duration=effect.duration,
                        max_stacks=float(effect.params.get("max_stacks", 999)),
                        logs=logs,
                        round_index=round_index,
                        actor_name=watcher.name,
                        action_name=str(effect.params.get("action_name", effect.effect_type)),
                    )

    def _break_freeze_on_hit(self, target: BattleUnit, logs: list[BattleLogEntry], round_index: int) -> None:
        frozen = [effect for effect in target.status_effects if effect.effect_type == "freeze"]
        if not frozen:
            return
        target.status_effects = [effect for effect in target.status_effects if effect.effect_type != "freeze"]
        logs.append(BattleLogEntry(round_index, target.name, "freeze解除", target.name, 0.0, metadata={"skill_type": "状态", "effect_type": "freeze"}))

    def _trigger_team_action_passives(
        self,
        actor: BattleUnit,
        skill: SkillData,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        watchers = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        for watcher in watchers:
            if not watcher.is_alive or watcher.unit_id == actor.unit_id:
                continue
            for reactive_skill in self._iter_reactive_skills(watcher, "友军行动后"):
                for effect in reactive_skill.effects:
                    if effect.effect_type != "follow_up_on_ally_actions":
                        if effect.effect_type != "chance_follow_up_on_ally_action":
                            continue
                    watcher.team_action_count_this_round += 1
                    if effect.effect_type == "follow_up_on_ally_actions":
                        required_actions = int(effect.params.get("required_actions", 4))
                        if watcher.team_action_count_this_round % required_actions != 0:
                            continue
                    elif effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    per_round_limit = int(effect.params.get("per_round_limit", 999))
                    if watcher.team_action_triggers_this_round >= per_round_limit:
                        continue
                    base_skill = self._resolve_turn_basic_attack_skill(watcher)
                    follow_up_skill = self._clone_skill(base_skill, skill_type="追击", name=str(effect.params.get("action_name", f"{base_skill.name}追击")))
                    if not self._execute_skill(watcher, follow_up_skill, watchers, enemies, logs, round_index):
                        continue
                    watcher.last_skill_type = "追击"
                    watcher.team_action_triggers_this_round += 1
                    granted_stack = effect.params.get("granted_stack_name")
                    if granted_stack:
                        self._grant_stack_status(
                            watcher,
                            actor=watcher,
                            skill=reactive_skill,
                            effect_type=str(granted_stack),
                            amount=float(effect.params.get("granted_stack_amount", 1)),
                            duration=int(effect.params.get("granted_stack_duration", 3)),
                            max_stacks=float(effect.params.get("granted_stack_max", 999)),
                            logs=logs,
                            round_index=round_index,
                            actor_name=watcher.name,
                            action_name=str(effect.params.get("granted_stack_action_name", "叠层")),
                        )
                    self._trigger_actor_passives(watcher, "行动后", ally_units, enemy_units, logs, round_index)

    def _trigger_guo_jia_shadow_on_action(
        self,
        actor: BattleUnit,
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        watchers = ally_units if actor.side == "ally" else enemy_units
        enemies = enemy_units if actor.side == "ally" else ally_units
        for watcher in watchers:
            if not watcher.is_alive or watcher.hero_id == actor.hero_id and watcher.unit_id == actor.unit_id:
                continue
            self._trigger_guo_jia_shadow_attack(watcher, watchers, enemies, logs, round_index, triggered_by="行动后")

    def _trigger_guo_jia_shadow_attack(
        self,
        actor: BattleUnit,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        triggered_by: str,
        round_end: bool = False,
    ) -> None:
        if not actor.is_alive:
            return
        shadow_effect = next((effect for effect in actor.status_effects if effect.effect_type == "guo_jia_chess_shadow"), None)
        passive_effect = next((item for passive in self._iter_passive_skill_slots(actor) for item in passive.effects if item.effect_type == "guo_jia_shadow_reaction"), None)
        if shadow_effect is None or passive_effect is None:
            return
        low_hp_threshold = float(passive_effect.params.get("low_hp_threshold", 0.6))
        living_enemies = [unit for unit in enemies if unit.is_alive]
        if not living_enemies:
            return
        if not round_end and not any(unit.max_hp > 0 and (unit.current_hp / unit.max_hp) < low_hp_threshold for unit in living_enemies):
            return
        attacks = int(max(1, shadow_effect.value)) if round_end else 1
        for _ in range(attacks):
            living_enemies = [unit for unit in enemies if unit.is_alive]
            if not living_enemies:
                break
            target = min(living_enemies, key=lambda unit: ((unit.current_hp / unit.max_hp) if unit.max_hp > 0 else 0.0, unit.position))
            percent_hp_damage = min(target.max_hp * float(passive_effect.params.get("percent_hp_damage", 0.0)), actor.stats.attack * float(passive_effect.params.get("cap_attack_multiplier", 0.0)))
            total_damage = actor.stats.attack * passive_effect.value + percent_hp_damage
            actual_damage, absorbed, blocked_by_invincible = self._apply_damage(
                actor,
                target,
                total_damage,
                logs,
                round_index,
                skill_name="棋影",
                skill_type="追击",
                ignore_defense=True,
                allies=allies,
                opponents=enemies,
                invincible_pierce_ratio=float(passive_effect.params.get("invincible_pierce_ratio", 0.0)),
            )
            self._append_log(
                logs,
                round_index=round_index,
                actor=actor,
                action="棋影",
                target=target,
                value=actual_damage,
                event_kind="damage",
                metadata={"skill_type": "追击", "effect_type": passive_effect.effect_type, "triggered_by": triggered_by, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible},
                hp_delta=-actual_damage,
                energy_delta=10 if actual_damage > 0 else 0.0,
            )
            shadow_effect.value -= 1
            if shadow_effect.value <= 0:
                actor.status_effects = [effect for effect in actor.status_effects if effect is not shadow_effect]
                break
        actor.status_effects = [effect for effect in actor.status_effects if effect.effect_type != "guo_jia_shadow_crit_bonus"]

    def _trigger_reactive_marks(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        lightning_mark = next((effect for effect in target.status_effects if effect.effect_type == "lightning_mark"), None)
        if lightning_mark is None:
            return
        source_pool = allies + enemies
        source = next((unit for unit in source_pool if unit.unit_id == lightning_mark.source_unit_id and unit.is_alive), None)
        if source is None:
            return
        if actor.unit_id != source.unit_id:
            trigger_chance = float(lightning_mark.params.get("ally_trigger_chance", 0.0))
            if trigger_chance <= 0 or self.random_service.roll() >= trigger_chance:
                return
        source_allies = allies if source.side == actor.side else enemies
        source_enemies = enemies if source.side == actor.side else allies
        splash_pool = [unit for unit in source_enemies if unit.is_alive and unit.unit_id != target.unit_id]
        splash_targets = self._pick_random_targets(splash_pool, int(lightning_mark.params.get("splash_count", 0))) if splash_pool else []
        for victim in [target, *splash_targets]:
            actual_damage, absorbed, blocked_by_invincible = self._apply_damage(
                source,
                victim,
                source.stats.attack * lightning_mark.value,
                logs,
                round_index,
                skill_name="雷电印记",
                skill_type="印记",
                ignore_defense=True,
                allies=source_allies,
                opponents=source_enemies,
            )
            self._append_log(
                logs,
                round_index=round_index,
                actor=source,
                action="雷电印记",
                target=victim,
                value=actual_damage,
                event_kind="damage",
                metadata={"skill_type": "印记", "effect_type": "lightning_mark", "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible},
                hp_delta=-actual_damage,
                energy_delta=10 if actual_damage > 0 else 0.0,
            )
        self._trigger_energy_gain_passives(source, {"lightning"}, logs, round_index, source_skill_name="雷电印记")

    def _apply_single_effect(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        skill: SkillData,
        effect: SkillEffectData,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        allies: list[BattleUnit],
        enemies: list[BattleUnit],
    ) -> None:
        if effect.effect_type == "percent_hp_damage":
            cap = actor.stats.attack * float(effect.params.get("cap_attack_multiplier", 0.0))
            damage = min(target.max_hp * effect.value, cap if cap > 0 else target.max_hp * effect.value)
            actual_damage, absorbed, blocked_by_invincible = self._apply_damage(actor, target, damage, logs, round_index, skill_name="百分比伤害", skill_type="效果", ignore_defense=True, allies=allies, opponents=enemies)
            self._append_log(
                logs,
                round_index=round_index,
                actor=actor,
                action="百分比伤害",
                target=target,
                value=actual_damage,
                event_kind="damage",
                metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible, "skill_id": skill.skill_id},
                hp_delta=-actual_damage,
                energy_delta=10 if actual_damage > 0 else 0.0,
            )
            return
        if effect.effect_type == "cleanse_random_allies":
            candidates = [unit for unit in allies if unit.is_alive and any(self._status_matches_filter(item, effect.status_filter) for item in unit.status_effects)]
            for ally in candidates[: int(effect.params.get("count", 1))]:
                self._clear_status_effects(ally, status_filter=effect.status_filter, count=int(effect.value), actor_name=actor.name, skill_name=skill.name, skill_type=skill.skill_type, round_index=round_index, logs=logs)
            return
        proxy_skill = SkillData(skill.skill_id, skill.name, skill.skill_type, skill.target_type, skill.damage_coefficient, target_side=skill.target_side, trigger_timing=skill.trigger_timing, energy_cost=skill.energy_cost, effects=[effect], params=skill.params)
        self._apply_skill_effects(actor, target, proxy_skill, logs, round_index, allies=allies, enemies=enemies)

    def _apply_skill_effects(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        skill: SkillData,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        allies: list[BattleUnit] | None = None,
        enemies: list[BattleUnit] | None = None,
    ) -> None:
        allies = allies or [actor]
        enemies = enemies or []
        for effect in skill.effects:
            if effect.effect_type == "heal":
                heal_amount = actor.stats.attack * effect.value
                target.current_hp = min(target.max_hp, target.current_hp + heal_amount)
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action="治疗",
                    target=target,
                    value=heal_amount,
                    event_kind="heal",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "skill_id": skill.skill_id},
                    hp_delta=heal_amount,
                )
            elif effect.effect_type == "heal_side":
                target_side = str(effect.params.get("target_side", "ally"))
                selection = str(effect.params.get("selection", "all"))
                count = int(effect.params.get("count", 99))
                row_filter = effect.params.get("row_filter")
                scale = str(effect.params.get("scale", "attack"))
                pool = allies if target_side == "ally" else enemies
                selected = self._select_units_from_pool(actor, target, pool, selection=selection, count=count, row_filter=str(row_filter) if row_filter else None, exclude_actor=bool(effect.params.get("exclude_actor", False)))
                for recipient in selected:
                    if scale == "caster_max_hp":
                        heal_amount = actor.max_hp * effect.value
                    else:
                        heal_amount = actor.stats.attack * effect.value
                    recipient.current_hp = min(recipient.max_hp, recipient.current_hp + heal_amount)
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action=str(effect.params.get("action_name", "治疗")),
                        target=recipient,
                        value=heal_amount,
                        event_kind="heal",
                        metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "skill_id": skill.skill_id},
                        hp_delta=heal_amount,
                    )
            elif effect.effect_type == "shield":
                shield_effect = self._build_status_effect(actor, skill, "shield", effect.duration, actor.stats.attack * effect.value, effect.params)
                self._apply_status_effect(target, shield_effect, logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "apply_status_to_side":
                target_side = str(effect.params.get("target_side", "ally"))
                status_effect_type = str(effect.params.get("status_effect_type", ""))
                if not status_effect_type:
                    continue
                selection = str(effect.params.get("selection", "all"))
                count = int(effect.params.get("count", 99))
                row_filter = effect.params.get("row_filter")
                pool = allies if target_side == "ally" else enemies
                selected = self._select_units_from_pool(actor, target, pool, selection=selection, count=count, row_filter=str(row_filter) if row_filter else None, exclude_actor=bool(effect.params.get("exclude_actor", False)))
                status_value = float(effect.params.get("status_value", effect.value))
                status_duration = int(effect.params.get("status_duration", effect.duration))
                status_params = dict(effect.params.get("status_params", {}))
                for recipient in selected:
                    proxy_effect = SkillEffectData(status_effect_type, status_value, status_duration, chance=effect.chance, params={"applied_status": status_effect_type})
                    if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                        continue
                    if get_status_category(status_effect_type, status_value) == StatusCategory.DEBUFF and not self._effect_hits(actor, recipient, proxy_effect, skill):
                        self._append_log(
                            logs,
                            round_index=round_index,
                            actor=actor,
                            action=f"{status_effect_type}被抵抗",
                            target=recipient,
                            value=0.0,
                            event_kind="status",
                            metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": status_effect_type, "resisted": True, "skill_id": skill.skill_id},
                            status_delta=status_effect_type,
                        )
                        continue
                    status_effect = self._build_status_effect(actor, skill, status_effect_type, status_duration, status_value, status_params)
                    self._apply_status_effect(recipient, status_effect, logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "clear_status_from_side":
                target_side = str(effect.params.get("target_side", "ally"))
                selection = str(effect.params.get("selection", "all"))
                count = int(effect.params.get("count", 99))
                row_filter = effect.params.get("row_filter")
                pool = allies if target_side == "ally" else enemies
                selected = self._select_units_from_pool(actor, target, pool, selection=selection, count=count, row_filter=str(row_filter) if row_filter else None, exclude_actor=False)
                for recipient in selected:
                    self._clear_status_effects(recipient, status_filter=str(effect.params.get("status_filter", effect.status_filter or "debuff")), count=int(effect.value), actor_name=actor.name, skill_name=skill.name, skill_type=skill.skill_type, round_index=round_index, logs=logs)
            elif effect.effect_type == "cao_cao_grant_alliance":
                self._apply_cao_cao_alliance(target, actor, skill, effect, logs, round_index)
            elif effect.effect_type == "max_hp_bonus":
                bonus_ratio = max(0.0, effect.value)
                hp_gain = target.max_hp * bonus_ratio
                target.max_hp += hp_gain
                target.current_hp += hp_gain
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action="生命提升",
                    target=target,
                    value=hp_gain,
                    event_kind="status",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "skill_id": skill.skill_id},
                    hp_delta=hp_gain,
                    status_delta=effect.effect_type,
                )
            elif effect.effect_type in {"stun", "silence", "freeze", "taunt", "invincible", "untargetable", "attack_bonus", "defense_bonus", "speed_bonus", "damage_reduction", "crit_rate_bonus", "crit_damage_bonus", "frontline_damage_bonus", "conditional_damage_reduction", "skill_damage_bonus", "control_immunity", "heal_on_receive_attack", "heal_over_time", "delayed_heal", "anger_mark", "wood_mark"}:
                proxy_effect = SkillEffectData(effect.effect_type, effect.value, effect.duration, chance=1.0, params={"applied_status": effect.effect_type})
                if effect.effect_type in self.HARMFUL_EFFECTS and not self._effect_hits(actor, target, proxy_effect, skill):
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action=f"{effect.effect_type}被抵抗",
                        target=target,
                        value=0.0,
                        event_kind="status",
                        metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "resisted": True, "skill_id": skill.skill_id},
                        status_delta=effect.effect_type,
                    )
                    continue
                status_value = actor.stats.attack * effect.value if effect.effect_type in {"burn", "poison", "bleed"} else effect.value
                self._apply_status_effect(target, self._build_status_effect(actor, skill, effect.effect_type, effect.duration, status_value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type in {"burn", "poison", "bleed"}:
                proxy_effect = SkillEffectData(effect.effect_type, effect.value, effect.duration, chance=1.0, params={"applied_status": effect.effect_type})
                if not self._effect_hits(actor, target, proxy_effect, skill):
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action=f"{effect.effect_type}被抵抗",
                        target=target,
                        value=0.0,
                        event_kind="status",
                        metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "resisted": True, "skill_id": skill.skill_id},
                        status_delta=effect.effect_type,
                    )
                    continue
                status_effect = self._build_status_effect(actor, skill, effect.effect_type, effect.duration, actor.stats.attack * effect.value, effect.params)
                self._apply_status_effect(target, status_effect, logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "apply_status":
                status_type = str(effect.params.get("status_effect_type"))
                if not status_type:
                    continue
                if effect.chance < 1.0 and self.random_service.roll() >= effect.chance:
                    continue
                proxy_effect = SkillEffectData(status_type, effect.value, effect.duration, chance=1.0, params={"applied_status": status_type})
                if get_status_category(status_type, effect.value) == StatusCategory.DEBUFF and not self._effect_hits(actor, target, proxy_effect, skill):
                    self._append_log(
                        logs,
                        round_index=round_index,
                        actor=actor,
                        action=f"{status_type}被抵抗",
                        target=target,
                        value=0.0,
                        event_kind="status",
                        metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": status_type, "resisted": True, "skill_id": skill.skill_id},
                        status_delta=status_type,
                    )
                    continue
                max_stacks = effect.params.get("max_stacks")
                if max_stacks is not None:
                    current_count = len([item for item in target.status_effects if item.effect_type == status_type])
                    if current_count >= int(max_stacks):
                        continue
                status_value = float(effect.params.get("status_value", effect.value))
                status_duration = int(effect.params.get("status_duration", effect.duration))
                status_params = dict(effect.params.get("status_params", {}))
                self._apply_status_effect(target, self._build_status_effect(actor, skill, status_type, status_duration, status_value, status_params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "bonus_damage_if_target_has_status":
                if not any(item.effect_type == effect.status_filter for item in target.status_effects):
                    continue
                actual_damage, absorbed, blocked_by_invincible = self._apply_damage(actor, target, actor.stats.attack * effect.value, logs, round_index, skill_name="追加伤害", skill_type="效果", ignore_defense=True, allies=allies, opponents=enemies)
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action="追加伤害",
                    target=target,
                    value=actual_damage,
                    event_kind="damage",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible, "skill_id": skill.skill_id},
                    hp_delta=-actual_damage,
                    energy_delta=10 if actual_damage > 0 else 0.0,
                )
            elif effect.effect_type == "percent_hp_damage":
                cap = actor.stats.attack * float(effect.params.get("cap_attack_multiplier", 0.0))
                damage = min(target.max_hp * effect.value, cap if cap > 0 else target.max_hp * effect.value)
                actual_damage, absorbed, blocked_by_invincible = self._apply_damage(actor, target, damage, logs, round_index, skill_name="百分比伤害", skill_type="效果", ignore_defense=True, allies=allies, opponents=enemies)
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action="百分比伤害",
                    target=target,
                    value=actual_damage,
                    event_kind="damage",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible, "skill_id": skill.skill_id},
                    hp_delta=-actual_damage,
                    energy_delta=10 if actual_damage > 0 else 0.0,
                )
            elif effect.effect_type == "grant_stack":
                stack_name = str(effect.params.get("stack_name", effect.status_filter or effect.effect_type))
                stack_target = actor if effect.params.get("target", "self") == "self" else target
                self._grant_stack_status(stack_target, actor=actor, skill=skill, effect_type=stack_name, amount=effect.value, duration=effect.duration, max_stacks=float(effect.params.get("max_stacks", 999)) if effect.params.get("max_stacks") is not None else None, logs=logs, round_index=round_index, actor_name=actor.name, action_name=str(effect.params.get("action_name", stack_name)))
            elif effect.effect_type == "grant_team_shield":
                scale_stat = str(effect.params.get("scale_stat", "attack"))
                shield_value = actor.max_hp * effect.value if scale_stat == "max_hp" else actor.stats.attack * effect.value
                regen_ratio = float(effect.params.get("heal_ratio_if_has_shield", 0.0))
                for ally in allies:
                    if not ally.is_alive:
                        continue
                    self._apply_status_effect(ally, self._build_status_effect(actor, skill, "shield", effect.duration, shield_value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
                    if regen_ratio > 0:
                        self._apply_status_effect(ally, self._build_status_effect(actor, skill, "shield_regen", effect.duration, regen_ratio, {"heal_scale": "target_max_hp"}), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "protect_highest_attack_ally":
                candidates = [unit for unit in allies if unit.is_alive and (not bool(effect.params.get("exclude_self")) or unit.unit_id != actor.unit_id)]
                if not candidates:
                    continue
                protected = max(candidates, key=lambda unit: (unit.stats.attack, -unit.position))
                self._apply_status_effect(protected, self._build_status_effect(actor, skill, "damage_share", -1, effect.value, {"link_unit_id": actor.unit_id}), logs, round_index, actor.name, skill.name, skill.skill_type)
                linked_reduction = float(effect.params.get("linked_damage_reduction", 0.0))
                if linked_reduction > 0:
                    self._apply_status_effect(actor, self._build_status_effect(actor, skill, "damage_reduction", -1, linked_reduction, {"link_unit_id": protected.unit_id}), logs, round_index, actor.name, skill.name, skill.skill_type)
                    self._apply_status_effect(protected, self._build_status_effect(actor, skill, "damage_reduction", -1, linked_reduction, {"link_unit_id": actor.unit_id}), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "damage_reduction_from_stat":
                stat_name = str(effect.params.get("stat_name", "armor_break"))
                stat_value = float(getattr(target.stats, stat_name, 0.0))
                self._apply_status_effect(target, self._build_status_effect(actor, skill, "damage_reduction", effect.duration, stat_value * effect.value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "shield_by_stats":
                shield_value = actor.stats.attack * effect.value + actor.max_hp * float(effect.params.get("max_hp_ratio", 0.0))
                self._apply_status_effect(target, self._build_status_effect(actor, skill, "shield", effect.duration, shield_value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "grant_team_frontline_damage_bonus":
                for ally in allies:
                    if ally.is_alive:
                        self._apply_status_effect(ally, self._build_status_effect(actor, skill, "frontline_damage_bonus", effect.duration, effect.value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "heal_by_caster_max_hp":
                heal_amount = actor.max_hp * effect.value
                target.current_hp = min(target.max_hp, target.current_hp + heal_amount)
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=actor,
                    action="治疗",
                    target=target,
                    value=heal_amount,
                    event_kind="heal",
                    metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "skill_id": skill.skill_id},
                    hp_delta=heal_amount,
                )
            elif effect.effect_type == "cleanse":
                self._clear_status_effects(target, status_filter=effect.status_filter, count=int(effect.value), actor_name=actor.name, skill_name=skill.name, skill_type=skill.skill_type, round_index=round_index, logs=logs)
            elif effect.effect_type == "dispel":
                self._clear_status_effects(target, status_filter=effect.status_filter, count=int(effect.value), actor_name=actor.name, skill_name=skill.name, skill_type=skill.skill_type, round_index=round_index, logs=logs)
            elif effect.effect_type == "survive_once":
                used_marker = effect.params.get("used_marker_effect_type")
                if used_marker and self._has_status(target, str(used_marker)):
                    continue
                self._apply_status_effect(target, self._build_status_effect(actor, skill, "survive_once", effect.duration, effect.value, effect.params), logs, round_index, actor.name, skill.name, skill.skill_type)
            elif effect.effect_type == "follow_up_attack":
                min_times = int(effect.params.get("min_times", 1))
                max_times = int(effect.params.get("max_times", 1))
                chance = float(effect.params.get("chance", effect.chance))
                count = 0
                while count < max_times:
                    if count >= min_times and self.random_service.roll() >= chance:
                        break
                    count += 1
                    follow_up_skill = SkillData(
                        skill_id=f"{skill.skill_id}_follow_up",
                        name=str(effect.params.get("action_name", skill.name)),
                        skill_type="追击",
                        target_type=str(effect.params.get("target_type", "随机单体")),
                        damage_coefficient=effect.value,
                        target_side="enemy",
                        params={"bonus_status": effect.params.get("bonus_status"), "bonus_value": effect.params.get("bonus_value")},
                        effects=[SkillEffectData("bonus_damage_if_target_has_status", float(effect.params.get("bonus_value", 0.0)), 0, status_filter=effect.params.get("bonus_status"))] if effect.params.get("bonus_status") else [],
                    )
                    if not self._execute_skill(actor, follow_up_skill, allies, enemies, logs, round_index):
                        break
                    if logs:
                        logs[-1].metadata.update({"count": count, "chain_depth": count})
            elif effect.effect_type == "same_row_command_buff":
                stack_name = str(effect.params.get("stack_name", ""))
                stack_count = actor._status_total(stack_name) if stack_name else 0.0
                attack_bonus = effect.value + stack_count * float(effect.params.get("attack_bonus_per_stack", 0.0))
                shield_ratio = float(effect.params.get("shield_ratio", 0.0)) + stack_count * float(effect.params.get("shield_ratio_per_stack", 0.0))
                duration = int(effect.params.get("duration", effect.duration))
                for ally in [unit for unit in allies if unit.is_alive and (unit.position <= 3) == (actor.position <= 3)]:
                    self._apply_status_effect(ally, self._build_status_effect(actor, skill, "attack_bonus", duration, attack_bonus, {}), logs, round_index, actor.name, skill.name, skill.skill_type)
                    self._apply_status_effect(ally, self._build_status_effect(actor, skill, "shield", duration, actor.max_hp * shield_ratio, {}), logs, round_index, actor.name, skill.name, skill.skill_type)
                    energy_gain = int(effect.params.get("energy_gain", 0))
                    energy_chance = float(effect.params.get("energy_gain_chance", 0.0))
                    if energy_gain > 0 and self.random_service.roll() < energy_chance:
                        ally.current_energy = min(ally.max_energy, ally.current_energy + energy_gain)
            elif effect.effect_type == "guo_jia_ultimate_splash":
                for enemy in [unit for unit in enemies if unit.is_alive and unit.unit_id != target.unit_id]:
                    actual_damage, absorbed, blocked_by_invincible = self._apply_damage(actor, enemy, actor.stats.attack * effect.value, logs, round_index, skill_name="棋破万军溅射", skill_type="效果", ignore_defense=True, allies=allies, opponents=enemies)
                    logs.append(BattleLogEntry(round_index, actor.name, "棋破万军溅射", enemy.name, round(actual_damage, 2), metadata={"source_skill": skill.name, "skill_type": skill.skill_type, "effect_type": effect.effect_type, "absorbed": round(absorbed, 2), "invincible": blocked_by_invincible}))
            elif effect.effect_type in {"guo_jia_shadow_reaction", "follow_up_on_ally_actions", "chance_follow_up_on_ally_action", "gain_stack_when_column_front_enemy_damaged", "gain_energy_on_skill_tag", "damage_multiplier_by_target_hp", "gain_energy_and_heal_on_enemy_death", "gain_attack_bonus_on_kill", "gain_extra_turn_on_kill", "crit_rate_bonus_on_kill", "apply_status_on_skill_targets", "apply_random_status_to_side", "gain_stack_on_receive_attack", "transform_stack_to_status_on_threshold", "apply_status_to_attacker_on_receive_attack", "follow_up_attack_on_receive_attack_stack_threshold", "counterattack_on_receive_attack", "retreat_on_low_hp_once", "rescue_on_hp_threshold_or_death_once", "revive_ally_next_round"}:
                continue

    def _apply_damage(
        self,
        actor: BattleUnit,
        target: BattleUnit,
        damage: float,
        logs: list[BattleLogEntry],
        round_index: int,
        *,
        skill_name: str,
        skill_type: str,
        ignore_defense: bool = False,
        allies: list[BattleUnit] | None = None,
        opponents: list[BattleUnit] | None = None,
        allow_damage_share: bool = True,
        invincible_pierce_ratio: float = 0.0,
    ) -> tuple[float, float, bool]:
        if self._has_status(target, "invincible"):
            if invincible_pierce_ratio > 0:
                damage = max(1.0, damage * invincible_pierce_ratio)
            else:
                target.current_energy = min(target.max_energy, target.current_energy + 10)
                return 0.0, 0.0, True
        raw_damage = max(1.0, damage)
        if ignore_defense:
            raw_damage = max(1.0, damage)
        absorbed = self._consume_shield(target, raw_damage)
        actual_damage = max(0.0, raw_damage - absorbed)
        redirected_damage = 0.0
        if allow_damage_share and actual_damage > 0:
            shared_effect, protector = self._resolve_damage_share_link(target, actor, allies, opponents)
            if shared_effect is not None and protector is not None:
                redirect_ratio = MathUtils.clamp(shared_effect.value, 0.0, 1.0)
                redirected_damage = actual_damage * redirect_ratio
                redirected_damage *= 1 - MathUtils.percent(protector.damage_reduction())
                redirected_damage = max(0.0, redirected_damage)
                protected_side_allies = allies if protector.side == actor.side else opponents
                protected_side_enemies = opponents if protector.side == actor.side else allies
                protector_damage, protector_absorbed, protector_blocked = self._apply_damage(
                    actor,
                    protector,
                    redirected_damage,
                    logs,
                    round_index,
                    skill_name=skill_name,
                    skill_type="分担伤害",
                    ignore_defense=True,
                    allies=protected_side_allies,
                    opponents=protected_side_enemies,
                    allow_damage_share=False,
                    invincible_pierce_ratio=invincible_pierce_ratio,
                )
                redirected_damage = protector_damage
                self._append_log(
                    logs,
                    round_index=round_index,
                    actor=protector,
                    action="伤害分担",
                    target=target,
                    value=protector_damage,
                    event_kind="damage",
                    metadata={"skill_type": "状态", "effect_type": "damage_share", "source_skill": skill_name, "absorbed": round(protector_absorbed, 2), "invincible": protector_blocked},
                    hp_delta=-protector_damage,
                )
        target_damage = max(0.0, actual_damage - redirected_damage)
        remaining_hp = target.current_hp - target_damage
        alliance_effect = next((effect for effect in target.status_effects if effect.effect_type == "cao_cao_alliance"), None)
        alliance_cooldown = next((effect for effect in target.status_effects if effect.effect_type == "cao_cao_fatal_immunity_cooldown"), None)
        if target_damage > 0 and remaining_hp <= 0 and alliance_effect is not None and alliance_cooldown is None:
            heal_amount = target.max_hp * alliance_effect.value
            target_damage = 0.0
            actual_damage = 0.0
            target.current_hp = min(target.max_hp, target.current_hp + heal_amount)
            cooldown_rounds = max(1, int(alliance_effect.params.get("fatal_immunity_cooldown_rounds", 2)))
            cooldown_effect = StatusEffect(
                "cao_cao_fatal_immunity_cooldown",
                cooldown_rounds + 1,
                1.0,
                alliance_effect.source_unit_id,
                alliance_effect.source_skill_id,
                category=get_status_category("cao_cao_fatal_immunity_cooldown", 1.0).value,
                tags=tuple(tag.value for tag in get_status_tags("cao_cao_fatal_immunity_cooldown")),
                params={"fatal_immunity_cooldown_rounds": cooldown_rounds},
            )
            self._apply_status_effect(target, cooldown_effect, logs, round_index, target.name, "魏武之盟", "状态")
            self._append_log(
                logs,
                round_index=round_index,
                actor=target,
                action="魏武之盟护主",
                target=target,
                value=heal_amount,
                event_kind="heal",
                metadata={"skill_type": "状态", "effect_type": "cao_cao_alliance", "prevented_fatal": True},
                hp_delta=heal_amount,
                status_delta="cao_cao_alliance",
            )
        survive_effect = next((effect for effect in target.status_effects if effect.effect_type == "survive_once"), None)
        if target_damage > 0 and remaining_hp <= 0 and survive_effect is not None:
            actual_damage = max(0.0, target.current_hp - 1.0)
            target_damage = actual_damage
            target.current_hp = 1.0
            target.status_effects = [effect for effect in target.status_effects if effect is not survive_effect]
            self._trigger_survive_once(target, survive_effect, logs, round_index, allies=allies)
        else:
            target_allies = (allies if target.side == actor.side else opponents) or [target]
            target_enemies = (opponents if target.side == actor.side else allies) or [actor]
            if target_damage > 0:
                self._trigger_hp_threshold_passives(target, actor, remaining_hp, logs, round_index, target_allies=target_allies, target_enemies=target_enemies)
            target.current_hp = max(0.0, remaining_hp) if target_damage > 0 else target.current_hp
        actor.total_damage_dealt += target_damage
        target.total_damage_taken += target_damage
        target.current_energy = min(target.max_energy, target.current_energy + 10)
        if target_damage > 0:
            self._trigger_receive_attack_passives(target, actor, allies, opponents, logs, round_index, source_skill_name=skill_name, source_skill_type=skill_type)
            self._trigger_receive_attack_heal_statuses(target, allies, opponents, logs, round_index)
            self._trigger_anger_mark_burst(target, actor, allies, opponents, logs, round_index)
            self._trigger_enemy_damage_watchers(target, actor, allies, opponents, logs, round_index)
            self._break_freeze_on_hit(target, logs, round_index)
        if target_damage > 0 and remaining_hp <= 0:
            target_team = (allies if target.side == actor.side else opponents) or [target]
            opposing_team = (opponents if target.side == actor.side else allies) or [actor]
            self._trigger_ally_death_passives(target, target_team, opposing_team, logs, round_index)
        target_team = (allies if target.side == actor.side else opponents) or [target]
        self._trigger_cao_cao_guard_mode_for_team(target_team, logs, round_index)
        linked_units: list[BattleUnit] = []
        for unit in [*((allies or [])), *((opponents or [])), actor, target]:
            if all(existing.unit_id != unit.unit_id for existing in linked_units):
                linked_units.append(unit)
        self._cleanup_linked_statuses(linked_units)
        return target_damage, absorbed, False

    def _trigger_cao_cao_after_skill_resolution(
        self,
        actor: BattleUnit,
        skill: SkillData,
        resolved_targets: list[BattleUnit],
        allies: list[BattleUnit],
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        if not actor.is_alive or skill.skill_type != "普攻":
            return
        for effect in skill.effects:
            if effect.effect_type != "cao_cao_grant_lowest_hp_ally_defense_bonus":
                continue
            candidates = [unit for unit in allies if unit.is_alive and unit.unit_id != actor.unit_id]
            if not candidates:
                continue
            target = min(candidates, key=lambda unit: (unit.current_hp, unit.position))
            status_effect = self._build_status_effect(actor, skill, "defense_bonus", effect.duration or -1, effect.value, effect.params)
            self._apply_status_effect(target, status_effect, logs, round_index, actor.name, skill.name, skill.skill_type)
        for passive in self._iter_passive_skill_slots(actor):
            for effect in passive.effects:
                if effect.effect_type != "cao_cao_grant_alliance_on_normal_attack":
                    continue
                trigger_chance = 1.0 if self._has_status(actor, "cao_cao_guard_mode") else effect.value
                if trigger_chance < 1.0 and self.random_service.roll() >= trigger_chance:
                    continue
                targets: list[BattleUnit] = []
                lowest_ally = self._select_cao_cao_lowest_ally(allies, actor, exclude_self=True)
                if lowest_ally is not None:
                    targets.append(lowest_ally)
                if bool(effect.params.get("include_self")) and actor not in targets:
                    targets.append(actor)
                heal_ratio = self._get_cao_cao_alliance_heal_ratio(actor)
                if heal_ratio <= 0:
                    continue
                cooldown_rounds = int(effect.params.get("fatal_immunity_cooldown_rounds", 2))
                for target in targets:
                    self._apply_cao_cao_alliance(target, actor, passive, SkillEffectData(effect_type="cao_cao_grant_alliance", value=heal_ratio, duration=-1, params={"fatal_immunity_cooldown_rounds": cooldown_rounds}), logs, round_index)

    @staticmethod
    def _select_cao_cao_lowest_ally(allies: list[BattleUnit], actor: BattleUnit, *, exclude_self: bool) -> BattleUnit | None:
        candidates = [unit for unit in allies if unit.is_alive and (not exclude_self or unit.unit_id != actor.unit_id)]
        if not candidates:
            return None
        return min(candidates, key=lambda unit: (unit.current_hp, unit.position))

    def _get_cao_cao_alliance_heal_ratio(self, actor: BattleUnit) -> float:
        alliance_effect = next((effect for effect in actor.ultimate_skill.effects if effect.effect_type == "cao_cao_grant_alliance"), None)
        return float(alliance_effect.value) if alliance_effect is not None else 0.0

    def _apply_cao_cao_alliance(
        self,
        target: BattleUnit,
        actor: BattleUnit,
        skill: SkillData,
        effect: SkillEffectData,
        logs: list[BattleLogEntry],
        round_index: int,
    ) -> None:
        status_effect = self._build_status_effect(actor, skill, "cao_cao_alliance", effect.duration or -1, effect.value, effect.params)
        self._apply_status_effect(target, status_effect, logs, round_index, actor.name, skill.name, skill.skill_type)

    def _trigger_cao_cao_guard_mode_for_team(self, team_units: list[BattleUnit], logs: list[BattleLogEntry], round_index: int) -> None:
        living_team = [unit for unit in team_units if unit.is_alive]
        for watcher in living_team:
            if self._has_status(watcher, "cao_cao_guard_mode"):
                continue
            passive_pair = next(((passive, effect) for passive in self._iter_passive_skill_slots(watcher) for effect in passive.effects if effect.effect_type == "cao_cao_enter_guard_on_low_ally_hp"), None)
            if passive_pair is None:
                continue
            passive, effect = passive_pair
            threshold = float(effect.params.get("hp_threshold", 0.0))
            low_hp_ally_exists = any(unit.unit_id != watcher.unit_id and unit.max_hp > 0 and (unit.current_hp / unit.max_hp) <= threshold for unit in living_team)
            if not low_hp_ally_exists:
                continue
            bonus_hp = watcher.max_hp * effect.value
            watcher.max_hp += bonus_hp
            watcher.current_hp = min(watcher.max_hp, watcher.current_hp + bonus_hp)
            status_effect = self._build_status_effect(watcher, passive, "cao_cao_guard_mode", -1, effect.value, effect.params)
            self._apply_status_effect(watcher, status_effect, logs, round_index, watcher.name, passive.name, passive.skill_type)
            logs.append(BattleLogEntry(round_index, watcher.name, "援护状态", watcher.name, round(bonus_hp, 2), metadata={"skill_type": passive.skill_type, "effect_type": "cao_cao_guard_mode", "hp_bonus": round(bonus_hp, 2)}))

    def _trigger_cao_cao_round_end_alliances(self, units: list[BattleUnit], logs: list[BattleLogEntry], round_index: int) -> None:
        for unit in units:
            if not unit.is_alive:
                continue
            alliance_effect = next((effect for effect in unit.status_effects if effect.effect_type == "cao_cao_alliance"), None)
            if alliance_effect is None:
                continue
            heal_amount = unit.max_hp * alliance_effect.value
            before = unit.current_hp
            unit.current_hp = min(unit.max_hp, unit.current_hp + heal_amount)
            actual_heal = unit.current_hp - before
            self._append_log(
                logs,
                round_index=round_index,
                actor=unit,
                action="魏武之盟",
                target=unit,
                value=actual_heal,
                event_kind="heal",
                metadata={"skill_type": "状态", "effect_type": "cao_cao_alliance", "round_end": True},
                hp_delta=actual_heal,
            )
            source = next((item for item in units if item.unit_id == alliance_effect.source_unit_id and item.is_alive), None)
            if source is not None:
                self._trigger_cao_cao_round_end_bonus_heal(source, logs, round_index)

    def _trigger_cao_cao_round_end_bonus_heal(self, actor: BattleUnit, logs: list[BattleLogEntry], round_index: int) -> None:
        effect = next((item for passive in self._iter_passive_skill_slots(actor) for item in passive.effects if item.effect_type == "cao_cao_round_end_self_heal_on_alliance"), None)
        if effect is None or not actor.is_alive:
            return
        heal_amount = actor.max_hp * effect.value
        before = actor.current_hp
        actor.current_hp = min(actor.max_hp, actor.current_hp + heal_amount)
        actual_heal = actor.current_hp - before
        self._append_log(
            logs,
            round_index=round_index,
            actor=actor,
            action="会盟之利",
            target=actor,
            value=actual_heal,
            event_kind="heal",
            metadata={"skill_type": "被动", "effect_type": effect.effect_type},
            hp_delta=actual_heal,
        )

    def _tick_status_effects(self, units: list[BattleUnit], logs: list[BattleLogEntry], round_index: int) -> None:
        self._trigger_guo_jia_round_end_shadows(units, logs, round_index)
        self._trigger_cao_cao_round_end_alliances(units, logs, round_index)
        living_before = {unit.unit_id for unit in units if unit.is_alive}
        for unit in units:
            if not unit.is_alive:
                continue
            next_effects: list[StatusEffect] = []
            for effect in unit.status_effects:
                if effect.effect_type == "burn":
                    damage = effect.value
                    unit.current_hp = max(0.0, unit.current_hp - damage)
                    self._append_log(logs, round_index=round_index, actor=unit, action="灼烧", target=unit, value=damage, event_kind="damage", metadata={"effect_type": "burn", "skill_type": "状态"}, hp_delta=-damage)
                elif effect.effect_type == "poison":
                    damage = effect.value
                    unit.current_hp = max(0.0, unit.current_hp - damage)
                    self._append_log(logs, round_index=round_index, actor=unit, action="中毒", target=unit, value=damage, event_kind="damage", metadata={"effect_type": "poison", "skill_type": "状态"}, hp_delta=-damage)
                elif effect.effect_type == "bleed":
                    damage = effect.value
                    unit.current_hp = max(0.0, unit.current_hp - damage)
                    self._append_log(logs, round_index=round_index, actor=unit, action="流血", target=unit, value=damage, event_kind="damage", metadata={"effect_type": "bleed", "skill_type": "状态"}, hp_delta=-damage)
                elif effect.effect_type == "shield_regen" and any(item.effect_type == "shield" for item in unit.status_effects):
                    heal_scale = effect.params.get("heal_scale", "target_max_hp")
                    heal_amount = unit.max_hp * effect.value if heal_scale == "target_max_hp" else unit.stats.attack * effect.value
                    unit.current_hp = min(unit.max_hp, unit.current_hp + heal_amount)
                    self._append_log(logs, round_index=round_index, actor=unit, action="护盾回春", target=unit, value=heal_amount, event_kind="heal", metadata={"skill_type": "状态", "effect_type": "shield_regen"}, hp_delta=heal_amount)
                elif effect.effect_type == "heal_over_time":
                    heal_scale = str(effect.params.get("heal_scale", "target_max_hp"))
                    source = next((item for item in units if item.unit_id == effect.source_unit_id), None)
                    base_value = unit.max_hp if heal_scale == "target_max_hp" else ((source.max_hp if source is not None else unit.max_hp) if heal_scale == "source_max_hp" else (source.stats.attack if source is not None else unit.stats.attack))
                    heal_amount = max(0.0, base_value * effect.value)
                    if heal_amount > 0:
                        unit.current_hp = min(unit.max_hp, unit.current_hp + heal_amount)
                        self._append_log(logs, round_index=round_index, actor=source or unit, action=str(effect.params.get("action_name", "持续治疗")), target=unit, value=heal_amount, event_kind="heal", metadata={"skill_type": "状态", "effect_type": "heal_over_time"}, hp_delta=heal_amount)
                elif effect.effect_type == "delayed_heal" and effect.duration <= 1:
                    heal_scale = str(effect.params.get("heal_scale", "self_max_hp"))
                    heal_amount = unit.max_hp * effect.value if heal_scale in {"self_max_hp", "source_max_hp"} else unit.stats.attack * effect.value
                    if heal_amount > 0:
                        unit.current_hp = min(unit.max_hp, unit.current_hp + heal_amount)
                        self._append_log(logs, round_index=round_index, actor=unit, action=str(effect.params.get("action_name", "整装归来")), target=unit, value=heal_amount, event_kind="heal", metadata={"skill_type": "状态", "effect_type": "delayed_heal"}, hp_delta=heal_amount)
                if effect.effect_type == "freeze" and not unit.is_alive:
                    continue
                if effect.duration < 0:
                    next_effects.append(effect)
                    continue
                effect.duration -= 1
                if effect.duration > 0:
                    next_effects.append(effect)
            unit.status_effects = next_effects
        living_after = {unit.unit_id for unit in units if unit.is_alive}
        for fallen_unit in [unit for unit in units if unit.unit_id in living_before and unit.unit_id not in living_after]:
            allies = [unit for unit in units if unit.side == fallen_unit.side]
            enemies = [unit for unit in units if unit.side != fallen_unit.side]
            self._trigger_ally_death_passives(fallen_unit, allies, enemies, logs, round_index)
        self._cleanup_linked_statuses(units)

    def _trigger_guo_jia_round_end_shadows(self, units: list[BattleUnit], logs: list[BattleLogEntry], round_index: int) -> None:
        for actor in units:
            if not actor.is_alive:
                continue
            allies = [unit for unit in units if unit.side == actor.side]
            enemies = [unit for unit in units if unit.side != actor.side]
            self._trigger_guo_jia_shadow_attack(actor, allies, enemies, logs, round_index, triggered_by="回合结束", round_end=True)

    def _cleanup_linked_statuses(self, units: list[BattleUnit]) -> None:
        living_ids = {unit.unit_id for unit in units if unit.is_alive}
        for unit in units:
            unit.status_effects = [
                effect
                for effect in unit.status_effects
                if not effect.params.get("link_unit_id") or effect.params.get("link_unit_id") in living_ids
            ]

    def _build_result(
        self,
        winner: str,
        rounds: int,
        timed_out: bool,
        logs: list[BattleLogEntry],
        ally_units: list[BattleUnit],
        enemy_units: list[BattleUnit],
        rewards: dict[str, int] | None,
    ) -> BattleResult:
        if winner != "ally":
            stars = 0
        elif rounds <= 10:
            stars = 3
        elif rounds <= 20:
            stars = 2
        else:
            stars = 1
        statistics = {unit.name: round(unit.total_damage_dealt, 2) for unit in ally_units + enemy_units}
        granted_rewards = rewards if winner == "ally" and rewards is not None else ({"铜币": 300, "武将经验": 120} if winner == "ally" else {})
        return BattleResult(winner=winner, rounds=rounds, stars=stars, timed_out=timed_out, logs=logs, damage_statistics=statistics, rewards=granted_rewards)

