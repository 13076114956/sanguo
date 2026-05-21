from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import random
import re

from game.data.models import FormationData, HeroData, HeroQuality, PlayerData
from game.develop.hero_service import HeroDevelopmentService
from game.utility.time_utils import TimeUtils


@dataclass(slots=True)
class StageDefinition:
    stage_id: str
    name: str
    enemy_formation: dict[int, str]
    recommended_power: int
    rewards: dict[str, int]
    idle_rewards_per_hour: dict[str, int]
    enemy_level: int = 1
    enemy_stat_multiplier: float = 1.0
    stage_order: int = 1
    enemy_seed: str | int | None = None
    enemy_team_size: int = 6


@dataclass(slots=True)
class StageBattlePreparation:
    stage_id: str
    stage_name: str
    formation_id: str
    ally_formation: FormationData
    selectable_heroes: list[HeroData]
    enemy_heroes: list[HeroData]
    enemy_formation: dict[int, str]
    recommended_power: int
    current_power: int
    current_stamina: int
    challenge_cost: int
    min_heroes: int = 1
    max_heroes: int = 6
    can_start: bool = False


@dataclass(slots=True)
class ChapterDefinition:
    chapter_id: str
    name: str
    unlock_condition: str
    stage_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StaminaRecoveryResult:
    stamina: int
    recovered: int
    consumed_seconds: int
    next_recovery_seconds: int | None


class FormationService:
    MAX_HEROES = 6
    MAX_PRESETS = 3

    def __init__(self) -> None:
        self.hero_service = HeroDevelopmentService()

    def calculate_power(self, formation: FormationData, heroes: list[HeroData]) -> int:
        resolved_heroes = [self.hero_service.resolve_best_card(heroes, hero_ref) for hero_ref in formation.positions.values() if hero_ref]
        total_power = 0.0
        for hero in resolved_heroes:
            if hero is None:
                continue
            final_stats = self.hero_service.calculate_stats(hero).final
            total_power += final_stats.attack + final_stats.hp / 10
        return int(total_power)

    def deploy_hero(self, formation: FormationData, heroes: list[HeroData], position: int, hero_ref: str) -> FormationData:
        self._validate_position(position)
        if len(formation.positions) >= self.MAX_HEROES and position not in formation.positions:
            raise ValueError("阵容已满，最多上阵 6 名武将")
        self._assert_no_duplicate_template(formation, heroes, hero_ref, ignore_positions={position})
        formation.positions[position] = hero_ref
        return formation

    def undeploy_hero(self, formation: FormationData, position: int) -> FormationData:
        self._validate_position(position)
        formation.positions.pop(position, None)
        return formation

    def swap_positions(self, formation: FormationData, left_position: int, right_position: int) -> FormationData:
        self._validate_position(left_position)
        self._validate_position(right_position)
        if left_position == right_position:
            return formation
        left_ref = formation.positions.get(left_position)
        right_ref = formation.positions.get(right_position)
        if right_ref is None:
            formation.positions.pop(left_position, None)
        else:
            formation.positions[left_position] = right_ref
        if left_ref is None:
            formation.positions.pop(right_position, None)
        else:
            formation.positions[right_position] = left_ref
        return formation

    def validate(self, formation: FormationData) -> bool:
        return len(formation.positions) <= self.MAX_HEROES and all(1 <= position <= 6 for position in formation.positions)

    def validate_or_raise(self, formation: FormationData, heroes: list[HeroData]) -> None:
        if not formation.id:
            raise ValueError("阵容方案 ID 不可为空")
        if not self.validate(formation):
            raise ValueError("阵容站位数量或范围非法")
        resolved_templates: set[str] = set()
        for position, hero_ref in formation.positions.items():
            self._validate_position(position)
            if not hero_ref:
                continue
            template_id = self._resolve_template_id(heroes, hero_ref)
            if template_id in resolved_templates:
                raise ValueError("同模板武将不可重复上阵")
            resolved_templates.add(template_id)

    def validate_player_formations(self, player: PlayerData) -> None:
        if len(player.formations) > self.MAX_PRESETS:
            raise ValueError(f"阵容方案最多保存 {self.MAX_PRESETS} 套")
        formation_ids: set[str] = set()
        for formation in player.formations:
            if formation.id in formation_ids:
                raise ValueError(f"阵容方案 ID 重复：{formation.id}")
            formation_ids.add(formation.id)
            self.validate_or_raise(formation, player.heroes)
        active_formation_id = player.settings.get("active_formation_id")
        if active_formation_id and active_formation_id not in formation_ids:
            raise ValueError(f"当前激活的阵容方案不存在：{active_formation_id}")

    def ensure_battle_ready(self, formation: FormationData, heroes: list[HeroData], *, min_heroes: int = 1, max_heroes: int | None = None) -> None:
        self.validate_or_raise(formation, heroes)
        hero_count = len([hero_ref for hero_ref in formation.positions.values() if hero_ref])
        upper_bound = self.MAX_HEROES if max_heroes is None else max_heroes
        if hero_count < min_heroes:
            raise ValueError(f"出战武将至少需要 {min_heroes} 名")
        if hero_count > upper_bound:
            raise ValueError(f"出战武将最多只能 {upper_bound} 名")

    def _assert_no_duplicate_template(
        self,
        formation: FormationData,
        heroes: list[HeroData],
        hero_ref: str,
        *,
        ignore_positions: set[int] | None = None,
    ) -> None:
        target_template_id = self._resolve_template_id(heroes, hero_ref)
        ignored = ignore_positions or set()
        for position, existing_ref in formation.positions.items():
            if position in ignored or not existing_ref:
                continue
            if self._resolve_template_id(heroes, existing_ref) == target_template_id:
                raise ValueError("同模板武将不可重复上阵")

    def _resolve_template_id(self, heroes: list[HeroData], hero_ref: str) -> str:
        hero = self.hero_service.resolve_best_card(heroes, hero_ref)
        if hero is None:
            raise ValueError(f"阵容中的武将引用不存在：{hero_ref}")
        return hero.template_id

    @staticmethod
    def _validate_position(position: int) -> None:
        if not 1 <= position <= 6:
            raise ValueError("阵容站位必须在 1~6 之间")


class CampaignService:
    STAGE_ID_PATTERN = re.compile(r"^stage_(\d+)-(\d+)$")
    CHAPTER_ID_PATTERN = re.compile(r"^chapter_(\d+)$")

    def __init__(self, stage_definitions: dict[str, StageDefinition], chapter_definitions: dict[str, ChapterDefinition] | None = None) -> None:
        self.stage_definitions = stage_definitions
        self.chapter_definitions = self._prepare_chapter_definitions(chapter_definitions)
        self.stage_to_chapter: dict[str, str] = {}
        for chapter in self.chapter_definitions.values():
            for stage_id in chapter.stage_ids:
                if stage_id not in self.stage_definitions:
                    raise ValueError(f"章节 {chapter.chapter_id} 配置了不存在的关卡：{stage_id}")
                if stage_id in self.stage_to_chapter:
                    raise ValueError(f"关卡被重复配置到多个章节：{stage_id}")
                self.stage_to_chapter[stage_id] = chapter.chapter_id
        for stage_id in self.stage_definitions:
            if stage_id not in self.stage_to_chapter:
                raise ValueError(f"关卡未配置所属章节：{stage_id}")
        self.hero_service = HeroDevelopmentService()

    def is_stage_unlocked(self, player: PlayerData, stage_id: str) -> bool:
        if stage_id not in self.stage_definitions:
            raise ValueError(f"关卡不存在：{stage_id}")
        chapter_id = self.chapter_id_from_stage_id(stage_id)
        if not self.is_chapter_unlocked(player, chapter_id):
            return False
        chapter_stage_ids = self.list_stage_ids_in_chapter(chapter_id)
        index = chapter_stage_ids.index(stage_id)
        if index == 0:
            return True
        previous_stage_id = chapter_stage_ids[index - 1]
        return bool(player.stage_progress.get(previous_stage_id, {}).get("completed", False))

    def stage_unlock_reason(self, player: PlayerData, stage_id: str) -> str | None:
        if self.is_stage_unlocked(player, stage_id):
            return None
        chapter_id = self.chapter_id_from_stage_id(stage_id)
        chapter = self.chapter_definitions[chapter_id]
        if not self.is_chapter_unlocked(player, chapter_id):
            return chapter.unlock_condition
        chapter_stage_ids = self.list_stage_ids_in_chapter(chapter_id)
        index = chapter_stage_ids.index(stage_id)
        if index == 0:
            return chapter.unlock_condition
        previous_stage_id = chapter_stage_ids[index - 1]
        return f"需先通关 {previous_stage_id}"

    def is_chapter_unlocked(self, player: PlayerData, chapter_id: str) -> bool:
        if chapter_id not in self.chapter_definitions:
            raise ValueError(f"章节不存在：{chapter_id}")
        chapter_ids = self.list_chapter_ids()
        index = chapter_ids.index(chapter_id)
        if index == 0:
            return True
        previous_chapter_id = chapter_ids[index - 1]
        return self.is_chapter_completed(player, previous_chapter_id)

    def chapter_unlock_reason(self, player: PlayerData, chapter_id: str) -> str | None:
        if self.is_chapter_unlocked(player, chapter_id):
            return None
        return self.chapter_definitions[chapter_id].unlock_condition

    def is_chapter_completed(self, player: PlayerData, chapter_id: str) -> bool:
        stage_ids = self.list_stage_ids_in_chapter(chapter_id)
        return bool(stage_ids) and all(player.stage_progress.get(stage_id, {}).get("completed", False) for stage_id in stage_ids)

    def complete_stage(self, player: PlayerData, stage_id: str, stars: int) -> dict[str, int]:
        definition = self.stage_definitions[stage_id]
        entry = player.stage_progress.setdefault(stage_id, {"completed": False, "stars": 0})
        entry["completed"] = True
        entry["stars"] = max(entry["stars"], stars)
        for currency, amount in definition.rewards.items():
            player.profile.currencies[currency] = player.profile.currencies.get(currency, 0) + amount
        return dict(definition.rewards)

    def can_sweep_stage(self, player: PlayerData, stage_id: str) -> bool:
        return bool(player.stage_progress.get(stage_id, {}).get("completed", False))

    def sweep_stage(self, player: PlayerData, stage_id: str) -> dict[str, int]:
        if stage_id not in self.stage_definitions:
            raise ValueError(f"关卡不存在：{stage_id}")
        if not self.can_sweep_stage(player, stage_id):
            raise ValueError(f"关卡尚未通关，不能扫荡：{stage_id}")
        definition = self.stage_definitions[stage_id]
        for currency, amount in definition.rewards.items():
            player.profile.currencies[currency] = player.profile.currencies.get(currency, 0) + amount
        return dict(definition.rewards)

    def best_stage_id(self, player: PlayerData) -> str | None:
        completed = [stage_id for stage_id, state in player.stage_progress.items() if state.get("completed")]
        return sorted(completed, key=self.stage_sort_key)[-1] if completed else None

    def current_chapter_id(self, player: PlayerData) -> str | None:
        if self.chapter_definitions:
            completed = [stage_id for stage_id, state in player.stage_progress.items() if state.get("completed")]
            if completed:
                return self.chapter_id_from_stage_id(sorted(completed, key=self.stage_sort_key)[-1])
            return self.list_chapter_ids()[0]
        return None

    def resolve_chapter_id(self, chapter_ref: str) -> str:
        normalized = chapter_ref.strip()
        if not normalized:
            raise ValueError("章节标识不可为空")
        chapter_id = self._normalize_chapter_id(normalized)
        if chapter_id not in self.chapter_definitions:
            raise ValueError(f"章节不存在或暂无关卡配置：{chapter_id}")
        return chapter_id

    def list_stage_ids_in_chapter(self, chapter_ref: str) -> list[str]:
        chapter_id = self._normalize_chapter_id(chapter_ref.strip())
        chapter = self.chapter_definitions.get(chapter_id)
        return list(chapter.stage_ids) if chapter is not None else []

    def list_chapter_ids(self) -> list[str]:
        return sorted(self.chapter_definitions, key=self.chapter_sort_key)

    def build_stage_enemy_team(self, stage_id: str, hero_templates: list[HeroData]) -> tuple[list[HeroData], dict[int, str]]:
        definition = self.stage_definitions[stage_id]
        template_index = {hero.id: hero for hero in hero_templates}
        enemy_heroes: list[HeroData] = []
        enemy_formation: dict[int, str] = {}
        if definition.enemy_seed is not None or not definition.enemy_formation:
            selected_templates = self._build_seeded_enemy_templates(definition, hero_templates)
            for position, template in zip(range(1, definition.enemy_team_size + 1), selected_templates, strict=False):
                enemy = self.hero_service.create_stage_enemy_from_template(
                    template,
                    stage_id=stage_id,
                    position=position,
                    level=definition.enemy_level,
                    stat_multiplier=definition.enemy_stat_multiplier,
                )
                enemy_heroes.append(enemy)
                enemy_formation[position] = enemy.id
            return enemy_heroes, enemy_formation
        for position, hero_id in sorted(definition.enemy_formation.items()):
            template = template_index.get(hero_id)
            if template is None:
                raise ValueError(f"关卡 {stage_id} 配置了不存在的敌方武将：{hero_id}")
            enemy = self.hero_service.create_stage_enemy_from_template(
                template,
                stage_id=stage_id,
                position=position,
                level=definition.enemy_level,
                stat_multiplier=definition.enemy_stat_multiplier,
            )
            enemy_heroes.append(enemy)
            enemy_formation[position] = enemy.id
        return enemy_heroes, enemy_formation

    def _build_seeded_enemy_templates(self, definition: StageDefinition, hero_templates: list[HeroData]) -> list[HeroData]:
        rng = self._build_stage_rng(definition)
        quality_pools: dict[HeroQuality, list[HeroData]] = {
            quality: sorted(
                [hero for hero in hero_templates if hero.hero_quality == quality],
                key=lambda hero: hero.id,
            )
            for quality in HeroQuality
        }
        regular_pool = [
            *quality_pools.get(HeroQuality.A, []),
            *quality_pools.get(HeroQuality.B, []),
        ]
        if not regular_pool:
            raise ValueError("缺少 A/B 品质敌军武将池，无法生成关卡敌军")

        selected: list[HeroData] = []
        if definition.stage_order % 5 == 0:
            s_plus_pool = quality_pools.get(HeroQuality.S_PLUS, [])
            s_pool = quality_pools.get(HeroQuality.S, [])
            if not s_plus_pool or len(s_pool) < 2:
                raise ValueError("缺少足够的 S / S+ 武将池，无法生成第 5 关首领阵容")
            selected.extend(self._pick_unique_templates(s_plus_pool, 1, rng))
            selected.extend(self._pick_unique_templates(s_pool, 2, rng))
            selected.extend(self._pick_unique_templates(regular_pool, max(0, definition.enemy_team_size - len(selected)), rng))
        else:
            selected.extend(self._pick_unique_templates(regular_pool, definition.enemy_team_size, rng))

        rng.shuffle(selected)
        return selected[: definition.enemy_team_size]

    @staticmethod
    def _build_stage_rng(definition: StageDefinition) -> random.Random:
        seed_text = f"{definition.enemy_seed if definition.enemy_seed is not None else definition.stage_id}:{definition.stage_order}:{definition.enemy_team_size}"
        digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    @staticmethod
    def _pick_unique_templates(pool: list[HeroData], count: int, rng: random.Random) -> list[HeroData]:
        if count <= 0:
            return []
        if not pool:
            raise ValueError("敌军武将池为空，无法生成阵容")
        if count <= len(pool):
            return list(rng.sample(pool, count))
        picked = list(pool)
        while len(picked) < count:
            picked.append(rng.choice(pool))
        rng.shuffle(picked)
        return picked[:count]

    @classmethod
    def stage_sort_key(cls, stage_id: str) -> tuple[int, int, str]:
        match = cls.STAGE_ID_PATTERN.match(stage_id)
        if match is None:
            return (10**9, 10**9, stage_id)
        return (int(match.group(1)), int(match.group(2)), stage_id)

    @classmethod
    def chapter_id_from_stage_id(cls, stage_id: str) -> str:
        match = cls.STAGE_ID_PATTERN.match(stage_id)
        if match is None:
            raise ValueError(f"无法从关卡ID解析章节：{stage_id}")
        return f"chapter_{int(match.group(1))}"

    @classmethod
    def chapter_sort_key(cls, chapter_id: str) -> tuple[int, str]:
        match = cls.CHAPTER_ID_PATTERN.match(chapter_id)
        if match is None:
            return (10**9, chapter_id)
        return (int(match.group(1)), chapter_id)

    @classmethod
    def _normalize_chapter_id(cls, chapter_ref: str) -> str:
        if chapter_ref.startswith("stage_"):
            return cls.chapter_id_from_stage_id(chapter_ref)
        if chapter_ref.startswith("chapter_"):
            return chapter_ref
        if chapter_ref.isdigit():
            return f"chapter_{int(chapter_ref)}"
        raise ValueError(f"无法识别章节标识：{chapter_ref}")

    def _prepare_chapter_definitions(self, chapter_definitions: dict[str, ChapterDefinition] | None) -> dict[str, ChapterDefinition]:
        if chapter_definitions:
            return {
                chapter_id: ChapterDefinition(
                    chapter_id=chapter.chapter_id,
                    name=chapter.name,
                    unlock_condition=chapter.unlock_condition,
                    stage_ids=list(chapter.stage_ids),
                )
                for chapter_id, chapter in sorted(chapter_definitions.items(), key=lambda item: self.chapter_sort_key(item[0]))
            }
        derived: dict[str, ChapterDefinition] = {}
        for stage_id in sorted(self.stage_definitions, key=self.stage_sort_key):
            chapter_id = self.chapter_id_from_stage_id(stage_id)
            chapter = derived.setdefault(
                chapter_id,
                ChapterDefinition(
                    chapter_id=chapter_id,
                    name=chapter_id,
                    unlock_condition="默认解锁" if not derived else f"通关上一章节全部关卡后解锁 {chapter_id}",
                    stage_ids=[],
                ),
            )
            chapter.stage_ids.append(stage_id)
        return derived


class IdleRewardService:
    MAX_IDLE_HOURS = 8
    QUICK_IDLE_COUNT = 3
    QUICK_IDLE_HOURS = 2

    def capped_seconds(self, offline_seconds: int) -> int:
        return min(max(0, int(offline_seconds)), self.MAX_IDLE_HOURS * 3600)

    def calculate_rewards(self, idle_rewards_per_hour: dict[str, int], offline_seconds: int) -> dict[str, int]:
        capped_seconds = self.capped_seconds(offline_seconds)
        ratio = capped_seconds / 3600
        return {
            key: amount
            for key, value in idle_rewards_per_hour.items()
            if (amount := int(value * ratio)) > 0
        }

    def quick_idle_rewards(self, idle_rewards_per_hour: dict[str, int]) -> dict[str, int]:
        return {
            key: amount
            for key, value in idle_rewards_per_hour.items()
            if (amount := value * self.QUICK_IDLE_HOURS) > 0
        }


class StaminaService:
    MAX_STAMINA = 100
    RECOVER_INTERVAL_MINUTES = 6
    PURCHASE_LIMIT = 5
    CHALLENGE_COST = 5

    def recover(self, current: int, minutes_offline: int) -> int:
        recovered = minutes_offline // self.RECOVER_INTERVAL_MINUTES
        return min(self.MAX_STAMINA, current + recovered)

    def recover_with_elapsed_seconds(self, current: int, elapsed_seconds: int) -> StaminaRecoveryResult:
        normalized_current = max(0, min(self.MAX_STAMINA, int(current)))
        if normalized_current >= self.MAX_STAMINA:
            return StaminaRecoveryResult(stamina=self.MAX_STAMINA, recovered=0, consumed_seconds=0, next_recovery_seconds=None)

        interval_seconds = self.RECOVER_INTERVAL_MINUTES * 60
        normalized_elapsed = max(0, int(elapsed_seconds))
        recovered_attempt = normalized_elapsed // interval_seconds
        stamina = min(self.MAX_STAMINA, normalized_current + recovered_attempt)
        recovered = stamina - normalized_current
        if stamina >= self.MAX_STAMINA:
            next_recovery_seconds = None
        else:
            remainder = normalized_elapsed % interval_seconds
            next_recovery_seconds = interval_seconds - remainder if remainder else interval_seconds
        return StaminaRecoveryResult(
            stamina=stamina,
            recovered=recovered,
            consumed_seconds=recovered * interval_seconds,
            next_recovery_seconds=next_recovery_seconds,
        )

    def consume_for_stage(self, current: int) -> int:
        if current < self.CHALLENGE_COST:
            raise ValueError("体力不足")
        return current - self.CHALLENGE_COST

    def purchase_cost(self, purchase_times_today: int) -> int:
        if purchase_times_today >= self.PURCHASE_LIMIT:
            raise ValueError("今日购买次数已达上限")
        return 50 + purchase_times_today * 50


class AutoSavePolicy:
    AUTO_SAVE_INTERVAL_SECONDS = 300

    def should_auto_save(self, last_saved_at: datetime | None, now: datetime | None = None) -> bool:
        if last_saved_at is None:
            return True
        current = now or TimeUtils.utcnow()
        return (current - last_saved_at).total_seconds() >= self.AUTO_SAVE_INTERVAL_SECONDS

