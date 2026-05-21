from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from game.battle.engine import BattleEngine, BattleResult
from game.data.models import FormationData, HeroData, HeroStats, PlayerData, hero_from_dict
from game.develop.hero_service import HeroDevelopmentService
from game.gameplay.services import AutoSavePolicy, CampaignService, ChapterDefinition, FormationService, IdleRewardService, StageBattlePreparation, StageDefinition, StaminaRecoveryResult, StaminaService
from game.managers.runtime import EventManager, GameManager, ResourceManager, SaveManager, TimeManager, UIManager
from game.storage.repository import ConfigLoader, MigrationManager, SaveRepository, SQLiteRepository
from game.ui.console import BattleConsoleView, ConsoleAppView
from game.utility.random_utils import RandomService
from game.utility.time_utils import TimeUtils


@dataclass(slots=True)
class GameConfig:
    project_root: Path
    config_dir: Path
    save_dir: Path
    database_path: Path
    save_secret: str = "happy-sanguo-local-secret"

    @classmethod
    def from_project_root(cls, project_root: Path) -> "GameConfig":
        return cls(
            project_root=project_root,
            config_dir=project_root / "assets" / "config",
            save_dir=project_root / "runtime" / "saves",
            database_path=project_root / "runtime" / "game.db",
        )


@dataclass(slots=True)
class GameState:
    player: PlayerData | None = None
    current_slot: int = 1
    last_saved_at: datetime | None = None
    battle_speed: int = 1
    auto_battle: bool = True
    debug_flags: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillLevelOverview:
    slot_key: str
    skill_name: str
    skill_type: str
    level: int
    locked_by_rare_treasure: bool
    needs_rare_treasure_for_level_four: bool


@dataclass(slots=True)
class HeroSkillOverview:
    hero_id: str
    template_id: str
    hero_name: str
    camp: str
    profession: str
    role: str
    hero_quality: str
    hero_level_cap: int
    awakening_level: str
    awakening_color: str
    hero_level: int
    base_power: int
    final_power: int
    base_stats: HeroStats
    final_stats: HeroStats
    has_rare_treasure: bool
    rare_treasure_locked_skill_slots: list[str]
    obtained_from: str
    acquired_at: str
    skills: list[SkillLevelOverview]


@dataclass(slots=True)
class HeroCardOverview:
    hero_id: str
    template_id: str
    hero_name: str
    camp: str
    role: str
    hero_quality: str
    awakening_level: str
    awakening_color: str
    hero_level: int
    has_rare_treasure: bool
    is_visible: bool
    obtained_from: str
    acquired_at: str


@dataclass(slots=True)
class HeroLevelUpResult:
    hero_id: str
    template_id: str
    hero_name: str
    old_level: int
    new_level: int
    level_cap: int
    requested_levels: int
    actual_levels: int
    spent_hero_exp: int
    spent_copper: int
    remaining_hero_exp: int
    remaining_copper: int
    power_before: int
    power_after: int
    battle_skill_level_before: int
    battle_skill_level_after: int


@dataclass(slots=True)
class SummonResult:
    summon_type: str
    count: int
    spent_currency: str
    spent_amount: int
    remaining_currency: int
    power_before: int
    power_after: int
    heroes: list[HeroCardOverview]


@dataclass(slots=True)
class FormationSlotOverview:
    position: int
    hero_ref: str
    hero_id: str
    template_id: str
    hero_name: str


@dataclass(slots=True)
class FormationOverview:
    formation_id: str
    formation_name: str
    power: int
    slots: list[FormationSlotOverview]


@dataclass(slots=True)
class FormationPresetOverview:
    formation_id: str
    formation_name: str
    power: int
    hero_count: int
    is_active: bool


@dataclass(slots=True)
class StageOverview:
    stage_id: str
    stage_name: str
    chapter_id: str
    chapter_name: str
    chapter_unlocked: bool
    chapter_completed: bool
    chapter_unlock_condition: str
    unlocked: bool
    completed: bool
    stars: int
    recommended_power: int
    current_power: int
    lock_reason: str | None = None


@dataclass(slots=True)
class ResourceOverview:
    stamina: int
    max_stamina: int
    challenge_cost: int
    next_recovery_seconds: int | None
    currencies: dict[str, int]
    stamina_purchase_times_today: int
    stamina_purchase_limit: int
    stamina_purchase_remaining: int
    next_stamina_purchase_cost: int | None
    quick_idle_used_today: int
    quick_idle_limit: int
    quick_idle_remaining: int
    quick_idle_hours: int
    idle_stage_id: str | None
    idle_stage_name: str | None
    idle_elapsed_seconds: int
    idle_capped_seconds: int
    idle_rewards_preview: dict[str, int]
    quick_idle_rewards_preview: dict[str, int]


@dataclass(slots=True)
class IdleRewardClaimResult:
    idle_stage_id: str | None
    idle_stage_name: str | None
    idle_elapsed_seconds: int
    idle_capped_seconds: int
    rewards: dict[str, int]


@dataclass(slots=True)
class QuickIdleResult:
    idle_stage_id: str | None
    idle_stage_name: str | None
    rewards: dict[str, int]
    used_today: int
    remaining_times: int


@dataclass(slots=True)
class StaminaPurchaseResult:
    spent_currency: str
    spent_amount: int
    stamina_before: int
    stamina_after: int
    purchase_times_today: int
    remaining_times: int


@dataclass(slots=True)
class StageSweepResult:
    stage_id: str
    stage_name: str
    chapter_id: str
    rewards: dict[str, int]
    stamina_before: int
    stamina_after: int
    challenge_cost: int


@dataclass(slots=True)
class ChapterSweepResult:
    chapter_id: str
    stage_results: list[StageSweepResult]
    total_rewards: dict[str, int]
    stamina_before: int
    stamina_after: int
    attempted_stage_ids: list[str]
    remaining_stage_ids: list[str]


@dataclass(slots=True)
class SaveSlotOverview:
    slot: int
    path: str
    exists: bool
    is_current: bool
    player_name: str | None = None
    player_level: int | None = None
    power: int | None = None
    hero_count: int | None = None
    error: str | None = None


@dataclass(slots=True)
class SettingsOverview:
    battle_speed: int
    auto_battle: bool
    current_slot: int


class GameApplication:
    """首版单机框架应用入口。"""

    ACTIVE_FORMATION_SETTING = "active_formation_id"
    SUMMON_SINGLE_COST = 300
    SUMMON_TEN_COST = 2700
    SUMMON_POOL_NAME = "元宝招募"
    SUMMON_QUALITY_WEIGHTS = {
        "S": 0.8,
        "S+": 0.2,
    }

    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self.state = GameState()
        self.game_manager = GameManager()
        self.event_manager = EventManager()
        self.time_manager = TimeManager()
        self.ui_manager = UIManager()
        self.resource_manager = ResourceManager()
        self.save_manager = SaveManager()
        self.console_view = ConsoleAppView()
        self.battle_view = BattleConsoleView()
        self.auto_save_policy = AutoSavePolicy()
        self.battle_engine = BattleEngine()
        self.random_service = RandomService()
        self.hero_service = HeroDevelopmentService()
        self.formation_service = FormationService()
        self.idle_reward_service = IdleRewardService()
        self.stamina_service = StaminaService()
        self.migration_manager = MigrationManager()
        self.config_loader = ConfigLoader(self.config.config_dir)
        self.sqlite_repository = SQLiteRepository(self.config.database_path)
        self.save_repository = SaveRepository(self.config.save_dir, secret=self.config.save_secret, migration_manager=self.migration_manager)
        self.save_manager.bind_repository(self.save_repository)
        self._register_services()

    def initialize(self) -> None:
        self._bootstrap_database()
        self._bootstrap_player()
        self.time_manager.register_repeating_task("auto_save", AutoSavePolicy.AUTO_SAVE_INTERVAL_SECONDS, self.auto_save)
        self.game_manager.initialize()
        self.event_manager.publish("game.initialized", {"player_name": self.state.player.profile.name})
        self.ui_manager.show_message("游戏框架初始化完成")

    def run_battle_demo(self) -> BattleResult:
        heroes = self.load_heroes()
        stages = self.load_stages()
        ally_pool = heroes[:3]
        for hero in ally_pool:
            hero.metadata["start_energy"] = 100
        ally_formation = {1: ally_pool[0].id, 2: ally_pool[1].id, 4: ally_pool[2].id}
        campaign_service = self._build_campaign_service(stages)
        enemy_pool, enemy_formation = campaign_service.build_stage_enemy_team("stage_1-1", heroes)
        for hero in enemy_pool:
            hero.metadata["start_energy"] = 100
        result = self.battle_engine.run_battle(ally_pool, ally_formation, enemy_pool, enemy_formation, rewards=stages["stage_1-1"].rewards)
        self.event_manager.publish("battle.completed", {"winner": result.winner, "rounds": result.rounds})
        if result.winner == "ally":
            self.complete_stage("stage_1-1", result.stars)
        return result

    def complete_stage(self, stage_id: str, stars: int) -> dict[str, int]:
        return self._complete_stage(stage_id, stars)

    def _complete_stage(self, stage_id: str, stars: int, *, now: datetime | None = None, auto_save: bool = True) -> dict[str, int]:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        campaign_service = self._build_campaign_service()
        previous_best_stage_id = campaign_service.best_stage_id(player)
        previous_unlocked_chapters = {chapter_id for chapter_id in campaign_service.list_chapter_ids() if campaign_service.is_chapter_unlocked(player, chapter_id)}
        rewards = campaign_service.complete_stage(player, stage_id, stars)
        if campaign_service.best_stage_id(player) != previous_best_stage_id:
            player.idle_last_claimed_at = self._serialize_datetime(current)
        newly_unlocked = [chapter_id for chapter_id in campaign_service.list_chapter_ids() if chapter_id not in previous_unlocked_chapters and campaign_service.is_chapter_unlocked(player, chapter_id)]
        for chapter_id in newly_unlocked:
            chapter = campaign_service.chapter_definitions[chapter_id]
            self.event_manager.publish("chapter.unlocked", {"chapter_id": chapter_id, "chapter_name": chapter.name})
            self.ui_manager.show_message(f"已解锁新章节：{chapter.name} ({chapter_id})")
        self.state.player.profile.power = self.calculate_player_power()
        self.event_manager.publish("stage.completed", {"stage_id": stage_id, "stars": stars, "rewards": rewards})
        if auto_save:
            self.auto_save()
        return rewards

    def calculate_player_power(self) -> int:
        if not self.state.player:
            return 0
        formation = self.get_active_formation()
        if formation is None:
            return 0
        return self.formation_service.calculate_power(formation, self.state.player.heroes)

    def create_new_player(self) -> PlayerData:
        now = TimeUtils.utcnow()
        templates = self.load_heroes()[:3]
        cards = [self.hero_service.create_card_from_template(template, card_id=f"{template.id}_starter") for template in templates]
        formation = FormationData(id="formation_1", name="初始阵容", positions={1: templates[0].template_id, 2: templates[1].template_id, 4: templates[2].template_id})
        player = PlayerData(
            id="player_1",
            heroes=cards,
            formations=[formation],
            stamina=self.stamina_service.MAX_STAMINA,
            stamina_last_updated_at=self._serialize_datetime(now),
            idle_last_claimed_at=self._serialize_datetime(now),
            daily_reset_at=self._serialize_datetime(now),
        )
        player.settings[self.ACTIVE_FORMATION_SETTING] = formation.id
        player.profile.power = self.formation_service.calculate_power(formation, cards)
        return player

    def get_active_formation(self) -> FormationData | None:
        if not self.state.player:
            return None
        self._ensure_player_formations(self.state.player)
        active_formation_id = self.state.player.settings.get(self.ACTIVE_FORMATION_SETTING)
        return next((formation for formation in self.state.player.formations if formation.id == active_formation_id), self.state.player.formations[0])

    def list_formation_presets(self) -> list[FormationData]:
        if not self.state.player:
            return []
        self._ensure_player_formations(self.state.player)
        return list(self.state.player.formations)

    def list_formation_preset_overviews(self) -> list[FormationPresetOverview]:
        player = self._require_player()
        active = self.get_active_formation()
        active_id = active.id if active is not None else ""
        return [
            FormationPresetOverview(
                formation_id=formation.id,
                formation_name=formation.name,
                power=self.formation_service.calculate_power(formation, player.heroes),
                hero_count=len([hero_ref for hero_ref in formation.positions.values() if hero_ref]),
                is_active=formation.id == active_id,
            )
            for formation in player.formations
        ]

    def switch_formation_preset(self, formation_id: str) -> FormationData:
        if not self.state.player:
            raise ValueError("当前没有可切换阵容的玩家数据")
        self._ensure_player_formations(self.state.player)
        formation = next((item for item in self.state.player.formations if item.id == formation_id), None)
        if formation is None:
            raise ValueError(f"阵容方案不存在：{formation_id}")
        self.state.player.settings[self.ACTIVE_FORMATION_SETTING] = formation.id
        self.state.player.profile.power = self.calculate_player_power()
        self.auto_save()
        return formation

    def save_formation_preset(self, formation_id: str, positions: dict[int, str], *, name: str | None = None) -> FormationData:
        if not self.state.player:
            raise ValueError("当前没有可编辑阵容的玩家数据")
        self._ensure_player_formations(self.state.player)
        formation = next((item for item in self.state.player.formations if item.id == formation_id), None)
        if formation is None:
            if len(self.state.player.formations) >= FormationService.MAX_PRESETS:
                raise ValueError(f"阵容方案最多保存 {FormationService.MAX_PRESETS} 套")
            formation = FormationData(id=formation_id, name=name or f"阵容{len(self.state.player.formations) + 1}", positions=dict(positions))
            self.state.player.formations.append(formation)
        else:
            formation.positions = dict(positions)
            if name is not None:
                formation.name = name
        self.formation_service.validate_or_raise(formation, self.state.player.heroes)
        self.formation_service.validate_player_formations(self.state.player)
        if not self.state.player.settings.get(self.ACTIVE_FORMATION_SETTING):
            self.state.player.settings[self.ACTIVE_FORMATION_SETTING] = formation.id
        self.state.player.profile.power = self.calculate_player_power()
        self.auto_save()
        return formation

    def deploy_hero_to_active_formation(self, position: int, hero_ref: str) -> FormationData:
        if not self.state.player:
            raise ValueError("当前没有可编辑阵容的玩家数据")
        formation = self.get_active_formation()
        if formation is None:
            raise ValueError("当前没有可编辑的活动阵容")
        self.formation_service.deploy_hero(formation, self.state.player.heroes, position, hero_ref)
        self.formation_service.validate_player_formations(self.state.player)
        self.state.player.profile.power = self.calculate_player_power()
        self.auto_save()
        return formation

    def undeploy_hero_from_active_formation(self, position: int) -> FormationData:
        if not self.state.player:
            raise ValueError("当前没有可编辑阵容的玩家数据")
        formation = self.get_active_formation()
        if formation is None:
            raise ValueError("当前没有可编辑的活动阵容")
        self.formation_service.undeploy_hero(formation, position)
        self.formation_service.validate_player_formations(self.state.player)
        self.state.player.profile.power = self.calculate_player_power()
        self.auto_save()
        return formation

    def swap_active_formation_positions(self, left_position: int, right_position: int) -> FormationData:
        if not self.state.player:
            raise ValueError("当前没有可编辑阵容的玩家数据")
        formation = self.get_active_formation()
        if formation is None:
            raise ValueError("当前没有可编辑的活动阵容")
        self.formation_service.swap_positions(formation, left_position, right_position)
        self.formation_service.validate_player_formations(self.state.player)
        self.state.player.profile.power = self.calculate_player_power()
        self.auto_save()
        return formation

    def get_visible_player_heroes(self) -> list[HeroData]:
        if not self.state.player:
            return []
        return self.hero_service.visible_heroes(self.state.player.heroes)

    def list_visible_hero_skill_overviews(self) -> list[HeroSkillOverview]:
        player = self._require_player()
        return [self._build_hero_skill_overview(hero) for hero in self.hero_service.visible_heroes(player.heroes)]

    def get_hero_skill_overview(self, hero_ref: str) -> HeroSkillOverview:
        player = self._require_player()
        hero = self.hero_service.resolve_best_card(player.heroes, hero_ref)
        if hero is None:
            raise ValueError(f"武将不存在：{hero_ref}")
        return self._build_hero_skill_overview(hero)

    def activate_rare_treasure(self, hero_ref: str) -> HeroData:
        player = self._require_player()
        hero = self.hero_service.resolve_best_card(player.heroes, hero_ref)
        if hero is None:
            raise ValueError(f"武将不存在：{hero_ref}")
        hero.has_rare_treasure = True
        hero.refresh_structured_progression()
        self.state.player.profile.power = self.calculate_player_power()
        self.event_manager.publish("hero.rare_treasure.activated", {"hero_id": hero.id, "template_id": hero.template_id, "locked_skill_slots": list(hero.rare_treasure_locked_skill_slots)})
        self.ui_manager.show_message(f"{hero.name} 已激活奇珍，四个技能均可升到 4 级")
        self.auto_save()
        return hero

    def upgrade_hero_level(self, hero_ref: str, *, levels: int = 1, use_max: bool = False) -> HeroLevelUpResult:
        player = self._require_player()
        hero = self.hero_service.resolve_best_card(player.heroes, hero_ref)
        if hero is None:
            raise ValueError(f"武将不存在：{hero_ref}")
        if not use_max and levels <= 0:
            raise ValueError("升级级数必须大于 0")
        if hero.level >= hero.hero_quality.level_cap:
            raise ValueError(f"{hero.name} 已达到等级上限 {hero.hero_quality.level_cap}")

        old_level = hero.level
        power_before = self.calculate_player_power()
        battle_skill_level_before = self.hero_service.resolve_base_skill_level(hero)
        available_hero_exp = player.profile.currencies.get("武将经验", 0)
        available_copper = player.profile.currencies.get("铜币", 0)
        plan = self.hero_service.plan_level_ups(
            hero,
            available_hero_exp=available_hero_exp,
            available_copper=available_copper,
            requested_levels=None if use_max else levels,
        )
        if plan.actual_levels <= 0:
            next_exp, next_copper = self.hero_service.level_up_cost(hero)
            raise ValueError(f"资源不足，{hero.name} 下一级需要 {next_exp} 武将经验、{next_copper} 铜币")

        self.hero_service.level_up(hero, plan.actual_levels)
        player.profile.currencies["武将经验"] = max(0, available_hero_exp - plan.spent_hero_exp)
        player.profile.currencies["铜币"] = max(0, available_copper - plan.spent_copper)
        self.state.player.profile.power = self.calculate_player_power()
        battle_skill_level_after = self.hero_service.resolve_base_skill_level(hero)
        power_after = self.state.player.profile.power

        self.event_manager.publish(
            "hero.level_up",
            {
                "hero_id": hero.id,
                "template_id": hero.template_id,
                "old_level": old_level,
                "new_level": hero.level,
                "actual_levels": plan.actual_levels,
                "spent_hero_exp": plan.spent_hero_exp,
                "spent_copper": plan.spent_copper,
            },
        )
        message = (
            f"{hero.name} 升级成功：Lv.{old_level} -> Lv.{hero.level}，"
            f"消耗 {plan.spent_hero_exp} 武将经验 / {plan.spent_copper} 铜币"
        )
        if not use_max and plan.actual_levels < plan.requested_levels:
            message += "（受当前资源限制，已升级至本次可达上限）"
        if battle_skill_level_after > battle_skill_level_before:
            message += f"，战斗技能档位提升至 Lv.{battle_skill_level_after}"
        self.ui_manager.show_message(message)
        self.auto_save()
        return HeroLevelUpResult(
            hero_id=hero.id,
            template_id=hero.template_id,
            hero_name=hero.name,
            old_level=old_level,
            new_level=hero.level,
            level_cap=hero.hero_quality.level_cap,
            requested_levels=plan.requested_levels,
            actual_levels=plan.actual_levels,
            spent_hero_exp=plan.spent_hero_exp,
            spent_copper=plan.spent_copper,
            remaining_hero_exp=player.profile.currencies.get("武将经验", 0),
            remaining_copper=player.profile.currencies.get("铜币", 0),
            power_before=power_before,
            power_after=power_after,
            battle_skill_level_before=battle_skill_level_before,
            battle_skill_level_after=battle_skill_level_after,
        )

    def summon_heroes(self, *, count: int = 1) -> SummonResult:
        player = self._require_player()
        if count not in {1, 10}:
            raise ValueError("当前仅支持单抽或十连招募")
        cost = self.SUMMON_SINGLE_COST if count == 1 else self.SUMMON_TEN_COST
        currency_name = "元宝"
        current_currency = player.profile.currencies.get(currency_name, 0)
        if current_currency < cost:
            raise ValueError(f"元宝不足，{count} 连招募需要 {cost} 元宝")

        templates = self.load_heroes()
        quality_pool: dict[str, list[HeroData]] = {}
        for hero in templates:
            quality_pool.setdefault(hero.hero_quality.value, []).append(hero)
        available_quality_weights = [
            (quality, weight)
            for quality, weight in self.SUMMON_QUALITY_WEIGHTS.items()
            if quality_pool.get(quality)
        ]
        if not available_quality_weights:
            raise ValueError("当前没有可用的招募武将池")

        power_before = self.calculate_player_power()
        summoned_cards: list[HeroData] = []
        for _ in range(count):
            quality = self.random_service.weighted_choice(available_quality_weights)
            template = self.random_service.choice(quality_pool[quality])
            card = self.hero_service.create_card_from_template(template, obtained_from="summon")
            player.heroes.append(card)
            summoned_cards.append(card)

        player.profile.currencies[currency_name] = current_currency - cost
        self.state.player.profile.power = self.calculate_player_power()
        power_after = self.state.player.profile.power
        visible_ids = {hero.id for hero in self.hero_service.visible_heroes(player.heroes)}
        summoned_overviews = [
            self._build_hero_card_overview(card, visible_ids=visible_ids)
            for card in summoned_cards
        ]
        self.event_manager.publish(
            "hero.summoned",
            {
                "summon_type": self.SUMMON_POOL_NAME,
                "count": count,
                "spent_currency": currency_name,
                "spent_amount": cost,
                "hero_ids": [hero.id for hero in summoned_cards],
                "template_ids": [hero.template_id for hero in summoned_cards],
            },
        )
        self.ui_manager.show_message(
            f"已完成{count}次{self.SUMMON_POOL_NAME}，消耗 {cost} 元宝，获得：{', '.join(hero.hero_name for hero in summoned_overviews)}"
        )
        self.auto_save()
        return SummonResult(
            summon_type=self.SUMMON_POOL_NAME,
            count=count,
            spent_currency=currency_name,
            spent_amount=cost,
            remaining_currency=player.profile.currencies.get(currency_name, 0),
            power_before=power_before,
            power_after=power_after,
            heroes=summoned_overviews,
        )

    def get_active_formation_overview(self) -> FormationOverview:
        player = self._require_player()
        formation = self.get_active_formation()
        if formation is None:
            raise ValueError("当前没有活动阵容")
        slots: list[FormationSlotOverview] = []
        for position, hero_ref in sorted(formation.positions.items()):
            hero = self.hero_service.resolve_best_card(player.heroes, hero_ref)
            if hero is None:
                continue
            slots.append(FormationSlotOverview(position=position, hero_ref=hero_ref, hero_id=hero.id, template_id=hero.template_id, hero_name=hero.name))
        return FormationOverview(formation_id=formation.id, formation_name=formation.name, power=self.formation_service.calculate_power(formation, player.heroes), slots=slots)

    def get_resource_overview(self, *, now: datetime | None = None) -> ResourceOverview:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        recovery = self._refresh_player_timed_state(player, current)
        return self._build_resource_overview(player, current, recovery)

    def claim_idle_rewards(self, *, now: datetime | None = None) -> IdleRewardClaimResult:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        self._refresh_player_timed_state(player, current)
        idle_stage_id, idle_stage, idle_elapsed_seconds, idle_capped_seconds, rewards = self._get_idle_reward_snapshot(player, current)
        if idle_stage is None:
            self.ui_manager.show_message("当前尚未通关任何主线关卡，暂无挂机收益可领取")
            return IdleRewardClaimResult(
                idle_stage_id=None,
                idle_stage_name=None,
                idle_elapsed_seconds=0,
                idle_capped_seconds=0,
                rewards={},
            )

        self._grant_rewards(player, rewards)
        player.idle_last_claimed_at = self._serialize_datetime(current)
        if rewards:
            self.ui_manager.show_message(f"已领取挂机收益：{rewards}")
        else:
            self.ui_manager.show_message("当前挂机时间不足，暂无可领取收益")
        self.auto_save()
        return IdleRewardClaimResult(
            idle_stage_id=idle_stage_id,
            idle_stage_name=idle_stage.name,
            idle_elapsed_seconds=idle_elapsed_seconds,
            idle_capped_seconds=idle_capped_seconds,
            rewards=rewards,
        )

    def quick_idle(self, *, now: datetime | None = None) -> QuickIdleResult:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        self._refresh_player_timed_state(player, current)
        idle_stage_id, idle_stage, _idle_elapsed_seconds, _idle_capped_seconds, _rewards = self._get_idle_reward_snapshot(player, current)
        if idle_stage is None or idle_stage_id is None:
            raise ValueError("当前尚未通关任何主线关卡，暂不可快速挂机")
        if player.quick_idle_used_today >= self.idle_reward_service.QUICK_IDLE_COUNT:
            raise ValueError("今日快速挂机次数已达上限")
        rewards = self.idle_reward_service.quick_idle_rewards(idle_stage.idle_rewards_per_hour)
        self._grant_rewards(player, rewards)
        player.quick_idle_used_today += 1
        remaining_times = max(0, self.idle_reward_service.QUICK_IDLE_COUNT - player.quick_idle_used_today)
        self.ui_manager.show_message(f"快速挂机 2 小时完成，获得：{rewards}")
        self.auto_save()
        return QuickIdleResult(
            idle_stage_id=idle_stage_id,
            idle_stage_name=idle_stage.name,
            rewards=rewards,
            used_today=player.quick_idle_used_today,
            remaining_times=remaining_times,
        )

    def purchase_stamina(self, *, now: datetime | None = None) -> StaminaPurchaseResult:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        self._refresh_player_timed_state(player, current)
        if player.stamina >= self.stamina_service.MAX_STAMINA:
            raise ValueError("体力已满，无需购买")
        cost = self.stamina_service.purchase_cost(player.stamina_purchase_times_today)
        currency_name = "元宝"
        current_currency = player.profile.currencies.get(currency_name, 0)
        if current_currency < cost:
            raise ValueError("元宝不足")
        stamina_before = player.stamina
        player.profile.currencies[currency_name] = current_currency - cost
        player.stamina = min(self.stamina_service.MAX_STAMINA, player.stamina + self.stamina_service.MAX_STAMINA)
        player.stamina_last_updated_at = self._serialize_datetime(current)
        player.stamina_purchase_times_today += 1
        remaining_times = max(0, self.stamina_service.PURCHASE_LIMIT - player.stamina_purchase_times_today)
        self.ui_manager.show_message(
            f"已消耗 {cost} 元宝购买体力，体力 {stamina_before} -> {player.stamina}，今日剩余购买次数 {remaining_times}"
        )
        self.auto_save()
        return StaminaPurchaseResult(
            spent_currency=currency_name,
            spent_amount=cost,
            stamina_before=stamina_before,
            stamina_after=player.stamina,
            purchase_times_today=player.stamina_purchase_times_today,
            remaining_times=remaining_times,
        )

    def sweep_stage(self, stage_id: str, *, now: datetime | None = None) -> StageSweepResult:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        self._refresh_player_timed_state(player, current)
        stages = self.load_stages()
        campaign_service = self._build_campaign_service(stages)
        stage = self._ensure_stage_available(stage_id)
        if not campaign_service.can_sweep_stage(player, stage_id):
            raise ValueError(f"关卡尚未通关，不能扫荡：{stage_id}")

        stamina_before = player.stamina
        player.stamina = self.stamina_service.consume_for_stage(player.stamina)
        player.stamina_last_updated_at = self._serialize_datetime(current)
        rewards = campaign_service.sweep_stage(player, stage_id)
        stamina_after = player.stamina
        chapter_id = campaign_service.chapter_id_from_stage_id(stage_id)
        self.event_manager.publish(
            "stage.swept",
            {
                "stage_id": stage_id,
                "chapter_id": chapter_id,
                "rewards": rewards,
                "stamina_before": stamina_before,
                "stamina_after": stamina_after,
            },
        )
        self.ui_manager.show_message(f"已扫荡 {stage_id}，消耗体力 {self.stamina_service.CHALLENGE_COST}，获得奖励 {rewards}")
        self.auto_save()
        return StageSweepResult(
            stage_id=stage_id,
            stage_name=stage.name,
            chapter_id=chapter_id,
            rewards=rewards,
            stamina_before=stamina_before,
            stamina_after=stamina_after,
            challenge_cost=self.stamina_service.CHALLENGE_COST,
        )

    def sweep_chapter(self, chapter_ref: str | None = None, *, now: datetime | None = None) -> ChapterSweepResult:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        self._refresh_player_timed_state(player, current)
        stages = self.load_stages()
        campaign_service = self._build_campaign_service(stages)
        chapter_id = campaign_service.resolve_chapter_id(chapter_ref) if chapter_ref else campaign_service.current_chapter_id(player)
        if chapter_id is None:
            raise ValueError("当前没有可扫荡的章节")
        if not campaign_service.is_chapter_unlocked(player, chapter_id):
            raise ValueError(f"章节尚未解锁：{chapter_id}")

        chapter_stage_ids = campaign_service.list_stage_ids_in_chapter(chapter_id)
        attempted_stage_ids = [stage_id for stage_id in chapter_stage_ids if campaign_service.can_sweep_stage(player, stage_id)]
        if not attempted_stage_ids:
            raise ValueError(f"{chapter_id} 当前没有已通关关卡可扫荡")

        stamina_before = player.stamina
        stage_results: list[StageSweepResult] = []
        total_rewards: dict[str, int] = {}
        remaining_stage_ids: list[str] = []
        for index, stage_id in enumerate(attempted_stage_ids):
            if player.stamina < self.stamina_service.CHALLENGE_COST:
                remaining_stage_ids = attempted_stage_ids[index:]
                break
            stage = stages[stage_id]
            stage_stamina_before = player.stamina
            player.stamina = self.stamina_service.consume_for_stage(player.stamina)
            rewards = campaign_service.sweep_stage(player, stage_id)
            for currency, amount in rewards.items():
                total_rewards[currency] = total_rewards.get(currency, 0) + amount
            stage_results.append(
                StageSweepResult(
                    stage_id=stage_id,
                    stage_name=stage.name,
                    chapter_id=chapter_id,
                    rewards=rewards,
                    stamina_before=stage_stamina_before,
                    stamina_after=player.stamina,
                    challenge_cost=self.stamina_service.CHALLENGE_COST,
                )
            )
        if not stage_results:
            raise ValueError("体力不足，无法进行章节扫荡")

        player.stamina_last_updated_at = self._serialize_datetime(current)
        self.event_manager.publish(
            "chapter.swept",
            {
                "chapter_id": chapter_id,
                "stage_ids": [item.stage_id for item in stage_results],
                "remaining_stage_ids": remaining_stage_ids,
                "total_rewards": total_rewards,
                "stamina_before": stamina_before,
                "stamina_after": player.stamina,
            },
        )
        self.ui_manager.show_message(
            f"已完成 {chapter_id} 章节扫荡，共扫荡 {len(stage_results)} 关，消耗体力 {stamina_before - player.stamina}，获得奖励 {total_rewards}"
        )
        self.auto_save()
        return ChapterSweepResult(
            chapter_id=chapter_id,
            stage_results=stage_results,
            total_rewards=total_rewards,
            stamina_before=stamina_before,
            stamina_after=player.stamina,
            attempted_stage_ids=attempted_stage_ids,
            remaining_stage_ids=remaining_stage_ids,
        )

    def list_save_slot_overviews(self) -> list[SaveSlotOverview]:
        overviews: list[SaveSlotOverview] = []
        for item in self.save_repository.list_slots():
            summary = item.get("summary", {})
            overviews.append(
                SaveSlotOverview(
                    slot=int(item["slot"]),
                    path=str(item["path"]),
                    exists=bool(item.get("exists", False)),
                    is_current=int(item["slot"]) == self.state.current_slot,
                    player_name=summary.get("name"),
                    player_level=summary.get("level"),
                    power=summary.get("power"),
                    hero_count=summary.get("hero_count"),
                    error=summary.get("error"),
                )
            )
        return overviews

    def save_to_slot(self, slot: int) -> Path:
        player = self._require_player()
        self._ensure_player_formations(player)
        self.formation_service.validate_player_formations(player)
        path = self.save_repository.save(slot, player)
        self.state.current_slot = slot
        self.state.last_saved_at = datetime.now(UTC)
        self.ui_manager.show_message(f"已手动存档到槽位 {slot}")
        return path

    def load_slot(self, slot: int) -> PlayerData:
        existed = (self.config.save_dir / f"slot_{slot}.sav").exists()
        player = self.load_or_create_slot(slot)
        self.state.player = player
        self.state.player.profile.power = self.calculate_player_power()
        self.state.battle_speed = player.settings.get("battle_speed", 1)
        self.state.auto_battle = player.settings.get("auto_battle", True)
        self.ui_manager.show_message(f"已{'加载' if existed else '创建并加载'}槽位 {slot}")
        return player

    def delete_save_slot(self, slot: int) -> None:
        if slot == self.state.current_slot:
            raise ValueError("不能删除当前已加载的存档槽位，请先切换到其他槽位")
        self.save_repository.delete(slot)
        self.ui_manager.show_message(f"已删除槽位 {slot} 的存档")

    def export_save_slot(self, slot: int, destination: Path) -> Path:
        path = self.save_repository.export_slot(slot, destination)
        self.ui_manager.show_message(f"已导出槽位 {slot} 到 {path}")
        return path

    def import_save_slot(self, slot: int, source: Path) -> Path:
        path = self.save_repository.import_slot(slot, source)
        if slot == self.state.current_slot:
            self.load_slot(slot)
        else:
            self.ui_manager.show_message(f"已导入存档到槽位 {slot}")
        return path

    def get_settings_overview(self) -> SettingsOverview:
        self._require_player()
        return SettingsOverview(
            battle_speed=self.state.battle_speed,
            auto_battle=self.state.auto_battle,
            current_slot=self.state.current_slot,
        )

    def set_battle_speed(self, speed: int) -> int:
        if speed not in {1, 2, 3}:
            raise ValueError("战斗速度仅支持 1 / 2 / 3 倍")
        player = self._require_player()
        self.state.battle_speed = speed
        player.settings["battle_speed"] = speed
        self.ui_manager.show_message(f"已将默认战斗速度设置为 {speed} 倍")
        self.auto_save()
        return speed

    def set_auto_battle(self, enabled: bool) -> bool:
        player = self._require_player()
        self.state.auto_battle = enabled
        player.settings["auto_battle"] = enabled
        self.ui_manager.show_message(f"自动战斗已{'开启' if enabled else '关闭'}")
        self.auto_save()
        return enabled

    def toggle_auto_battle(self) -> bool:
        return self.set_auto_battle(not self.state.auto_battle)

    def list_stage_overviews(self, *, now: datetime | None = None) -> list[StageOverview]:
        player = self._require_player()
        self._refresh_player_timed_state(player, now or TimeUtils.utcnow())
        stages = self.load_stages()
        campaign_service = self._build_campaign_service(stages)
        current_power = self.calculate_player_power()
        overviews: list[StageOverview] = []
        for stage_id, stage in sorted(stages.items(), key=lambda item: campaign_service.stage_sort_key(item[0])):
            progress = player.stage_progress.get(stage_id, {})
            chapter_id = campaign_service.chapter_id_from_stage_id(stage_id)
            chapter = campaign_service.chapter_definitions[chapter_id]
            chapter_unlocked = campaign_service.is_chapter_unlocked(player, chapter_id)
            unlocked = campaign_service.is_stage_unlocked(player, stage_id)
            overviews.append(
                StageOverview(
                    stage_id=stage_id,
                    stage_name=stage.name,
                    chapter_id=chapter_id,
                    chapter_name=chapter.name,
                    chapter_unlocked=chapter_unlocked,
                    chapter_completed=campaign_service.is_chapter_completed(player, chapter_id),
                    chapter_unlock_condition=chapter.unlock_condition,
                    unlocked=unlocked,
                    completed=bool(progress.get("completed", False)),
                    stars=int(progress.get("stars", 0)),
                    recommended_power=stage.recommended_power,
                    current_power=current_power,
                    lock_reason=campaign_service.stage_unlock_reason(player, stage_id),
                )
            )
        return overviews

    def list_battle_selectable_heroes(self, stage_id: str) -> list[HeroData]:
        self._require_player()
        self._ensure_stage_available(stage_id)
        return self.get_visible_player_heroes()

    def list_hero_card_overviews(self) -> list[HeroCardOverview]:
        player = self._require_player()
        visible_ids = {hero.id for hero in self.hero_service.visible_heroes(player.heroes)}
        return [
            self._build_hero_card_overview(hero, visible_ids=visible_ids)
            for hero in sorted(
                player.heroes,
                key=lambda item: (item.name, -item.awakening_level.order, -item.level, item.acquired_at, item.id),
            )
        ]

    def fuse_hero_awakening(self, left_id: str, right_id: str) -> HeroData:
        player = self._require_player()
        original_left = next((hero for hero in player.heroes if hero.id == left_id), None)
        original_right = next((hero for hero in player.heroes if hero.id == right_id), None)
        if original_left is None or original_right is None:
            raise ValueError("用于合成的武将卡不存在")
        player.heroes, fused = self.hero_service.fuse_awakening(player.heroes, left_id, right_id)
        for formation in player.formations:
            for position, hero_ref in list(formation.positions.items()):
                if hero_ref in {left_id, right_id}:
                    formation.positions[position] = fused.template_id
        self.formation_service.validate_player_formations(player)
        self.state.player.profile.power = self.calculate_player_power()
        self.event_manager.publish(
            "hero.awakening.fused",
            {
                "template_id": fused.template_id,
                "left_id": left_id,
                "right_id": right_id,
                "awakening_level": fused.awakening_level.value,
            },
        )
        self.ui_manager.show_message(
            f"{fused.name} 觉醒合成成功：{original_left.awakening_level.value} -> {fused.awakening_level.value}（新卡等级重置为 1）"
        )
        self.auto_save()
        return fused

    def open_stage_battle_entry(
        self,
        stage_id: str,
        *,
        formation_id: str | None = None,
        formation_positions: dict[int, str] | None = None,
        now: datetime | None = None,
        refresh_resources: bool = True,
    ) -> StageBattlePreparation:
        player = self._require_player()
        current = now or TimeUtils.utcnow()
        if refresh_resources:
            self._refresh_player_timed_state(player, current)
        formation = self._get_formation_for_battle(formation_id, formation_positions=formation_positions)
        stages = self.load_stages()
        campaign_service = self._build_campaign_service(stages)
        stage = self._ensure_stage_available(stage_id)
        if not campaign_service.is_stage_unlocked(player, stage_id):
            raise ValueError(f"关卡尚未解锁：{stage_id}（{campaign_service.stage_unlock_reason(player, stage_id) or '请先推进主线'}）")
        enemy_heroes, enemy_formation = campaign_service.build_stage_enemy_team(stage_id, self.load_heroes())
        current_power = self.formation_service.calculate_power(formation, player.heroes)
        try:
            self.formation_service.ensure_battle_ready(formation, player.heroes, min_heroes=1, max_heroes=FormationService.MAX_HEROES)
            can_start = True
        except ValueError:
            can_start = False
        return StageBattlePreparation(
            stage_id=stage.stage_id,
            stage_name=stage.name,
            formation_id=formation.id,
            ally_formation=formation,
            selectable_heroes=self.get_visible_player_heroes(),
            enemy_heroes=enemy_heroes,
            enemy_formation=enemy_formation,
            recommended_power=stage.recommended_power,
            current_power=current_power,
            current_stamina=player.stamina,
            challenge_cost=self.stamina_service.CHALLENGE_COST,
            can_start=can_start,
        )

    def start_stage_battle(
        self,
        stage_id: str,
        *,
        formation_id: str | None = None,
        formation_positions: dict[int, str] | None = None,
        now: datetime | None = None,
    ) -> BattleResult:
        current = now or TimeUtils.utcnow()
        player = self._require_player()
        self._refresh_player_timed_state(player, current)
        preparation = self.open_stage_battle_entry(
            stage_id,
            formation_id=formation_id,
            formation_positions=formation_positions,
            now=current,
            refresh_resources=False,
        )
        self.formation_service.ensure_battle_ready(preparation.ally_formation, player.heroes, min_heroes=1, max_heroes=FormationService.MAX_HEROES)
        player.stamina = self.stamina_service.consume_for_stage(player.stamina)
        player.stamina_last_updated_at = self._serialize_datetime(current)
        result = self.battle_engine.run_battle(
            player.heroes,
            preparation.ally_formation.positions,
            preparation.enemy_heroes,
            preparation.enemy_formation,
            rewards=self.load_stages()[stage_id].rewards,
        )
        self.event_manager.publish("battle.completed", {"winner": result.winner, "rounds": result.rounds, "stage_id": stage_id})
        self.ui_manager.show_message(f"挑战 {stage_id} 消耗体力 {self.stamina_service.CHALLENGE_COST}，剩余体力 {player.stamina}")
        if result.winner == "ally":
            self._complete_stage(stage_id, result.stars, now=current, auto_save=False)
        self.auto_save()
        return result

    def load_or_create_slot(self, slot: int = 1) -> PlayerData:
        self.state.current_slot = slot
        try:
            player = self.save_repository.load(slot)
        except FileNotFoundError:
            player = self.create_new_player()
            self.save_repository.save(slot, player)
        self._ensure_player_formations(player)
        self._refresh_player_timed_state(player, TimeUtils.utcnow())
        self.state.player = player
        return player

    def auto_save(self) -> None:
        if not self.state.player:
            return
        self._ensure_player_formations(self.state.player)
        self.formation_service.validate_player_formations(self.state.player)
        self.save_repository.save(self.state.current_slot, self.state.player)
        self.state.last_saved_at = datetime.now(UTC)
        self.ui_manager.show_message(f"自动存档完成：槽位 {self.state.current_slot}")

    def tick(self, delta_seconds: float) -> None:
        self.time_manager.tick(delta_seconds)

    def load_heroes(self) -> list[HeroData]:
        raw_heroes = list(self.config_loader.load("heroes"))
        extra_enemy_hero_path = self.config.config_dir / "enemy_heroes.json"
        if extra_enemy_hero_path.exists():
            raw_heroes.extend(self.config_loader.load("enemy_heroes"))
        return [hero_from_dict(hero) for hero in raw_heroes]

    def load_stages(self) -> dict[str, StageDefinition]:
        raw = self.config_loader.load("stages")
        ordered_stage_ids = [item["stage_id"] for item in sorted(raw, key=lambda entry: CampaignService.stage_sort_key(entry["stage_id"]))]
        stage_order_by_id = {stage_id: index + 1 for index, stage_id in enumerate(ordered_stage_ids)}
        base_stage_exp = 0
        if ordered_stage_ids:
            first_stage = next(item for item in raw if item["stage_id"] == ordered_stage_ids[0])
            base_stage_exp = int((first_stage.get("rewards") or {}).get("武将经验", 0))

        normalized_rewards_by_stage_id: dict[str, dict[str, int]] = {}
        for index, stage_id in enumerate(ordered_stage_ids):
            source = next(item for item in raw if item["stage_id"] == stage_id)
            rewards = dict(source.get("rewards", {}))
            if base_stage_exp > 0:
                rewards["武将经验"] = int(round(base_stage_exp * (1.1**index)))
            normalized_rewards_by_stage_id[stage_id] = rewards

        return {
            item["stage_id"]: StageDefinition(
                stage_id=item["stage_id"],
                name=item["name"],
                enemy_formation={int(key): value for key, value in item.get("enemy_formation", {}).items()},
                recommended_power=item["recommended_power"],
                rewards=normalized_rewards_by_stage_id[item["stage_id"]],
                idle_rewards_per_hour=item["idle_rewards_per_hour"],
                enemy_level=stage_order_by_id[item["stage_id"]],
                enemy_stat_multiplier=item.get("enemy_stat_multiplier", 1.0),
                stage_order=stage_order_by_id[item["stage_id"]],
                enemy_seed=item.get("enemy_seed"),
                enemy_team_size=int(item.get("enemy_team_size", 6) or 6),
            )
            for item in raw
        }

    def load_chapters(self) -> dict[str, ChapterDefinition]:
        raw = self.config_loader.load("chapters")
        return {
            item["chapter_id"]: ChapterDefinition(
                chapter_id=item["chapter_id"],
                name=item["name"],
                unlock_condition=item["unlock_condition"],
                stage_ids=list(item.get("stage_ids", [])),
            )
            for item in raw
        }

    def present_messages(self) -> str:
        return self.console_view.render_messages(self.ui_manager.flush_messages())

    def _build_hero_skill_overview(self, hero: HeroData) -> HeroSkillOverview:
        battle_hero = self.hero_service.prepare_hero_for_battle(hero)
        calculated_stats = self.hero_service.calculate_stats(battle_hero)
        locked_slots = set(hero.rare_treasure_locked_skill_slots)
        skills = [
            SkillLevelOverview(
                slot_key="passive_1",
                skill_name=battle_hero.passive_skills[0].name,
                skill_type=battle_hero.passive_skills[0].skill_type,
                level=battle_hero.passive_skills[0].level,
                locked_by_rare_treasure=("passive_1" in locked_slots and not hero.has_rare_treasure),
                needs_rare_treasure_for_level_four="passive_1" in locked_slots,
            ),
            SkillLevelOverview(
                slot_key="passive_2",
                skill_name=battle_hero.passive_skills[1].name,
                skill_type=battle_hero.passive_skills[1].skill_type,
                level=battle_hero.passive_skills[1].level,
                locked_by_rare_treasure=("passive_2" in locked_slots and not hero.has_rare_treasure),
                needs_rare_treasure_for_level_four="passive_2" in locked_slots,
            ),
            SkillLevelOverview(
                slot_key="passive_3",
                skill_name=battle_hero.passive_skill_3.name,
                skill_type=battle_hero.passive_skill_3.skill_type,
                level=battle_hero.passive_skill_3.level,
                locked_by_rare_treasure=("passive_3" in locked_slots and not hero.has_rare_treasure),
                needs_rare_treasure_for_level_four="passive_3" in locked_slots,
            ),
            SkillLevelOverview(
                slot_key="ultimate",
                skill_name=battle_hero.ultimate_skill.name,
                skill_type=battle_hero.ultimate_skill.skill_type,
                level=battle_hero.ultimate_skill.level,
                locked_by_rare_treasure=("ultimate" in locked_slots and not hero.has_rare_treasure),
                needs_rare_treasure_for_level_four="ultimate" in locked_slots,
            ),
        ]
        return HeroSkillOverview(
            hero_id=hero.id,
            template_id=hero.template_id,
            hero_name=hero.name,
            camp=hero.camp.value,
            profession=hero.profession.value,
            role=hero.role.value,
            hero_quality=hero.hero_quality.value,
            hero_level_cap=hero.hero_quality.level_cap,
            awakening_level=hero.awakening_level.value,
            awakening_color=hero.awakening_level.color,
            hero_level=hero.level,
            base_power=int(calculated_stats.base.attack + calculated_stats.base.hp / 10),
            final_power=int(calculated_stats.final.attack + calculated_stats.final.hp / 10),
            base_stats=calculated_stats.base,
            final_stats=calculated_stats.final,
            has_rare_treasure=hero.has_rare_treasure,
            rare_treasure_locked_skill_slots=list(hero.rare_treasure_locked_skill_slots),
            obtained_from=hero.obtained_from,
            acquired_at=hero.acquired_at,
            skills=skills,
        )

    @staticmethod
    def _build_hero_card_overview(hero: HeroData, *, visible_ids: set[str]) -> HeroCardOverview:
        return HeroCardOverview(
            hero_id=hero.id,
            template_id=hero.template_id,
            hero_name=hero.name,
            camp=hero.camp.value,
            role=hero.role.value,
            hero_quality=hero.hero_quality.value,
            awakening_level=hero.awakening_level.value,
            awakening_color=hero.awakening_level.color,
            hero_level=hero.level,
            has_rare_treasure=hero.has_rare_treasure,
            is_visible=hero.id in visible_ids,
            obtained_from=hero.obtained_from,
            acquired_at=hero.acquired_at,
        )

    def _bootstrap_database(self) -> None:
        self.sqlite_repository.execute(
            "CREATE TABLE IF NOT EXISTS player_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, slot INTEGER NOT NULL, saved_at TEXT NOT NULL, payload_size INTEGER NOT NULL)"
        )

    def _bootstrap_player(self) -> None:
        player = self.load_or_create_slot(1)
        self.state.player = player
        self.state.player.profile.power = self.calculate_player_power()
        self.state.battle_speed = player.settings.get("battle_speed", 1)
        self.state.auto_battle = player.settings.get("auto_battle", True)

    def _ensure_player_formations(self, player: PlayerData) -> None:
        if not player.formations:
            player.formations = [FormationData(id="formation_1", name="默认阵容", positions={})]
        active_formation_id = player.settings.get(self.ACTIVE_FORMATION_SETTING)
        if active_formation_id not in {formation.id for formation in player.formations}:
            player.settings[self.ACTIVE_FORMATION_SETTING] = player.formations[0].id

    def _require_player(self) -> PlayerData:
        if not self.state.player:
            raise ValueError("当前没有玩家数据，请先初始化或读档")
        self._ensure_player_formations(self.state.player)
        return self.state.player

    def _get_formation_for_battle(
        self,
        formation_id: str | None = None,
        *,
        formation_positions: dict[int, str] | None = None,
    ) -> FormationData:
        player = self._require_player()
        if formation_positions is not None:
            return FormationData(id=formation_id or "battle_preview", name="本次出战阵容", positions=dict(formation_positions))
        if formation_id is None:
            formation = self.get_active_formation()
            if formation is None:
                raise ValueError("当前没有可出战的阵容")
            return formation
        formation = next((item for item in player.formations if item.id == formation_id), None)
        if formation is None:
            raise ValueError(f"阵容方案不存在：{formation_id}")
        return formation

    def _ensure_stage_available(self, stage_id: str) -> StageDefinition:
        stages = self.load_stages()
        if stage_id not in stages:
            raise ValueError(f"关卡不存在：{stage_id}")
        return stages[stage_id]

    def _build_campaign_service(self, stages: dict[str, StageDefinition] | None = None) -> CampaignService:
        return CampaignService(stages or self.load_stages(), self.load_chapters())

    def _build_resource_overview(self, player: PlayerData, now: datetime, recovery: StaminaRecoveryResult | None = None) -> ResourceOverview:
        idle_stage_id, idle_stage, idle_elapsed_seconds, idle_capped_seconds, rewards = self._get_idle_reward_snapshot(player, now)
        next_purchase_cost: int | None
        try:
            next_purchase_cost = self.stamina_service.purchase_cost(player.stamina_purchase_times_today)
        except ValueError:
            next_purchase_cost = None
        quick_idle_rewards = self.idle_reward_service.quick_idle_rewards(idle_stage.idle_rewards_per_hour) if idle_stage is not None else {}
        return ResourceOverview(
            stamina=player.stamina,
            max_stamina=self.stamina_service.MAX_STAMINA,
            challenge_cost=self.stamina_service.CHALLENGE_COST,
            next_recovery_seconds=recovery.next_recovery_seconds if recovery is not None else self._preview_next_stamina_recovery_seconds(player, now),
            currencies=dict(player.profile.currencies),
            stamina_purchase_times_today=player.stamina_purchase_times_today,
            stamina_purchase_limit=self.stamina_service.PURCHASE_LIMIT,
            stamina_purchase_remaining=max(0, self.stamina_service.PURCHASE_LIMIT - player.stamina_purchase_times_today),
            next_stamina_purchase_cost=next_purchase_cost,
            quick_idle_used_today=player.quick_idle_used_today,
            quick_idle_limit=self.idle_reward_service.QUICK_IDLE_COUNT,
            quick_idle_remaining=max(0, self.idle_reward_service.QUICK_IDLE_COUNT - player.quick_idle_used_today),
            quick_idle_hours=self.idle_reward_service.QUICK_IDLE_HOURS,
            idle_stage_id=idle_stage_id,
            idle_stage_name=idle_stage.name if idle_stage is not None else None,
            idle_elapsed_seconds=idle_elapsed_seconds,
            idle_capped_seconds=idle_capped_seconds,
            idle_rewards_preview=rewards,
            quick_idle_rewards_preview=quick_idle_rewards,
        )

    def _get_idle_reward_snapshot(self, player: PlayerData, now: datetime) -> tuple[str | None, StageDefinition | None, int, int, dict[str, int]]:
        stages = self.load_stages()
        campaign_service = self._build_campaign_service(stages)
        idle_stage_id = campaign_service.best_stage_id(player)
        if idle_stage_id is None:
            return None, None, 0, 0, {}
        idle_stage = stages[idle_stage_id]
        idle_started_at = self._deserialize_datetime(player.idle_last_claimed_at) or now
        idle_elapsed_seconds = max(0, int((now - idle_started_at).total_seconds()))
        idle_capped_seconds = self.idle_reward_service.capped_seconds(idle_elapsed_seconds)
        rewards = self.idle_reward_service.calculate_rewards(idle_stage.idle_rewards_per_hour, idle_elapsed_seconds)
        return idle_stage_id, idle_stage, idle_elapsed_seconds, idle_capped_seconds, rewards

    def _refresh_player_timed_state(self, player: PlayerData, now: datetime) -> StaminaRecoveryResult:
        self._reset_daily_counters_if_needed(player, now)
        return self._refresh_stamina(player, now)

    def _refresh_stamina(self, player: PlayerData, now: datetime) -> StaminaRecoveryResult:
        last_updated_at = self._deserialize_datetime(player.stamina_last_updated_at) or now
        elapsed_seconds = max(0, int((now - last_updated_at).total_seconds()))
        recovery = self.stamina_service.recover_with_elapsed_seconds(player.stamina, elapsed_seconds)
        player.stamina = recovery.stamina
        if player.stamina >= self.stamina_service.MAX_STAMINA:
            player.stamina_last_updated_at = self._serialize_datetime(now)
        elif recovery.recovered > 0:
            player.stamina_last_updated_at = self._serialize_datetime(last_updated_at + timedelta(seconds=recovery.consumed_seconds))
        elif not player.stamina_last_updated_at:
            player.stamina_last_updated_at = self._serialize_datetime(now)
        return recovery

    def _preview_next_stamina_recovery_seconds(self, player: PlayerData, now: datetime) -> int | None:
        last_updated_at = self._deserialize_datetime(player.stamina_last_updated_at) or now
        elapsed_seconds = max(0, int((now - last_updated_at).total_seconds()))
        return self.stamina_service.recover_with_elapsed_seconds(player.stamina, elapsed_seconds).next_recovery_seconds

    def _reset_daily_counters_if_needed(self, player: PlayerData, now: datetime) -> None:
        last_reset_at = self._deserialize_datetime(player.daily_reset_at)
        if last_reset_at is None:
            player.daily_reset_at = self._serialize_datetime(now)
            return
        if last_reset_at.date() != now.date():
            player.stamina_purchase_times_today = 0
            player.quick_idle_used_today = 0
            player.daily_reset_at = self._serialize_datetime(now)

    @staticmethod
    def _grant_rewards(player: PlayerData, rewards: dict[str, int]) -> None:
        for currency, amount in rewards.items():
            player.profile.currencies[currency] = player.profile.currencies.get(currency, 0) + amount

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        return TimeUtils.to_isoformat(value)

    @staticmethod
    def _deserialize_datetime(value: str | None) -> datetime | None:
        return TimeUtils.parse_datetime(value)

    def _register_services(self) -> None:
        self.game_manager.register_service("event_manager", self.event_manager)
        self.game_manager.register_service("time_manager", self.time_manager)
        self.game_manager.register_service("ui_manager", self.ui_manager)
        self.game_manager.register_service("resource_manager", self.resource_manager)
        self.game_manager.register_service("save_repository", self.save_repository)
        self.resource_manager.register("config_loader", self.config_loader)

