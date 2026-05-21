from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from game.battle.engine import BattleResult
from game.ui.display_text import display_battle_action, display_name, display_status_list, display_status_name

POSITION_LABELS = {
    1: "前排左",
    2: "前排中",
    3: "前排右",
    4: "后排左",
    5: "后排中",
    6: "后排右",
}


@dataclass(slots=True)
class StageNodeViewModel:
    stage_id: str
    stage_name: str
    chapter_id: str
    chapter_name: str
    chapter_unlocked: bool
    chapter_completed: bool
    unlocked: bool
    completed: bool
    stars: int
    recommended_power: int
    current_power: int
    lock_reason: str | None
    row_index: int
    column_index: int
    is_selected: bool = False


@dataclass(slots=True)
class ChapterStageRowViewModel:
    chapter_id: str
    chapter_name: str
    chapter_unlocked: bool
    chapter_completed: bool
    unlock_condition: str
    row_index: int
    nodes: list[StageNodeViewModel] = field(default_factory=list)


@dataclass(slots=True)
class StageMapSceneModel:
    rows: list[ChapterStageRowViewModel]
    selected_stage_id: str | None = None


@dataclass(slots=True)
class BattlefieldSlotViewModel:
    side: str
    position: int
    slot_label: str
    hero_name: str
    camp: str
    role: str
    hero_level: int
    hero_quality: str
    awakening_level: str
    hero_ref: str | None = None
    is_empty: bool = True
    is_highlighted: bool = False
    highlight_role: str = ""
    impact_style: str = ""
    current_hp_ratio: float = 0.0
    current_shield_ratio: float = 0.0
    current_energy_ratio: float = 0.0
    status_text: str = "待命"
    is_dead: bool = False


@dataclass(slots=True)
class ReplayMotionEvent:
    actor_side: str
    actor_position: int
    target_side: str
    target_positions: tuple[int, ...]
    mode: str


@dataclass(slots=True)
class BattlefieldSceneModel:
    stage_id: str
    stage_name: str
    formation_id: str
    recommended_power: int
    current_power: int
    current_stamina: int
    challenge_cost: int
    can_start: bool
    ally_slots: list[BattlefieldSlotViewModel]
    enemy_slots: list[BattlefieldSlotViewModel]
    summary_lines: list[str] = field(default_factory=list)
    feedback_events: list["ReplayFeedbackEvent"] = field(default_factory=list)
    motion_event: ReplayMotionEvent | None = None
    winner: str | None = None
    stars: int | None = None
    timed_out: bool = False


@dataclass(slots=True)
class ReplayFeedbackEvent:
    anchor_side: str
    anchor_position: int
    text: str
    color: str
    style: str


@dataclass(slots=True)
class ReplayUnitState:
    unit_id: str
    hero_name: str
    side: str
    position: int
    camp: str
    role: str
    hero_level: int
    hero_quality: str
    awakening_level: str
    current_hp: float
    max_hp: float
    current_energy: int
    max_energy: int
    current_shield: float = 0.0
    max_shield_seen: float = 0.0
    status_effects: list[str] = field(default_factory=list)
    is_alive: bool = True


@dataclass(slots=True)
class BattleReplayFrame:
    frame_index: int
    round_index: int
    log_index: int | None
    title: str
    detail_text: str
    scene: BattlefieldSceneModel
    feedback_events: tuple[ReplayFeedbackEvent, ...] = ()
    actor_unit_id: str | None = None
    primary_target_unit_id: str | None = None
    focus_unit_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class BattleReplayTimeline:
    stage_id: str
    stage_name: str
    frames: list[BattleReplayFrame]


def build_stage_map_scene(overviews: Iterable[Any], *, selected_stage_id: str | None = None) -> StageMapSceneModel:
    rows: list[ChapterStageRowViewModel] = []
    row_by_chapter_id: dict[str, ChapterStageRowViewModel] = {}

    for overview in overviews:
        row = row_by_chapter_id.get(overview.chapter_id)
        if row is None:
            row = ChapterStageRowViewModel(
                chapter_id=overview.chapter_id,
                chapter_name=overview.chapter_name,
                chapter_unlocked=bool(overview.chapter_unlocked),
                chapter_completed=bool(overview.chapter_completed),
                unlock_condition=str(overview.chapter_unlock_condition),
                row_index=len(rows),
            )
            rows.append(row)
            row_by_chapter_id[overview.chapter_id] = row
        row.nodes.append(
            StageNodeViewModel(
                stage_id=overview.stage_id,
                stage_name=overview.stage_name,
                chapter_id=overview.chapter_id,
                chapter_name=overview.chapter_name,
                chapter_unlocked=bool(overview.chapter_unlocked),
                chapter_completed=bool(overview.chapter_completed),
                unlocked=bool(overview.unlocked),
                completed=bool(overview.completed),
                stars=int(overview.stars),
                recommended_power=int(overview.recommended_power),
                current_power=int(overview.current_power),
                lock_reason=overview.lock_reason,
                row_index=row.row_index,
                column_index=len(row.nodes),
                is_selected=overview.stage_id == selected_stage_id,
            )
        )

    return StageMapSceneModel(rows=rows, selected_stage_id=selected_stage_id)


def build_battlefield_scene(preparation: Any, result: BattleResult | None = None) -> BattlefieldSceneModel:
    ally_lookup: dict[str, Any] = {}
    for hero in preparation.selectable_heroes:
        ally_lookup[hero.id] = hero
        ally_lookup[hero.template_id] = hero
    enemy_lookup = {hero.id: hero for hero in preparation.enemy_heroes}

    ally_slots = [
        _build_slot(
            side="ally",
            position=position,
            hero_ref=preparation.ally_formation.positions.get(position),
            hero=ally_lookup.get(preparation.ally_formation.positions.get(position, "")),
            default_status="出战中",
            default_energy_ratio=0.5,
        )
        for position in range(1, 7)
    ]
    enemy_slots = [
        _build_slot(
            side="enemy",
            position=position,
            hero_ref=preparation.enemy_formation.get(position),
            hero=enemy_lookup.get(preparation.enemy_formation.get(position, "")),
            default_status="敌方单位",
            default_energy_ratio=0.5,
        )
        for position in range(1, 7)
    ]

    summary_lines = [
        f"关卡：{preparation.stage_name} ({preparation.stage_id})",
        f"阵容方案：{preparation.formation_id}",
        f"战力对比：我方 {preparation.current_power} / 推荐 {preparation.recommended_power}",
        f"体力：{preparation.current_stamina}（开战消耗 {preparation.challenge_cost}）",
        f"开战条件：{'已满足' if preparation.can_start else '未满足'}",
    ]

    scene = BattlefieldSceneModel(
        stage_id=preparation.stage_id,
        stage_name=preparation.stage_name,
        formation_id=preparation.formation_id,
        recommended_power=int(preparation.recommended_power),
        current_power=int(preparation.current_power),
        current_stamina=int(preparation.current_stamina),
        challenge_cost=int(preparation.challenge_cost),
        can_start=bool(preparation.can_start),
        ally_slots=ally_slots,
        enemy_slots=enemy_slots,
        summary_lines=summary_lines,
    )
    if result is None:
        return scene
    return _apply_battle_result(scene, result)


def build_battle_replay_timeline(preparation: Any, result: BattleResult, battle_engine: Any) -> BattleReplayTimeline:
    ally_units = battle_engine.create_units(preparation.selectable_heroes, preparation.ally_formation.positions, side="ally")
    enemy_units = battle_engine.create_units(preparation.enemy_heroes, preparation.enemy_formation, side="enemy")
    states = {
        unit.unit_id: ReplayUnitState(
            unit_id=unit.unit_id,
            hero_name=unit.name,
            side=unit.side,
            position=unit.position,
            camp=_enum_value(unit.camp),
            role="敌军" if unit.side == "enemy" else "出战",
            hero_level=0,
            hero_quality="-",
            awakening_level="-",
            current_hp=float(unit.current_hp),
            max_hp=float(unit.max_hp),
            current_shield=0.0,
            max_shield_seen=0.0,
            current_energy=int(unit.current_energy),
            max_energy=int(unit.max_energy),
            is_alive=bool(unit.is_alive),
        )
        for unit in [*ally_units, *enemy_units]
    }
    _fill_replay_state_metadata(states, preparation)

    name_to_unit_ids: dict[str, list[str]] = {}
    for unit_id, state in states.items():
        name_to_unit_ids.setdefault(state.hero_name, []).append(unit_id)

    frames = [
        BattleReplayFrame(
            frame_index=0,
            round_index=0,
            log_index=None,
            title="开场布阵",
            detail_text="=== 2D 战斗回放 ===\n帧 1 / 1（初始化）\n说明: 展示战斗开始前的双方初始站位、生命与怒气。",
            scene=_build_scene_from_replay_states(
                preparation,
                states,
                actor_unit_id=None,
                primary_target_unit_id=None,
                feedback_events=[],
                action_name="",
                summary_lines=[
                    f"关卡：{preparation.stage_name} ({preparation.stage_id})",
                    "当前帧：开场布阵",
                    f"战力：我方 {preparation.current_power} / 推荐 {preparation.recommended_power}",
                ],
            ),
            feedback_events=(),
            focus_unit_ids=(),
        )
    ]

    processed_logs = 0
    for entries in _group_replay_log_entries(result.logs):
        frame = _build_replay_frame_from_log_group(
            preparation,
            states,
            name_to_unit_ids,
            entries,
            frame_index=len(frames),
            first_log_index=processed_logs,
        )
        frames.append(frame)
        processed_logs += len(entries)

    final_scene = _apply_battle_result(
        _build_scene_from_replay_states(
            preparation,
            states,
            actor_unit_id=None,
            primary_target_unit_id=None,
            feedback_events=[],
            action_name="",
            summary_lines=[
                f"关卡：{preparation.stage_name} ({preparation.stage_id})",
                f"战斗结束：{'我方胜利' if result.winner == 'ally' else '敌方胜利'}",
            ],
        ),
        result,
    )
    frames.append(
        BattleReplayFrame(
            frame_index=len(frames),
            round_index=result.rounds,
            log_index=len(result.logs) - 1 if result.logs else None,
            title="战斗结算",
            detail_text=(
                "=== 2D 战斗回放 ===\n"
                f"结算: {'我方胜利' if result.winner == 'ally' else '敌方胜利'}\n"
                f"回合: {result.rounds}\n"
                f"星级: {result.stars}\n"
                f"奖励: {result.rewards}"
            ),
            scene=final_scene,
            feedback_events=(),
            focus_unit_ids=(),
        )
    )

    total_frames = len(frames)
    normalized_frames: list[BattleReplayFrame] = []
    for frame in frames:
        normalized_frames.append(
            BattleReplayFrame(
                frame_index=frame.frame_index,
                round_index=frame.round_index,
                log_index=frame.log_index,
                title=frame.title,
                detail_text=frame.detail_text.replace("帧 1 / 1", f"帧 {frame.frame_index + 1} / {total_frames}"),
                scene=frame.scene,
                feedback_events=frame.feedback_events,
                actor_unit_id=frame.actor_unit_id,
                primary_target_unit_id=frame.primary_target_unit_id,
                focus_unit_ids=frame.focus_unit_ids,
            )
        )

    return BattleReplayTimeline(stage_id=preparation.stage_id, stage_name=preparation.stage_name, frames=normalized_frames)


def _group_replay_log_entries(logs: list[Any]) -> list[list[Any]]:
    groups: list[list[Any]] = []
    current_group: list[Any] = []
    current_key: tuple[Any, ...] | None = None

    for log_index, entry in enumerate(logs):
        metadata = getattr(entry, "metadata", {}) or {}
        cast_id = metadata.get("cast_id")
        if cast_id:
            group_key = ("cast", cast_id, metadata.get("cast_hit_index", 1))
        else:
            group_key = ("log", log_index)
        if current_group and group_key != current_key:
            groups.append(current_group)
            current_group = []
        current_group.append(entry)
        current_key = group_key

    if current_group:
        groups.append(current_group)
    return groups


def _build_replay_frame_from_log_group(
    preparation: Any,
    states: dict[str, ReplayUnitState],
    name_to_unit_ids: dict[str, list[str]],
    entries: list[Any],
    *,
    frame_index: int,
    first_log_index: int,
) -> BattleReplayFrame:
    first_entry = entries[0]
    first_metadata = getattr(first_entry, "metadata", {}) or {}
    actor_id = first_metadata.get("cast_actor_unit_id") or first_metadata.get("actor_unit_id") or _resolve_replay_unit_id(first_entry.actor, name_to_unit_ids, states)
    action_name = display_battle_action(str(first_metadata.get("cast_skill_name") or first_entry.action), first_metadata)

    feedback_events: list[ReplayFeedbackEvent] = []
    seen_skill_feedback: set[tuple[str, int, str, str]] = set()
    impacted_unit_ids: list[str] = []
    seen_impacted_units: set[str] = set()

    for entry in entries:
        metadata = getattr(entry, "metadata", {}) or {}
        entry_actor_id = metadata.get("actor_unit_id") or _resolve_replay_unit_id(entry.actor, name_to_unit_ids, states)
        entry_target_id = metadata.get("target_unit_id") or _resolve_replay_unit_id(entry.target, name_to_unit_ids, states)
        entry_actor = states.get(entry_actor_id) if entry_actor_id else None
        entry_target = states.get(entry_target_id) if entry_target_id else None
        _apply_replay_log_entry(states, entry, actor_id=entry_actor_id, target_id=entry_target_id)
        for event in _build_feedback_events(entry, actor=entry_actor, target=entry_target):
            if event.style == "skill":
                skill_key = (event.anchor_side, event.anchor_position, event.text, event.style)
                if skill_key in seen_skill_feedback:
                    continue
                seen_skill_feedback.add(skill_key)
            feedback_events.append(event)
        if entry_target_id and entry_target_id not in seen_impacted_units:
            seen_impacted_units.add(entry_target_id)
            impacted_unit_ids.append(entry_target_id)

    feedback_events = _order_replay_feedback_events(feedback_events)

    primary_target_unit_id = _resolve_group_primary_target(actor_id, impacted_unit_ids, states)
    focus_unit_ids = tuple(unit_id for unit_id in [actor_id, *impacted_unit_ids] if unit_id)
    target_summary = _summarize_group_targets(entries, actor_id=actor_id, impacted_unit_ids=impacted_unit_ids, states=states)
    value_summary = _summarize_group_values(entries)
    detail_text = (
        "=== 2D 战斗回放 ===\n"
        f"当前帧: {frame_index + 1}\n"
        f"回合: {first_entry.round_index}\n"
        f"事件: {first_entry.actor} 使用 {action_name} -> {target_summary}（{value_summary}）"
    )

    return BattleReplayFrame(
        frame_index=frame_index,
        round_index=first_entry.round_index,
        log_index=first_log_index + len(entries) - 1,
        title=f"第 {first_entry.round_index} 回合",
        detail_text=detail_text,
        scene=_build_scene_from_replay_states(
            preparation,
            states,
            actor_unit_id=actor_id,
            primary_target_unit_id=primary_target_unit_id,
            feedback_events=feedback_events,
            action_name=action_name,
            summary_lines=[
                f"关卡：{preparation.stage_name} ({preparation.stage_id})",
                f"当前帧：{first_entry.actor} → {target_summary}",
                f"动作：{action_name} / {value_summary}",
                f"回合：{first_entry.round_index}",
            ],
        ),
        feedback_events=tuple(feedback_events),
        actor_unit_id=actor_id,
        primary_target_unit_id=primary_target_unit_id,
        focus_unit_ids=focus_unit_ids,
    )


def _resolve_group_primary_target(
    actor_unit_id: str | None,
    impacted_unit_ids: list[str],
    states: dict[str, ReplayUnitState],
) -> str | None:
    if not impacted_unit_ids:
        return None
    actor = states.get(actor_unit_id) if actor_unit_id else None
    if actor is None:
        return impacted_unit_ids[0] if len(impacted_unit_ids) == 1 else None
    opposing_targets = [unit_id for unit_id in impacted_unit_ids if states.get(unit_id) is not None and states[unit_id].side != actor.side]
    if len(opposing_targets) == 1:
        return opposing_targets[0]
    return None


def _summarize_group_targets(
    entries: list[Any],
    *,
    actor_id: str | None,
    impacted_unit_ids: list[str],
    states: dict[str, ReplayUnitState],
) -> str:
    actor = states.get(actor_id) if actor_id else None
    if actor is not None:
        enemy_targets = [unit_id for unit_id in impacted_unit_ids if states.get(unit_id) is not None and states[unit_id].side != actor.side]
        ally_targets = [unit_id for unit_id in impacted_unit_ids if states.get(unit_id) is not None and states[unit_id].side == actor.side and unit_id != actor.unit_id]
        if enemy_targets:
            return _describe_target_group(enemy_targets, states, side_label="敌方")
        if ally_targets:
            return _describe_target_group(ally_targets, states, side_label="友方")
    if impacted_unit_ids:
        return _describe_target_group(impacted_unit_ids, states, side_label="目标")
    return str(entries[-1].target)


def _describe_target_group(unit_ids: list[str], states: dict[str, ReplayUnitState], *, side_label: str) -> str:
    resolved = [states[unit_id] for unit_id in unit_ids if unit_id in states]
    if not resolved:
        return side_label
    unique_names = [state.hero_name for state in resolved]
    if len(unique_names) == 1:
        return unique_names[0]
    return f"{side_label}{len(unique_names)}体"


def _summarize_group_values(entries: list[Any]) -> str:
    totals = {"damage": 0.0, "heal": 0.0, "energy": 0.0, "status": 0}
    for entry in entries:
        metadata = getattr(entry, "metadata", {}) or {}
        event_kind = str(metadata.get("event_kind", ""))
        value = float(entry.value)
        if event_kind == "damage" and value > 0:
            totals["damage"] += value
        elif event_kind == "heal" and value > 0:
            totals["heal"] += value
        elif event_kind == "energy" and value > 0:
            totals["energy"] += value
        elif event_kind == "status":
            totals["status"] += 1

    parts: list[str] = []
    if totals["damage"] > 0:
        parts.append(f"总伤害 {round(totals['damage'], 2)}")
    if totals["heal"] > 0:
        parts.append(f"总治疗 {round(totals['heal'], 2)}")
    if totals["energy"] > 0:
        parts.append(f"总回怒 {round(totals['energy'], 2)}")
    if totals["status"] > 0:
        parts.append(f"状态事件 {totals['status']} 条")
    return " / ".join(parts) if parts else f"事件 {len(entries)} 条"


def _apply_battle_result(scene: BattlefieldSceneModel, result: BattleResult) -> BattlefieldSceneModel:
    winner_text = "我方胜利" if result.winner == "ally" else "敌方胜利"
    summary_lines = [
        f"战斗结果：{winner_text}",
        f"回合 / 星级：{result.rounds} 回合 / {result.stars} 星",
        f"战斗状态：{'超时结束' if result.timed_out else '正常结束'}",
        f"奖励：{result.rewards}",
    ]
    top_damage = sorted(result.damage_statistics.items(), key=lambda item: item[1], reverse=True)[:4]
    if top_damage:
        summary_lines.append("伤害排行：" + "；".join(f"{name} {damage}" for name, damage in top_damage))

    ally_slots = list(scene.ally_slots)
    enemy_slots = list(scene.enemy_slots)
    if not result.timed_out:
        if result.winner == "ally":
            ally_slots = [_mark_victory(slot) for slot in ally_slots]
            enemy_slots = [_mark_defeat(slot) for slot in enemy_slots]
        else:
            ally_slots = [_mark_defeat(slot) for slot in ally_slots]
            enemy_slots = [_mark_victory(slot) for slot in enemy_slots]

    return BattlefieldSceneModel(
        stage_id=scene.stage_id,
        stage_name=scene.stage_name,
        formation_id=scene.formation_id,
        recommended_power=scene.recommended_power,
        current_power=scene.current_power,
        current_stamina=scene.current_stamina,
        challenge_cost=scene.challenge_cost,
        can_start=scene.can_start,
        ally_slots=ally_slots,
        enemy_slots=enemy_slots,
        summary_lines=summary_lines,
        motion_event=None,
        winner=result.winner,
        stars=result.stars,
        timed_out=result.timed_out,
    )


def _build_slot(
    *,
    side: str,
    position: int,
    hero_ref: str | None,
    hero: Any | None,
    default_status: str,
    default_energy_ratio: float,
) -> BattlefieldSlotViewModel:
    if hero is None:
        return BattlefieldSlotViewModel(
            side=side,
            position=position,
            slot_label=POSITION_LABELS[position],
            hero_name="空位",
            camp="-",
            role="-",
            hero_level=0,
            hero_quality="-",
            awakening_level="-",
            hero_ref=hero_ref,
            is_empty=True,
            status_text="待命",
            current_shield_ratio=0.0,
            is_dead=False,
        )
    return BattlefieldSlotViewModel(
        side=side,
        position=position,
        slot_label=POSITION_LABELS[position],
        hero_name=str(getattr(hero, "name", "未知武将")),
        camp=_enum_value(getattr(hero, "camp", "-")),
        role=_enum_value(getattr(hero, "role", "-")),
        hero_level=int(getattr(hero, "level", 1)),
        hero_quality=_enum_value(getattr(hero, "hero_quality", "-")),
        awakening_level=_enum_value(getattr(hero, "awakening_level", "-")),
        hero_ref=hero_ref,
        is_empty=False,
        current_hp_ratio=1.0,
        current_shield_ratio=0.0,
        current_energy_ratio=default_energy_ratio,
        status_text=default_status,
        is_dead=False,
    )


def _mark_victory(slot: BattlefieldSlotViewModel) -> BattlefieldSlotViewModel:
    if slot.is_empty:
        return slot
    return replace(slot, is_highlighted=True, status_text="胜利", current_hp_ratio=max(slot.current_hp_ratio, 0.75))


def _mark_defeat(slot: BattlefieldSlotViewModel) -> BattlefieldSlotViewModel:
    if slot.is_empty:
        return slot
    return replace(slot, is_highlighted=False, status_text="战败", current_hp_ratio=0.0, current_shield_ratio=0.0, current_energy_ratio=0.0, is_dead=True)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _fill_replay_state_metadata(states: dict[str, ReplayUnitState], preparation: Any) -> None:
    ally_lookup: dict[str, Any] = {}
    for hero in preparation.selectable_heroes:
        ally_lookup[hero.id] = hero
        ally_lookup[hero.template_id] = hero
    enemy_lookup = {hero.id: hero for hero in preparation.enemy_heroes}

    for state in states.values():
        if state.side == "ally":
            hero_ref = preparation.ally_formation.positions.get(state.position)
            hero = ally_lookup.get(hero_ref)
        else:
            hero_ref = preparation.enemy_formation.get(state.position)
            hero = enemy_lookup.get(hero_ref)
        if hero is None:
            continue
        state.role = _enum_value(getattr(hero, "role", state.role))
        state.hero_level = int(getattr(hero, "level", 1))
        state.hero_quality = _enum_value(getattr(hero, "hero_quality", state.hero_quality))
        state.awakening_level = _enum_value(getattr(hero, "awakening_level", state.awakening_level))


def _resolve_replay_unit_id(name: str, name_to_unit_ids: dict[str, list[str]], states: dict[str, ReplayUnitState]) -> str | None:
    candidates = name_to_unit_ids.get(name, [])
    if not candidates:
        return None
    living = [unit_id for unit_id in candidates if states[unit_id].is_alive]
    if len(living) == 1:
        return living[0]
    if len(candidates) == 1:
        return candidates[0]
    return living[0] if living else candidates[0]


def _apply_replay_log_entry(states: dict[str, ReplayUnitState], entry: Any, *, actor_id: str | None, target_id: str | None) -> None:
    metadata = getattr(entry, "metadata", {}) or {}
    effect_type = str(metadata.get("effect_type", ""))
    event_kind = str(metadata.get("event_kind", ""))
    action = str(entry.action)
    value = float(entry.value)
    actor = states.get(actor_id) if actor_id else None
    target = states.get(target_id) if target_id else None
    recipient = _resolve_log_recipient(action, actor=actor, target=target)

    if actor is not None:
        _apply_actor_energy_change(actor, metadata)

    absorbed = float(metadata.get("absorbed", 0.0) or 0.0)
    if target is not None and absorbed > 0:
        target.current_shield = max(0.0, target.current_shield - absorbed)

    if recipient is not None and metadata.get("hp_delta") is not None:
        hp_delta = float(metadata.get("hp_delta", 0.0))
        recipient.current_hp = min(recipient.max_hp, max(0.0, recipient.current_hp + hp_delta))
        recipient.is_alive = recipient.current_hp > 0
    elif recipient is not None and _is_heal_action(action, effect_type):
        recipient.current_hp = min(recipient.max_hp, recipient.current_hp + max(0.0, value))
        recipient.is_alive = recipient.current_hp > 0

    if recipient is not None and metadata.get("energy_delta") is not None:
        recipient.current_energy = min(recipient.max_energy, max(0, recipient.current_energy + int(float(metadata.get("energy_delta", 0.0)))))
    elif recipient is not None and _is_energy_action(action, effect_type):
        recipient.current_energy = min(recipient.max_energy, recipient.current_energy + int(max(0.0, value)))
    elif recipient is not None and action == "绝境续命":
        recipient.current_hp = min(recipient.max_hp, max(1.0, value))
        recipient.is_alive = True
    elif recipient is not None and _is_damage_action(action, effect_type, metadata, value):
        recipient.current_hp = max(0.0, recipient.current_hp - max(0.0, value))
        recipient.current_energy = min(recipient.max_energy, recipient.current_energy + 10)
        recipient.is_alive = recipient.current_hp > 0
        if not recipient.is_alive:
            recipient.status_effects.clear()

    if actor is not None and action == "能量恢复" and recipient is None:
        actor.current_energy = min(actor.max_energy, actor.current_energy + int(max(0.0, value)))

    status_delta = str(metadata.get("status_delta", ""))
    if recipient is not None and (status_delta or effect_type):
        target_status = status_delta or effect_type
        if target_status == "shield" and (action == "shield生效" or _is_status_add_action(action)):
            recipient.current_shield += max(0.0, value)
            recipient.max_shield_seen = max(recipient.max_shield_seen, recipient.current_shield)
        elif target_status == "shield" and _is_status_remove_action(action, metadata):
            recipient.current_shield = max(0.0, recipient.current_shield - max(0.0, value))
        if _is_status_add_action(action):
            if target_status not in recipient.status_effects:
                recipient.status_effects.append(target_status)
        elif _is_status_remove_action(action, metadata):
            recipient.status_effects = [status for status in recipient.status_effects if status != target_status]


def _build_scene_from_replay_states(
    preparation: Any,
    states: dict[str, ReplayUnitState],
    *,
    actor_unit_id: str | None,
    primary_target_unit_id: str | None,
    feedback_events: list[ReplayFeedbackEvent],
    action_name: str,
    summary_lines: list[str],
) -> BattlefieldSceneModel:
    ally_state_by_position = {state.position: state for state in states.values() if state.side == "ally"}
    enemy_state_by_position = {state.position: state for state in states.values() if state.side == "enemy"}
    ally_slots = [
        _build_slot_from_replay_state(
            ally_state_by_position.get(position),
            side="ally",
            position=position,
            highlight_role=_resolve_highlight_role(ally_state_by_position.get(position), actor_unit_id=actor_unit_id, primary_target_unit_id=primary_target_unit_id),
            impact_style=_resolve_impact_style(ally_state_by_position.get(position), feedback_events),
        )
        for position in range(1, 7)
    ]
    enemy_slots = [
        _build_slot_from_replay_state(
            enemy_state_by_position.get(position),
            side="enemy",
            position=position,
            highlight_role=_resolve_highlight_role(enemy_state_by_position.get(position), actor_unit_id=actor_unit_id, primary_target_unit_id=primary_target_unit_id),
            impact_style=_resolve_impact_style(enemy_state_by_position.get(position), feedback_events),
        )
        for position in range(1, 7)
    ]
    return BattlefieldSceneModel(
        stage_id=preparation.stage_id,
        stage_name=preparation.stage_name,
        formation_id=preparation.formation_id,
        recommended_power=int(preparation.recommended_power),
        current_power=int(preparation.current_power),
        current_stamina=int(preparation.current_stamina),
        challenge_cost=int(preparation.challenge_cost),
        can_start=bool(preparation.can_start),
        ally_slots=ally_slots,
        enemy_slots=enemy_slots,
        summary_lines=summary_lines,
        feedback_events=list(feedback_events),
        motion_event=_build_motion_event(states, actor_unit_id=actor_unit_id, primary_target_unit_id=primary_target_unit_id, feedback_events=feedback_events, action_name=action_name),
    )


def _build_slot_from_replay_state(
    state: ReplayUnitState | None,
    *,
    side: str,
    position: int,
    highlight_role: str,
    impact_style: str,
) -> BattlefieldSlotViewModel:
    if state is None:
        return BattlefieldSlotViewModel(
            side=side,
            position=position,
            slot_label=POSITION_LABELS[position],
            hero_name="空位",
            camp="-",
            role="-",
            hero_level=0,
            hero_quality="-",
            awakening_level="-",
            is_empty=True,
            is_highlighted=False,
            highlight_role="",
            impact_style="",
            status_text="待命",
        )

    localized_statuses = display_status_list(state.status_effects[-2:]) if state.status_effects else []
    status_text = "阵亡" if not state.is_alive else (" / ".join(localized_statuses) if localized_statuses else "待命")
    hp_ratio = 0.0 if state.max_hp <= 0 else max(0.0, min(1.0, state.current_hp / state.max_hp))
    shield_denominator = max(state.max_hp, state.max_shield_seen, 1.0)
    shield_ratio = max(0.0, min(1.0, state.current_shield / shield_denominator))
    energy_ratio = 0.0 if state.max_energy <= 0 else max(0.0, min(1.0, state.current_energy / state.max_energy))
    return BattlefieldSlotViewModel(
        side=state.side,
        position=state.position,
        slot_label=POSITION_LABELS[state.position],
        hero_name=state.hero_name,
        camp=state.camp,
        role=state.role,
        hero_level=state.hero_level,
        hero_quality=state.hero_quality,
        awakening_level=state.awakening_level,
        is_empty=False,
        is_highlighted=bool(highlight_role),
        highlight_role=highlight_role,
        impact_style=impact_style,
        current_hp_ratio=hp_ratio,
        current_shield_ratio=shield_ratio,
        current_energy_ratio=energy_ratio,
        status_text=status_text,
        is_dead=not state.is_alive,
    )


def _build_motion_event(
    states: dict[str, ReplayUnitState],
    *,
    actor_unit_id: str | None,
    primary_target_unit_id: str | None,
    feedback_events: list[ReplayFeedbackEvent],
    action_name: str,
) -> ReplayMotionEvent | None:
    if not actor_unit_id or not action_name:
        return None
    actor = states.get(actor_unit_id)
    if actor is None or not actor.is_alive:
        return None
    if action_name in {"能量恢复", "再行动", "绝境续命", "shield生效"}:
        return None
    if primary_target_unit_id:
        target = states.get(primary_target_unit_id)
        if target is not None:
            return ReplayMotionEvent(actor_side=actor.side, actor_position=actor.position, target_side=target.side, target_positions=(target.position,), mode="single")
    target_events = [event for event in feedback_events if event.anchor_side != actor.side and event.style != "skill"]
    if not target_events:
        return None
    target_side = target_events[0].anchor_side
    target_positions = tuple(sorted({event.anchor_position for event in target_events}))
    return ReplayMotionEvent(
        actor_side=actor.side,
        actor_position=actor.position,
        target_side=target_side,
        target_positions=target_positions,
        mode="multi" if len(target_positions) > 1 else "single",
    )


def _resolve_highlight_role(
    state: ReplayUnitState | None,
    *,
    actor_unit_id: str | None,
    primary_target_unit_id: str | None,
) -> str:
    if state is None:
        return ""
    if actor_unit_id and state.unit_id == actor_unit_id:
        return "actor"
    if primary_target_unit_id and state.unit_id == primary_target_unit_id:
        return "target"
    return ""


def _resolve_impact_style(state: ReplayUnitState | None, feedback_events: list[ReplayFeedbackEvent]) -> str:
    if state is None:
        return ""
    fallback_style = ""
    for event in feedback_events:
        if event.anchor_side == state.side and event.anchor_position == state.position:
            if event.style != "skill":
                return event.style
            fallback_style = event.style
    return fallback_style


def _order_replay_feedback_events(events: list[ReplayFeedbackEvent]) -> list[ReplayFeedbackEvent]:
    indexed_events = list(enumerate(events))
    indexed_events.sort(key=lambda item: (_feedback_style_priority(item[1].style), item[0]))
    return [event for _, event in indexed_events]


def _feedback_style_priority(style: str) -> int:
    if style == "skill":
        return 0
    if style in {"system", "status"}:
        return 1
    if style in {"damage", "heal", "energy", "shield"}:
        return 2
    return 3


def _apply_actor_energy_change(actor: ReplayUnitState, metadata: dict[str, Any]) -> None:
    skill_type = str(metadata.get("skill_type", ""))
    if skill_type == "必杀":
        actor.current_energy = 0
    elif skill_type == "普攻":
        actor.current_energy = min(actor.max_energy, actor.current_energy + 20)


def _resolve_log_recipient(action: str, *, actor: ReplayUnitState | None, target: ReplayUnitState | None) -> ReplayUnitState | None:
    if action in {"灼烧", "中毒", "流血", "伤害分担"}:
        return actor
    if action in {"能量恢复", "再行动"}:
        return actor or target
    return target or actor


def _is_heal_action(action: str, effect_type: str) -> bool:
    return action in {"治疗", "魏武之盟", "会盟之利", "护盾回春"} or effect_type == "shield_regen"


def _is_energy_action(action: str, effect_type: str) -> bool:
    return action == "能量恢复" or effect_type == "energy"


def _is_status_add_action(action: str) -> bool:
    return any(token in action for token in ("生效", "刷新", "覆盖"))


def _is_status_remove_action(action: str, metadata: dict[str, Any]) -> bool:
    return bool(metadata.get("removed")) or any(token in action for token in ("移除", "清除", "解除"))


def _is_damage_action(action: str, effect_type: str, metadata: dict[str, Any], value: float) -> bool:
    if value <= 0:
        return False
    if metadata.get("blocked") or metadata.get("invincible") or metadata.get("resisted"):
        return False
    if _is_heal_action(action, effect_type) or _is_energy_action(action, effect_type):
        return False
    if action in {"绝境续命", "再行动"}:
        return False
    if _is_status_add_action(action) or _is_status_remove_action(action, metadata):
        return False
    return True


def _build_feedback_events(
    entry: Any,
    *,
    actor: ReplayUnitState | None,
    target: ReplayUnitState | None,
) -> list[ReplayFeedbackEvent]:
    metadata = getattr(entry, "metadata", {}) or {}
    effect_type = str(metadata.get("effect_type", ""))
    action = str(entry.action)
    value = float(entry.value)
    recipient = _resolve_log_recipient(action, actor=actor, target=target) or target or actor
    if recipient is None:
        return []

    events: list[ReplayFeedbackEvent] = []
    if actor is not None and _should_show_skill_feedback(action, metadata):
        events.append(_make_feedback_event(actor, display_battle_action(action, metadata), "#f8e16c", "skill"))
    if _is_damage_action(action, effect_type, metadata, value):
        prefix = "暴击 " if metadata.get("critical") else ""
        events.append(_make_feedback_event(recipient, f"{prefix}-{int(round(value))}", "#ff6b6b", "damage"))
    elif _is_heal_action(action, effect_type):
        events.append(_make_feedback_event(recipient, f"+{int(round(value))}", "#2ecc71", "heal"))
    elif _is_energy_action(action, effect_type):
        events.append(_make_feedback_event(recipient, f"怒+{int(round(value))}", "#4dabf7", "energy"))
    elif action == "再行动":
        events.append(_make_feedback_event(recipient, "再行动", "#f8e16c", "system"))
    elif action == "绝境续命":
        events.append(_make_feedback_event(recipient, "续命", "#f8e16c", "system"))
    elif metadata.get("blocked"):
        events.append(_make_feedback_event(recipient, "受控", "#95a5a6", "status"))
    elif metadata.get("resisted"):
        events.append(_make_feedback_event(recipient, "抵抗", "#95a5a6", "status"))
    elif metadata.get("invincible"):
        events.append(_make_feedback_event(recipient, "免伤", "#f8e16c", "status"))
    elif _is_status_add_action(action) and effect_type:
        events.append(_make_feedback_event(recipient, display_status_name(effect_type), "#c77dff", "status"))
    elif _is_status_remove_action(action, metadata) and effect_type:
        events.append(_make_feedback_event(recipient, f"移除 {display_status_name(effect_type)}", "#adb5bd", "status"))

    absorbed = float(metadata.get("absorbed", 0.0) or 0.0)
    if absorbed > 0 and target is not None:
        events.append(_make_feedback_event(target, f"吸收 {int(round(absorbed))}", "#74c0fc", "shield"))
    return events


def _make_feedback_event(recipient: ReplayUnitState, text: str, color: str, style: str) -> ReplayFeedbackEvent:
    return ReplayFeedbackEvent(
        anchor_side=recipient.side,
        anchor_position=recipient.position,
        text=text,
        color=color,
        style=style,
    )


def _should_show_skill_feedback(action: str, metadata: dict[str, Any]) -> bool:
    skill_type = str(metadata.get("skill_type", ""))
    if skill_type not in {"普攻", "必杀"}:
        return False
    return action not in {"再行动", "绝境续命", "能量恢复", "shield生效"}


