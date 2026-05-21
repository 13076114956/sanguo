from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from game.battle.engine import BattleResult
from game.ui.display_text import display_battle_action, display_skill_slot_name
from game.utility.time_utils import TimeUtils


@dataclass(slots=True)
class Screen:
    name: str
    title: str


class ScreenRouter:
    def __init__(self) -> None:
        self.current: Screen | None = None

    def go(self, screen: Screen) -> None:
        self.current = screen


class BattleConsoleView:
    def render_summary(self, result: BattleResult) -> str:
        lines = [
            "=== 战斗结算 ===",
            f"胜方: {'我方' if result.winner == 'ally' else '敌方'}",
            f"回合数: {result.rounds}",
            f"星级: {result.stars}",
            f"超时: {'是' if result.timed_out else '否'}",
            f"奖励: {result.rewards}",
            "伤害统计:",
        ]
        lines.extend(f"- {name}: {damage}" for name, damage in result.damage_statistics.items())
        return "\n".join(lines)

    def render_logs(self, result: BattleResult, *, limit: int = 20) -> str:
        lines = ["=== 战斗日志 ==="]
        for entry in result.logs[:limit]:
            metadata = entry.metadata or {}
            tags = []
            if metadata.get("skill_type"):
                tags.append(metadata["skill_type"])
            if metadata.get("critical"):
                tags.append("暴击")
            if metadata.get("resisted"):
                tags.append("被抵抗")
            if metadata.get("invincible"):
                tags.append("无敌免伤")
            if metadata.get("refreshed"):
                tags.append("刷新")
            if metadata.get("overridden"):
                tags.append("覆盖")
            if metadata.get("removed"):
                tags.append("移除")
            if metadata.get("total_hits", 1) > 1:
                tags.append(f"{metadata.get('hit_index', 1)}/{metadata.get('total_hits')}段")
            absorbed = metadata.get("absorbed", 0)
            if absorbed:
                tags.append(f"护盾吸收 {absorbed}")
            tag_text = f" [{' / '.join(tags)}]" if tags else ""
            lines.append(f"[第 {entry.round_index} 回合] {entry.actor} 使用 {display_battle_action(entry.action, metadata)}{tag_text} -> {entry.target}: {entry.value}")
        if len(result.logs) > limit:
            lines.append(f"... 共 {len(result.logs)} 条，已截断显示前 {limit} 条")
        return "\n".join(lines)


class ConsoleAppView:
    def render_messages(self, messages: Iterable[str]) -> str:
        return "\n".join(messages)

    def render_main_menu(self) -> str:
        return "\n".join(
            [
                "=== 欢乐战三国控制台 ===",
                "1. 查看武将列表",
                "2. 查询武将详情",
                "3. 激活武将奇珍",
                "4. 阵容管理",
                "5. 查看关卡列表",
                "6. 进入关卡备战",
                "7. 开始主线关卡",
                "8. 运行战斗示例",
                "9. 查看资源状态",
                "10. 领取挂机收益",
                "11. 存档管理",
                "12. 游戏设置",
                "13. 快速挂机",
                "14. 购买体力",
                "15. 武将觉醒合成",
                "16. 扫荡已通关主线关卡",
                "17. 一键扫荡章节",
                "18. 升级武将",
                "19. 元宝招募",
                "0. 退出",
            ]
        )

    def render_stage_battle_entry_menu(self) -> str:
        return "\n".join(
            [
                "=== 关卡备战操作 ===",
                "1. 查看可选武将",
                "2. 设置本次出战站位",
                "3. 下阵本次出战站位",
                "4. 交换本次出战站位",
                "5. 恢复为当前活动阵容",
                "6. 开始本次战斗",
                "0. 返回主菜单",
            ]
        )

    def render_save_management_menu(self) -> str:
        return "\n".join(
            [
                "=== 存档管理 ===",
                "1. 查看存档槽位",
                "2. 手动存档到槽位",
                "3. 读取/切换槽位",
                "4. 删除槽位",
                "5. 导出槽位到文件",
                "6. 从文件导入到槽位",
                "0. 返回主菜单",
            ]
        )

    def render_settings_menu(self) -> str:
        return "\n".join(
            [
                "=== 游戏设置 ===",
                "1. 查看当前设置",
                "2. 设置默认战斗速度",
                "3. 切换自动战斗开关",
                "0. 返回主菜单",
            ]
        )

    def render_formation_management_menu(self) -> str:
        return "\n".join(
            [
                "=== 阵容管理 ===",
                "1. 查看当前阵容",
                "2. 查看阵容预设",
                "3. 切换活动预设",
                "4. 上阵武将",
                "5. 下阵武将",
                "6. 交换站位",
                "7. 当前阵容保存为预设",
                "0. 返回主菜单",
            ]
        )

    def render_hero_selection_menu(self, overviews: Iterable[Any]) -> str:
        lines = ["=== 请选择武将 ==="]
        for index, overview in enumerate(overviews, start=1):
            lines.append(f"{index}. {overview.hero_name} (卡片ID: {overview.hero_id} / 模板ID: {overview.template_id})")
        return "\n".join(lines)

    def render_hero_card_list(self, cards: Iterable[Any]) -> str:
        lines = ["=== 武将卡片列表 ==="]
        for index, card in enumerate(cards, start=1):
            visible_tag = " / 当前最高卡" if card.is_visible else ""
            treasure_tag = " / 奇珍已激活" if card.has_rare_treasure else ""
            lines.append(
                f"{index}. {card.hero_name} [{card.hero_quality} / {card.awakening_level} / {card.awakening_color}]"
                f" Lv.{card.hero_level} / {card.role} / 卡片ID: {card.hero_id} / 模板ID: {card.template_id}{visible_tag}{treasure_tag}"
            )
        return "\n".join(lines)

    def render_formation_overview(self, overview: Any) -> str:
        lines = [
            f"=== 当前阵容：{overview.formation_name} ===",
            f"阵容ID: {overview.formation_id}",
            f"当前战力: {overview.power}",
            "上阵列表:",
        ]
        for slot in overview.slots:
            lines.append(f"- {slot.position}号位: {slot.hero_name} (引用: {slot.hero_ref} / 卡片ID: {slot.hero_id})")
        if not overview.slots:
            lines.append("- 当前阵容为空")
        return "\n".join(lines)

    def render_formation_preset_list(self, presets: Iterable[Any]) -> str:
        lines = ["=== 阵容预设列表 ==="]
        for preset in presets:
            active_flag = " [当前使用]" if preset.is_active else ""
            lines.append(f"- {preset.formation_id} {preset.formation_name}{active_flag} | 上阵人数: {preset.hero_count} | 战力: {preset.power}")
        return "\n".join(lines)

    def render_stage_list(self, overviews: Iterable[Any]) -> str:
        lines = ["=== 主线关卡列表 ==="]
        current_chapter_id: str | None = None
        for overview in overviews:
            if overview.chapter_id != current_chapter_id:
                current_chapter_id = overview.chapter_id
                chapter_status = "已解锁" if overview.chapter_unlocked else "未解锁"
                chapter_completed = " / 已通关" if overview.chapter_completed else ""
                chapter_reason = "" if overview.chapter_unlocked else f" / {overview.chapter_unlock_condition}"
                lines.append(f"[{overview.chapter_id}] {overview.chapter_name} [{chapter_status}{chapter_completed}{chapter_reason}]")
            status = "已解锁" if overview.unlocked else "未解锁"
            cleared = f" / 已通关 {overview.stars} 星" if overview.completed else ""
            sweepable = " / 可扫荡" if overview.completed else ""
            reason = f" / {overview.lock_reason}" if not overview.unlocked and overview.lock_reason else ""
            lines.append(
                f"- {overview.stage_id} {overview.stage_name} [{status}{cleared}{sweepable}{reason}] 推荐战力: {overview.recommended_power} 当前战力: {overview.current_power}"
            )
        return "\n".join(lines)

    def render_stage_battle_preparation(self, preparation: Any) -> str:
        lines = [
            f"=== 关卡备战：{preparation.stage_name} ===",
            f"关卡ID: {preparation.stage_id}",
            f"阵容方案: {preparation.formation_id}",
            f"推荐战力: {preparation.recommended_power}",
            f"当前战力: {preparation.current_power}",
            f"当前体力: {preparation.current_stamina}",
            f"挑战消耗: {preparation.challenge_cost}",
            f"出战人数要求: {preparation.min_heroes}~{preparation.max_heroes}",
            f"可否开战: {'是' if preparation.can_start else '否'}",
            "我方本次出战:",
        ]
        ally_name_by_ref = {hero.id: hero.name for hero in preparation.selectable_heroes}
        ally_name_by_ref.update({hero.template_id: hero.name for hero in preparation.selectable_heroes})
        for position, hero_ref in sorted(preparation.ally_formation.positions.items()):
            lines.append(f"- {position}号位: {ally_name_by_ref.get(hero_ref, hero_ref)} (引用: {hero_ref})")
        if not preparation.ally_formation.positions:
            lines.append("- 当前未选择出战武将")
        lines.extend(
            [
                f"可选武将数: {len(preparation.selectable_heroes)}",
                "敌方阵容:",
            ]
        )
        enemy_name_by_id = {hero.id: hero.name for hero in preparation.enemy_heroes}
        for position, hero_id in sorted(preparation.enemy_formation.items()):
            lines.append(f"- {position}号位: {enemy_name_by_id.get(hero_id, hero_id)}")
        return "\n".join(lines)

    def render_hero_skill_overview(self, overview: Any) -> str:
        lines = [
            f"=== 武将技能详情：{overview.hero_name} ===",
            f"卡片ID: {overview.hero_id}",
            f"模板ID: {overview.template_id}",
            f"阵营/职业/定位: {overview.camp} / {overview.profession} / {overview.role}",
            f"品质/觉醒: {overview.hero_quality} / {overview.awakening_level} ({overview.awakening_color})",
            f"武将等级: {overview.hero_level}/{overview.hero_level_cap}",
            f"来源: {overview.obtained_from}",
            f"奇珍状态: {'已激活' if overview.has_rare_treasure else '未激活'}",
            f"奇珍锁定槽位: {', '.join(display_skill_slot_name(slot) for slot in overview.rare_treasure_locked_skill_slots)}",
            f"基础战力: {overview.base_power}",
            f"最终战力: {overview.final_power}",
            "基础普攻: 单体 / 100%攻击 / 行动时自动",
            (
                "最终属性: "
                f"生命 {int(overview.final_stats.hp)} / 攻击 {int(overview.final_stats.attack)} / 防御 {int(overview.final_stats.defense)} / "
                f"速度 {int(overview.final_stats.speed)} / 暴击 {overview.final_stats.crit_rate:.0%} / 暴伤 {overview.final_stats.crit_damage:.2f} / "
                f"破甲 {overview.final_stats.armor_break:.0%} / 效果命中 {overview.final_stats.effect_hit:.0%} / 效果抵抗 {overview.final_stats.effect_resist:.0%}"
            ),
            "技能列表:",
        ]
        for skill in overview.skills:
            tags: list[str] = [skill.skill_type, display_skill_slot_name(skill.slot_key), f"Lv.{skill.level}"]
            if skill.locked_by_rare_treasure:
                tags.append("未激活奇珍，当前封顶3级")
            elif skill.needs_rare_treasure_for_level_four:
                tags.append("奇珍锁定位")
            lines.append(f"- {skill.skill_name} [{' / '.join(tags)}]")
        return "\n".join(lines)

    def render_hero_skill_overview_list(self, overviews: Iterable[Any]) -> str:
        lines = ["=== 武将技能概览 ==="]
        for overview in overviews:
            lines.append(
                f"- {overview.hero_name} [{overview.hero_quality}/{overview.awakening_level}] Lv.{overview.hero_level} | {overview.role} | 奇珍: {'是' if overview.has_rare_treasure else '否'} | 锁定槽位: {', '.join(display_skill_slot_name(slot) for slot in overview.rare_treasure_locked_skill_slots)}"
            )
        return "\n".join(lines)

    def render_awakening_fusion_result(self, fused: Any) -> str:
        return "\n".join(
            [
                "=== 觉醒合成结果 ===",
                f"武将: {fused.name}",
                f"新卡ID: {fused.id}",
                f"模板ID: {fused.template_id}",
                f"当前觉醒: {fused.awakening_level.value} ({fused.awakening_level.color})",
                f"当前等级: {fused.level}",
                "说明: 新卡已重置为 1 级；角色列表将只显示该模板的当前最高卡。",
            ]
        )

    def render_hero_level_up_result(self, result: Any) -> str:
        lines = [
            "=== 武将升级结果 ===",
            f"武将: {result.hero_name}",
            f"卡片ID: {result.hero_id}",
            f"模板ID: {result.template_id}",
            f"等级变化: Lv.{result.old_level} -> Lv.{result.new_level}/{result.level_cap}",
            f"本次提升: {result.actual_levels} 级 (目标 {result.requested_levels} 级)",
            f"消耗资源: {result.spent_hero_exp} 武将经验 / {result.spent_copper} 铜币",
            f"剩余资源: 武将经验 {result.remaining_hero_exp} / 铜币 {result.remaining_copper}",
            f"战力变化: {result.power_before} -> {result.power_after}",
            f"战斗技能档位: Lv.{result.battle_skill_level_before} -> Lv.{result.battle_skill_level_after}",
        ]
        return "\n".join(lines)

    def render_summon_result(self, result: Any) -> str:
        lines = [
            "=== 招募结果 ===",
            f"招募类型: {result.summon_type}",
            f"招募次数: {result.count}",
            f"消耗: {result.spent_amount}{result.spent_currency}",
            f"剩余{result.spent_currency}: {result.remaining_currency}",
            f"战力变化: {result.power_before} -> {result.power_after}",
            "获得武将:",
        ]
        for hero in result.heroes:
            visible_tag = " / 当前最高卡" if hero.is_visible else ""
            lines.append(
                f"- {hero.hero_name} [{hero.hero_quality} / {hero.awakening_level}] Lv.{hero.hero_level}"
                f" / 卡片ID: {hero.hero_id} / 模板ID: {hero.template_id}{visible_tag}"
            )
        return "\n".join(lines)

    def render_resource_overview(self, overview: Any) -> str:
        lines = [
            "=== 资源状态 ===",
            f"体力: {overview.stamina}/{overview.max_stamina}",
            f"主线挑战消耗: {overview.challenge_cost}",
            f"当前货币: {overview.currencies}",
            f"今日体力购买: {overview.stamina_purchase_times_today}/{overview.stamina_purchase_limit} (剩余 {overview.stamina_purchase_remaining} 次)",
            f"下次购买体力价格: {overview.next_stamina_purchase_cost if overview.next_stamina_purchase_cost is not None else '已达上限'}",
            f"今日快速挂机: {overview.quick_idle_used_today}/{overview.quick_idle_limit} (剩余 {overview.quick_idle_remaining} 次)",
        ]
        if overview.next_recovery_seconds is None:
            lines.append("下次体力恢复: 当前已满")
        else:
            breakdown = TimeUtils.seconds_to_breakdown(overview.next_recovery_seconds)
            lines.append(f"下次体力恢复: {breakdown.minutes:02d}分{breakdown.seconds:02d}秒")

        if overview.idle_stage_id is None:
            lines.append("挂机基准关卡: 暂无（请先通关至少 1 个主线关卡）")
            lines.append("当前可领取挂机收益: {}")
            lines.append(f"快速挂机({overview.quick_idle_hours}小时)预览: {{}}")
            return "\n".join(lines)

        idle_duration = TimeUtils.seconds_to_breakdown(overview.idle_elapsed_seconds)
        capped_duration = TimeUtils.seconds_to_breakdown(overview.idle_capped_seconds)
        lines.extend(
            [
                f"挂机基准关卡: {overview.idle_stage_id} {overview.idle_stage_name}",
                f"累计挂机时长: {idle_duration.hours}小时{idle_duration.minutes}分{idle_duration.seconds}秒",
                f"收益结算时长(8小时封顶): {capped_duration.hours}小时{capped_duration.minutes}分{capped_duration.seconds}秒",
                f"当前可领取挂机收益: {overview.idle_rewards_preview}",
                f"快速挂机({overview.quick_idle_hours}小时)预览: {overview.quick_idle_rewards_preview}",
            ]
        )
        return "\n".join(lines)

    def render_idle_claim_result(self, result: Any) -> str:
        lines = ["=== 挂机收益领取结果 ==="]
        if result.idle_stage_id is None:
            lines.append("当前尚未解锁挂机收益。")
            return "\n".join(lines)
        idle_duration = TimeUtils.seconds_to_breakdown(result.idle_elapsed_seconds)
        capped_duration = TimeUtils.seconds_to_breakdown(result.idle_capped_seconds)
        lines.extend(
            [
                f"结算关卡: {result.idle_stage_id} {result.idle_stage_name}",
                f"原始挂机时长: {idle_duration.hours}小时{idle_duration.minutes}分{idle_duration.seconds}秒",
                f"实际结算时长: {capped_duration.hours}小时{capped_duration.minutes}分{capped_duration.seconds}秒",
                f"领取奖励: {result.rewards}",
            ]
        )
        return "\n".join(lines)

    def render_quick_idle_result(self, result: Any) -> str:
        lines = ["=== 快速挂机结果 ==="]
        if result.idle_stage_id is None:
            lines.append("当前尚未解锁快速挂机。")
            return "\n".join(lines)
        lines.extend(
            [
                f"结算关卡: {result.idle_stage_id} {result.idle_stage_name}",
                f"获得奖励: {result.rewards}",
                f"今日已用次数: {result.used_today}",
                f"今日剩余次数: {result.remaining_times}",
            ]
        )
        return "\n".join(lines)

    def render_stamina_purchase_result(self, result: Any) -> str:
        return "\n".join(
            [
                "=== 购买体力结果 ===",
                f"消耗: {result.spent_amount}{result.spent_currency}",
                f"体力变化: {result.stamina_before} -> {result.stamina_after}",
                f"今日已购次数: {result.purchase_times_today}",
                f"今日剩余次数: {result.remaining_times}",
            ]
        )

    def render_stage_sweep_result(self, result: Any) -> str:
        return "\n".join(
            [
                "=== 关卡扫荡结果 ===",
                f"章节: {result.chapter_id}",
                f"关卡: {result.stage_id} {result.stage_name}",
                f"体力变化: {result.stamina_before} -> {result.stamina_after} (消耗 {result.challenge_cost})",
                f"获得奖励: {result.rewards}",
            ]
        )

    def render_chapter_sweep_result(self, result: Any) -> str:
        lines = [
            "=== 章节一键扫荡结果 ===",
            f"章节: {result.chapter_id}",
            f"体力变化: {result.stamina_before} -> {result.stamina_after}",
            f"本次扫荡关卡数: {len(result.stage_results)}/{len(result.attempted_stage_ids)}",
            f"合计奖励: {result.total_rewards}",
            "已扫荡关卡:",
        ]
        for stage in result.stage_results:
            lines.append(f"- {stage.stage_id} {stage.stage_name} | 体力 {stage.stamina_before}->{stage.stamina_after} | 奖励: {stage.rewards}")
        if not result.stage_results:
            lines.append("- 本次未完成任何关卡扫荡")
        if result.remaining_stage_ids:
            lines.append(f"未继续扫荡关卡: {', '.join(result.remaining_stage_ids)}")
        return "\n".join(lines)

    def render_save_slot_list(self, overviews: Iterable[Any]) -> str:
        lines = ["=== 存档槽位列表 ==="]
        for overview in overviews:
            status = "当前槽位" if overview.is_current else ("已存在" if overview.exists else "空槽位")
            if overview.error:
                detail = f"读取失败: {overview.error}"
            elif overview.exists:
                detail = f"玩家: {overview.player_name} | 等级: {overview.player_level} | 战力: {overview.power} | 武将数: {overview.hero_count}"
            else:
                detail = "暂无存档数据"
            lines.append(f"- 槽位 {overview.slot} [{status}] | {detail} | 路径: {overview.path}")
        return "\n".join(lines)

    def render_settings_overview(self, overview: Any) -> str:
        return "\n".join(
            [
                "=== 当前设置 ===",
                f"当前存档槽位: {overview.current_slot}",
                f"默认战斗速度: {overview.battle_speed} 倍",
                f"自动战斗: {'开启' if overview.auto_battle else '关闭'}",
            ]
        )

