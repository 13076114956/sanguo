from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from game.core.app import GameApplication, GameConfig
from game.ui.game_scene_app import run_game_scene_app
from game.ui.gui_app import run_desktop_app


def run_interactive_console(
    app: GameApplication,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> None:
    output_func(app.present_messages())
    while True:
        output_func(app.console_view.render_main_menu())
        choice = input_func("请选择菜单项: ").strip()
        if choice == "1":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_skill_overview_list(overviews))
            continue
        if choice == "2":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            hero_ref = _resolve_hero_ref(input_func("请输入序号或武将ID: ").strip(), overviews)
            if hero_ref is None:
                output_func("未找到对应武将，请重新选择。")
                continue
            overview = app.get_hero_skill_overview(hero_ref)
            output_func(app.console_view.render_hero_skill_overview(overview))
            continue
        if choice == "3":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            hero_ref = _resolve_hero_ref(input_func("请输入要激活奇珍的序号或武将ID: ").strip(), overviews)
            if hero_ref is None:
                output_func("未找到对应武将，请重新选择。")
                continue
            app.activate_rare_treasure(hero_ref)
            output_func(app.present_messages())
            output_func(app.console_view.render_hero_skill_overview(app.get_hero_skill_overview(hero_ref)))
            continue
        if choice == "4":
            _run_formation_management(app, input_func=input_func, output_func=output_func)
            continue
        if choice == "5":
            output_func(app.console_view.render_stage_list(app.list_stage_overviews()))
            continue
        if choice == "6":
            _run_stage_battle_entry(app, input_func=input_func, output_func=output_func)
            continue
        if choice == "7":
            stage_id = input_func("请输入要挑战的关卡ID: ").strip()
            try:
                result = app.start_stage_battle(stage_id)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.battle_view.render_summary(result))
            output_func(app.battle_view.render_logs(result, limit=20))
            continue
        if choice == "8":
            result = app.run_battle_demo()
            output_func(app.present_messages())
            output_func(app.battle_view.render_summary(result))
            output_func(app.battle_view.render_logs(result, limit=20))
            continue
        if choice == "9":
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "10":
            result = app.claim_idle_rewards()
            output_func(app.present_messages())
            output_func(app.console_view.render_idle_claim_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "11":
            _run_save_management(app, input_func=input_func, output_func=output_func)
            continue
        if choice == "12":
            _run_settings_menu(app, input_func=input_func, output_func=output_func)
            continue
        if choice == "13":
            try:
                result = app.quick_idle()
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_quick_idle_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "14":
            try:
                result = app.purchase_stamina()
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_stamina_purchase_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "15":
            _run_awakening_fusion(app, input_func=input_func, output_func=output_func)
            continue
        if choice == "16":
            stage_id = input_func("请输入要扫荡的已通关关卡ID: ").strip()
            try:
                result = app.sweep_stage(stage_id)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_stage_sweep_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "17":
            chapter_ref = input_func("请输入章节ID/章节号/任一关卡ID（留空则使用当前章节）: ").strip()
            try:
                result = app.sweep_chapter(chapter_ref or None)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_chapter_sweep_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "18":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            hero_ref = _resolve_hero_ref(input_func("请输入要升级的序号或武将ID: ").strip(), overviews)
            if hero_ref is None:
                output_func("未找到对应武将，请重新选择。")
                continue
            raw_levels = input_func("请输入升级级数（留空默认1，输入 max 表示尽可能升级）: ").strip().lower()
            use_max = raw_levels == "max"
            if not use_max and raw_levels and not raw_levels.isdigit():
                output_func("升级级数输入无效，请重新选择。")
                continue
            levels = 1 if not raw_levels or use_max else int(raw_levels)
            try:
                result = app.upgrade_hero_level(hero_ref, levels=levels, use_max=use_max)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_hero_level_up_result(result))
            output_func(app.console_view.render_hero_skill_overview(app.get_hero_skill_overview(result.hero_id)))
            continue
        if choice == "19":
            raw_count = input_func("请输入招募次数（1 或 10，留空默认 1）: ").strip()
            if raw_count and raw_count not in {"1", "10"}:
                output_func("招募次数输入无效，请输入 1 或 10。")
                continue
            count = 1 if not raw_count else int(raw_count)
            try:
                result = app.summon_heroes(count=count)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_summon_result(result))
            output_func(app.console_view.render_resource_overview(app.get_resource_overview()))
            continue
        if choice == "0":
            output_func("已退出控制台。")
            break
        output_func("无效菜单项，请输入 0~19。")


def _run_stage_battle_entry(
    app: GameApplication,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    stage_id = input_func("请输入关卡ID: ").strip()
    if not stage_id:
        output_func("关卡ID不可为空。")
        return
    active = app.get_active_formation()
    formation_positions: dict[int, str] = dict(active.positions) if active is not None else {}
    while True:
        try:
            preparation = app.open_stage_battle_entry(stage_id, formation_positions=formation_positions)
        except ValueError as exc:
            output_func(str(exc))
            return
        output_func(app.console_view.render_stage_battle_preparation(preparation))
        output_func(app.console_view.render_stage_battle_entry_menu())
        choice = input_func("请选择备战操作: ").strip()
        if choice == "1":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            continue
        if choice == "2":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            hero_ref = _resolve_hero_ref(input_func("请输入要设置到本次出战的序号或武将ID: ").strip(), overviews)
            position = _parse_position(input_func("请输入目标站位(1~6): ").strip())
            if hero_ref is None or position is None:
                output_func("武将或站位输入无效，请重新选择。")
                continue
            trial_positions = dict(formation_positions)
            trial_positions[position] = hero_ref
            try:
                app.formation_service.validate_or_raise(
                    app.open_stage_battle_entry(stage_id, formation_positions=trial_positions).ally_formation,
                    app._require_player().heroes,
                )
            except ValueError as exc:
                output_func(str(exc))
                continue
            formation_positions = trial_positions
            output_func("已更新本次出战站位。")
            continue
        if choice == "3":
            position = _parse_position(input_func("请输入要下阵的站位(1~6): ").strip())
            if position is None:
                output_func("站位输入无效，请重新选择。")
                continue
            formation_positions.pop(position, None)
            output_func("已从本次出战阵容中移除该站位武将。")
            continue
        if choice == "4":
            left = _parse_position(input_func("请输入左侧站位(1~6): ").strip())
            right = _parse_position(input_func("请输入右侧站位(1~6): ").strip())
            if left is None or right is None:
                output_func("站位输入无效，请重新选择。")
                continue
            preparation.ally_formation.positions = dict(formation_positions)
            app.formation_service.swap_positions(preparation.ally_formation, left, right)
            formation_positions = dict(preparation.ally_formation.positions)
            output_func("已交换本次出战站位。")
            continue
        if choice == "5":
            active = app.get_active_formation()
            formation_positions = dict(active.positions) if active is not None else {}
            output_func("已恢复为当前活动阵容。")
            continue
        if choice == "6":
            try:
                result = app.start_stage_battle(stage_id, formation_positions=formation_positions)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.battle_view.render_summary(result))
            output_func(app.battle_view.render_logs(result, limit=20))
            return
        if choice == "0":
            return
        output_func("无效菜单项，请输入 0~6。")


def _run_awakening_fusion(
    app: GameApplication,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    cards = app.list_hero_card_overviews()
    output_func(app.console_view.render_hero_card_list(cards))
    left_id = _resolve_hero_card_id(input_func("请输入左侧卡片序号或卡片ID: ").strip(), cards)
    right_id = _resolve_hero_card_id(input_func("请输入右侧卡片序号或卡片ID: ").strip(), cards)
    if left_id is None or right_id is None:
        output_func("卡片选择无效，请重新选择。")
        return
    try:
        fused = app.fuse_hero_awakening(left_id, right_id)
    except ValueError as exc:
        output_func(str(exc))
        return
    output_func(app.present_messages())
    output_func(app.console_view.render_awakening_fusion_result(fused))
    output_func(app.console_view.render_hero_card_list(app.list_hero_card_overviews()))


def _run_formation_management(
    app: GameApplication,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    while True:
        output_func(app.console_view.render_formation_management_menu())
        choice = input_func("请选择阵容操作: ").strip()
        if choice == "1":
            output_func(app.console_view.render_formation_overview(app.get_active_formation_overview()))
            continue
        if choice == "2":
            output_func(app.console_view.render_formation_preset_list(app.list_formation_preset_overviews()))
            continue
        if choice == "3":
            output_func(app.console_view.render_formation_preset_list(app.list_formation_preset_overviews()))
            formation_id = input_func("请输入要切换的阵容ID: ").strip()
            try:
                app.switch_formation_preset(formation_id)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_formation_overview(app.get_active_formation_overview()))
            continue
        if choice == "4":
            overviews = app.list_visible_hero_skill_overviews()
            output_func(app.console_view.render_hero_selection_menu(overviews))
            hero_ref = _resolve_hero_ref(input_func("请输入要上阵的序号或武将ID: ").strip(), overviews)
            position = _parse_position(input_func("请输入目标站位(1~6): ").strip())
            if hero_ref is None or position is None:
                output_func("武将或站位输入无效，请重新选择。")
                continue
            try:
                app.deploy_hero_to_active_formation(position, hero_ref)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_formation_overview(app.get_active_formation_overview()))
            continue
        if choice == "5":
            position = _parse_position(input_func("请输入要下阵的站位(1~6): ").strip())
            if position is None:
                output_func("站位输入无效，请重新选择。")
                continue
            app.undeploy_hero_from_active_formation(position)
            output_func(app.present_messages())
            output_func(app.console_view.render_formation_overview(app.get_active_formation_overview()))
            continue
        if choice == "6":
            left = _parse_position(input_func("请输入左侧站位(1~6): ").strip())
            right = _parse_position(input_func("请输入右侧站位(1~6): ").strip())
            if left is None or right is None:
                output_func("站位输入无效，请重新选择。")
                continue
            app.swap_active_formation_positions(left, right)
            output_func(app.present_messages())
            output_func(app.console_view.render_formation_overview(app.get_active_formation_overview()))
            continue
        if choice == "7":
            current = app.get_active_formation()
            if current is None:
                output_func("当前没有可保存的活动阵容。")
                continue
            formation_id = input_func("请输入要保存的阵容ID(如 formation_2): ").strip()
            name = input_func("请输入阵容名称(可留空): ").strip()
            if not formation_id:
                output_func("阵容ID不可为空。")
                continue
            try:
                app.save_formation_preset(formation_id, dict(current.positions), name=name or None)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_formation_preset_list(app.list_formation_preset_overviews()))
            continue
        if choice == "0":
            break
        output_func("无效菜单项，请输入 0~7。")


def _run_save_management(
    app: GameApplication,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    while True:
        output_func(app.console_view.render_save_management_menu())
        choice = input_func("请选择存档操作: ").strip()
        if choice == "1":
            output_func(app.console_view.render_save_slot_list(app.list_save_slot_overviews()))
            continue
        if choice == "2":
            slot = _parse_slot(input_func("请输入要保存到的槽位(1~5): ").strip())
            if slot is None:
                output_func("槽位输入无效，请重新选择。")
                continue
            try:
                app.save_to_slot(slot)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_save_slot_list(app.list_save_slot_overviews()))
            continue
        if choice == "3":
            slot = _parse_slot(input_func("请输入要读取的槽位(1~5): ").strip())
            if slot is None:
                output_func("槽位输入无效，请重新选择。")
                continue
            try:
                app.load_slot(slot)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_save_slot_list(app.list_save_slot_overviews()))
            continue
        if choice == "4":
            slot = _parse_slot(input_func("请输入要删除的槽位(1~5): ").strip())
            if slot is None:
                output_func("槽位输入无效，请重新选择。")
                continue
            try:
                app.delete_save_slot(slot)
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_save_slot_list(app.list_save_slot_overviews()))
            continue
        if choice == "5":
            slot = _parse_slot(input_func("请输入要导出的槽位(1~5): ").strip())
            destination = input_func("请输入导出文件路径: ").strip()
            if slot is None or not destination:
                output_func("槽位或路径输入无效，请重新选择。")
                continue
            try:
                app.export_save_slot(slot, Path(destination))
            except (OSError, ValueError, FileNotFoundError) as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            continue
        if choice == "6":
            slot = _parse_slot(input_func("请输入要导入到的槽位(1~5): ").strip())
            source = input_func("请输入导入文件路径: ").strip()
            if slot is None or not source:
                output_func("槽位或路径输入无效，请重新选择。")
                continue
            try:
                app.import_save_slot(slot, Path(source))
            except (OSError, ValueError, FileNotFoundError) as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_save_slot_list(app.list_save_slot_overviews()))
            continue
        if choice == "0":
            break
        output_func("无效菜单项，请输入 0~6。")


def _run_settings_menu(
    app: GameApplication,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    while True:
        output_func(app.console_view.render_settings_menu())
        choice = input_func("请选择设置项: ").strip()
        if choice == "1":
            output_func(app.console_view.render_settings_overview(app.get_settings_overview()))
            continue
        if choice == "2":
            raw_speed = input_func("请输入默认战斗速度(1/2/3): ").strip()
            if not raw_speed.isdigit():
                output_func("战斗速度输入无效，请重新选择。")
                continue
            try:
                app.set_battle_speed(int(raw_speed))
            except ValueError as exc:
                output_func(str(exc))
                continue
            output_func(app.present_messages())
            output_func(app.console_view.render_settings_overview(app.get_settings_overview()))
            continue
        if choice == "3":
            app.toggle_auto_battle()
            output_func(app.present_messages())
            output_func(app.console_view.render_settings_overview(app.get_settings_overview()))
            continue
        if choice == "0":
            break
        output_func("无效菜单项，请输入 0~3。")


def _resolve_hero_ref(selection: str, overviews: list[Any]) -> str | None:
    if not selection:
        return None
    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(overviews):
            return overviews[index].template_id
        return None
    for overview in overviews:
        if selection == overview.hero_id:
            return overview.hero_id
        if selection == overview.template_id:
            return overview.template_id
        if selection == overview.hero_name:
            return overview.template_id
    return None


def _resolve_hero_card_id(selection: str, cards: list[Any]) -> str | None:
    if not selection:
        return None
    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(cards):
            return cards[index].hero_id
        return None
    for card in cards:
        if selection == card.hero_id:
            return card.hero_id
    return None


def _parse_position(raw: str) -> int | None:
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if 1 <= value <= 6 else None


def _parse_slot(raw: str) -> int | None:
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if 1 <= value <= 5 else None


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="欢乐战三国入口")
    parser.add_argument("--console", action="store_true", help="使用旧版控制台菜单入口")
    parser.add_argument("--legacy-desktop", action="store_true", help="使用旧版管理后台式 GUI")
    args = parser.parse_args()

    if args.console:
        app = GameApplication(GameConfig.from_project_root(project_root))
        app.initialize()
        run_interactive_console(app)
        return
    if args.legacy_desktop:
        run_desktop_app(project_root)
        return
    run_game_scene_app(project_root)


if __name__ == "__main__":
    main()

