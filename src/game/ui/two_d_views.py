from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from game.ui.two_d_models import BattlefieldSceneModel, ReplayFeedbackEvent, ReplayMotionEvent, StageMapSceneModel


class StageMapCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, *, on_stage_selected: Callable[[str], None] | None = None, **kwargs) -> None:
        super().__init__(master, highlightthickness=0, bg="#101820", **kwargs)
        self._on_stage_selected = on_stage_selected
        self._node_regions: dict[int, str] = {}
        self.bind("<Button-1>", self._handle_click)

    def render(self, scene: StageMapSceneModel | None) -> None:
        self.delete("all")
        self._node_regions.clear()
        width = max(self.winfo_width(), int(self.cget("width") or 900), 900)
        height = max(self.winfo_height(), int(self.cget("height") or 520), 520)
        self.create_rectangle(0, 0, width, height, fill="#101820", outline="")
        self.create_text(20, 24, anchor="w", fill="#f5f7fa", font=("Microsoft YaHei UI", 15, "bold"), text="2D 主线地图")
        self.create_text(20, 52, anchor="w", fill="#95a5a6", font=("Microsoft YaHei UI", 9), text="点击节点可同步选择关卡，绿色=已通关，蓝色=已解锁，灰色=未解锁")

        if scene is None or not scene.rows:
            self.create_text(width / 2, height / 2, fill="#d0d7de", font=("Microsoft YaHei UI", 14), text="当前没有可展示的主线地图")
            return

        left_margin = 150
        top_margin = 120
        row_gap = 120
        col_gap = 150
        radius = 34

        for row in scene.rows:
            y = top_margin + row.row_index * row_gap
            chapter_fill = "#ecf0f1" if row.chapter_unlocked else "#7f8c8d"
            chapter_status = "已通关" if row.chapter_completed else ("已解锁" if row.chapter_unlocked else f"未解锁 / {row.unlock_condition}")
            self.create_text(24, y - 18, anchor="w", fill=chapter_fill, font=("Microsoft YaHei UI", 12, "bold"), text=f"{row.chapter_id} {row.chapter_name}")
            self.create_text(24, y + 10, anchor="w", fill="#95a5a6", font=("Microsoft YaHei UI", 9), text=chapter_status)

            centers: list[tuple[int, int, str]] = []
            for node in row.nodes:
                x = left_margin + node.column_index * col_gap
                centers.append((x, y, node.stage_id))
            for index in range(len(centers) - 1):
                start_x, start_y, _ = centers[index]
                end_x, end_y, _ = centers[index + 1]
                self.create_line(start_x + radius, start_y, end_x - radius, end_y, fill="#34495e", width=3)

            for node in row.nodes:
                x = left_margin + node.column_index * col_gap
                fill, outline, text_fill = self._node_colors(node)
                if node.is_selected:
                    self.create_oval(x - radius - 8, y - radius - 8, x + radius + 8, y + radius + 8, outline="#f1c40f", width=4)
                shape_id = self.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=2)
                self._node_regions[shape_id] = node.stage_id
                self.create_text(x, y - 6, fill=text_fill, font=("Microsoft YaHei UI", 9, "bold"), text=node.stage_id.removeprefix("stage_"))
                subtitle = "★" * node.stars if node.completed else ("LOCK" if not node.unlocked else "OPEN")
                self.create_text(x, y + 15, fill=text_fill, font=("Microsoft YaHei UI", 8), text=subtitle)
                self.create_text(x, y + 54, fill="#ecf0f1", font=("Microsoft YaHei UI", 9), text=node.stage_name)
                self.create_text(x, y + 74, fill="#95a5a6", font=("Microsoft YaHei UI", 8), text=f"荐 {node.recommended_power} / 我 {node.current_power}")

    def _handle_click(self, event: tk.Event[tk.Misc]) -> None:
        current = self.find_withtag("current")
        if not current:
            return
        stage_id = self._node_regions.get(current[0])
        if stage_id and self._on_stage_selected is not None:
            self._on_stage_selected(stage_id)

    @staticmethod
    def _node_colors(node: object) -> tuple[str, str, str]:
        if getattr(node, "completed", False):
            return "#27ae60", "#7bed9f", "#ffffff"
        if getattr(node, "unlocked", False):
            return "#2980b9", "#74b9ff", "#ffffff"
        return "#2c3e50", "#7f8c8d", "#c7d0d9"


class BattlefieldCanvas(tk.Canvas):
    FEEDBACK_STEP_INTERVAL_MS = 45
    BASE_SCENE_ANIMATION_STEPS = 6
    ACTION_FEEDBACK_REVEAL_STEP = 1
    ACTION_FEEDBACK_ACTIVE_STEPS = 4
    ACTION_FEEDBACK_MOVE_Y = -3.0
    REGULAR_FEEDBACK_REVEAL_STEP = 1
    REGULAR_FEEDBACK_ACTIVE_STEPS = 4
    REGULAR_FEEDBACK_MOVE_Y = -3.0
    NUMERIC_FEEDBACK_REVEAL_STEP = 4
    NUMERIC_FEEDBACK_ACTIVE_STEPS = 6
    NUMERIC_FEEDBACK_MOVE_Y = -0.75

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, highlightthickness=0, bg="#1b2631", **kwargs)
        self._animation_after_ids: list[str] = []
        self._feedback_item_ids: list[int] = []
        self._feedback_animation_settings: dict[int, tuple[int, int, float]] = {}
        self._actor_glow_ids: list[int] = []
        self._shake_tags: list[str] = []
        self._shake_offsets: dict[str, int] = {}
        self._motion_tags: list[str] = []
        self._motion_offsets: dict[str, tuple[float, float]] = {}
        self._motion_sequences: dict[str, list[tuple[float, float]]] = {}

    def render(self, scene: BattlefieldSceneModel | None) -> None:
        self.stop_animations(reset_positions=False)
        self.delete("all")
        width = max(self.winfo_width(), int(self.cget("width") or 920), 920)
        height = max(self.winfo_height(), int(self.cget("height") or 620), 620)
        self.create_rectangle(0, 0, width, height, fill="#1b2631", outline="")
        self.create_rectangle(24, 24, width - 24, 120, fill="#243447", outline="#34495e", width=2)
        self.create_text(44, 44, anchor="w", fill="#f5f7fa", font=("Microsoft YaHei UI", 16, "bold"), text="2D 战场预览")

        if scene is None:
            self.create_text(width / 2, height / 2, fill="#d0d7de", font=("Microsoft YaHei UI", 14), text="请先在关卡列表或左侧地图中选择一个关卡")
            return

        self.create_text(44, 76, anchor="w", fill="#ecf0f1", font=("Microsoft YaHei UI", 10), text=f"关卡：{scene.stage_name} ({scene.stage_id})")
        self.create_text(44, 100, anchor="w", fill="#bdc3c7", font=("Microsoft YaHei UI", 10), text=f"战力：{scene.current_power} / 推荐 {scene.recommended_power}   体力：{scene.current_stamina}（消耗 {scene.challenge_cost}）")
        self.create_text(width - 44, 76, anchor="e", fill="#bdc3c7", font=("Microsoft YaHei UI", 10, "bold"), text=f"阵容：{scene.formation_id}")
        self.create_text(width - 44, 100, anchor="e", fill=("#2ecc71" if scene.can_start else "#e67e22"), font=("Microsoft YaHei UI", 10, "bold"), text=("可直接开战" if scene.can_start else "阵容未满足开战条件"))

        battle_top = 140
        battle_bottom = height - 24
        self.create_rectangle(24, battle_top, width - 24, battle_bottom, fill="#16212b", outline="#34495e", width=2)
        center_y = (battle_top + battle_bottom) / 2
        self.create_line(40, center_y, width - 40, center_y, fill="#3b4b5b", dash=(10, 8), width=2)
        self.create_text(width / 2, center_y - 18, fill="#7f8c8d", font=("Microsoft YaHei UI", 10, "bold"), text="交战区域")

        column_x = [170, width / 2, width - 170]
        battle_height = battle_bottom - battle_top
        team_gap = max(170.0, battle_height * 0.34)
        row_gap = max(78.0, battle_height * 0.12)
        enemy_front_y = center_y - team_gap / 2
        enemy_back_y = enemy_front_y - row_gap
        ally_front_y = center_y + team_gap / 2
        ally_back_y = ally_front_y + row_gap
        enemy_rows = {1: enemy_front_y, 4: enemy_back_y}
        ally_rows = {1: ally_front_y, 4: ally_back_y}
        slot_centers: dict[tuple[str, int], tuple[float, float]] = {}

        for slot in scene.enemy_slots:
            x = column_x[(slot.position - 1) % 3]
            y = enemy_rows[1 if slot.position <= 3 else 4]
            slot_centers[(slot.side, slot.position)] = (x, y)
            self._draw_unit_card(x, y, slot)
        for slot in scene.ally_slots:
            x = column_x[(slot.position - 1) % 3]
            y = ally_rows[1 if slot.position <= 3 else 4]
            slot_centers[(slot.side, slot.position)] = (x, y)
            self._draw_unit_card(x, y, slot)

        self._setup_motion_animation(scene.motion_event, slot_centers)
        self._draw_feedback_events(scene.feedback_events, slot_centers)

        self.create_text(70, battle_top + 18, anchor="w", fill="#ffcf99", font=("Microsoft YaHei UI", 11, "bold"), text="敌方阵线")
        self.create_text(70, battle_bottom - 18, anchor="w", fill="#9dd9ff", font=("Microsoft YaHei UI", 11, "bold"), text="我方阵线")

        if scene.winner is not None:
            banner_text = f"{'我方胜利' if scene.winner == 'ally' else '敌方胜利'}  ·  {scene.stars or 0} 星"
            if scene.timed_out:
                banner_text += "  ·  超时结束"
            self.create_rectangle(width / 2 - 170, height / 2 - 62, width / 2 + 170, height / 2 + 10, fill="#111827", outline="#f1c40f", width=3)
            self.create_text(width / 2, height / 2 - 26, fill="#f8e16c", font=("Microsoft YaHei UI", 18, "bold"), text=banner_text)

        self._start_scene_animations(scene)

    def _draw_unit_card(self, x: float, y: float, slot: object) -> None:
        card_width = 188
        card_height = 114
        left = x - card_width / 2
        top = y - card_height / 2
        right = x + card_width / 2
        bottom = y + card_height / 2
        slot_tag = self._slot_tag(getattr(slot, "side", "unknown"), int(getattr(slot, "position", 0) or 0))

        if getattr(slot, "is_empty", True):
            self.create_rectangle(left, top, right, bottom, outline="#4b5563", width=2, dash=(8, 5), tags=(slot_tag,))
            self.create_text(x, y - 8, fill="#9ca3af", font=("Microsoft YaHei UI", 10, "bold"), text=f"{slot.slot_label}", tags=(slot_tag,))
            self.create_text(x, y + 14, fill="#6b7280", font=("Microsoft YaHei UI", 9), text="待命", tags=(slot_tag,))
            return

        side_fill = "#263b50" if getattr(slot, "side", "ally") == "ally" else "#4b2c39"
        highlight_role = getattr(slot, "highlight_role", "")
        impact_style = getattr(slot, "impact_style", "")
        outline = self._resolve_outline_color(slot, highlight_role)
        self.create_rectangle(left, top, right, bottom, fill=side_fill, outline=outline, width=3, tags=(slot_tag,))
        if highlight_role == "actor":
            glow_id = self.create_rectangle(left - 6, top - 6, right + 6, bottom + 6, outline="#f8e16c", width=3, tags=(slot_tag, "actor_glow"))
            self._actor_glow_ids.append(glow_id)
        elif highlight_role == "target":
            self.create_rectangle(left - 4, top - 4, right + 4, bottom + 4, outline="#ff8fab", width=2, dash=(6, 3), tags=(slot_tag,))
        if impact_style:
            self.create_rectangle(left + 4, top + 4, right - 4, bottom - 4, outline=self._impact_color(impact_style), width=2, tags=(slot_tag,))
            if impact_style in {"damage", "shield", "status"}:
                self._shake_tags.append(slot_tag)
                self._shake_offsets.setdefault(slot_tag, 0)
        self.create_text(left + 10, top + 12, anchor="w", fill="#ecf0f1", font=("Microsoft YaHei UI", 9, "bold"), text=f"{slot.slot_label} · {slot.hero_name}", tags=(slot_tag,))
        self.create_text(left + 10, top + 34, anchor="w", fill="#d0d7de", font=("Microsoft YaHei UI", 8), text=f"{slot.camp} / {slot.role} / Lv.{slot.hero_level}", tags=(slot_tag,))
        self.create_text(left + 10, top + 52, anchor="w", fill="#bdc3c7", font=("Microsoft YaHei UI", 8), text=f"{slot.hero_quality} / {slot.awakening_level}", tags=(slot_tag,))
        status_color = "#ff7a7a" if getattr(slot, "is_dead", False) else "#f8e16c"
        self.create_text(right - 10, top + 12, anchor="e", fill=status_color, font=("Microsoft YaHei UI", 8, "bold"), text=slot.status_text, tags=(slot_tag,))
        self._draw_bar(left + 14, bottom - 40, right - 10, bottom - 32, ratio=float(getattr(slot, "current_hp_ratio", 0.0)), fill="#2ecc71", bg="#27313d", label="HP", tag=slot_tag)
        self._draw_bar(left + 14, bottom - 28, right - 10, bottom - 20, ratio=float(getattr(slot, "current_shield_ratio", 0.0)), fill="#4dabf7", bg="#27313d", label="盾", tag=slot_tag)
        self._draw_bar(left + 14, bottom - 16, right - 10, bottom - 8, ratio=float(getattr(slot, "current_energy_ratio", 0.0)), fill="#f7d774", bg="#27313d", label="怒", tag=slot_tag)
        if getattr(slot, "is_dead", False):
            self.create_line(left + 14, top + 18, right - 14, bottom - 18, fill="#ff3b30", width=5, tags=(slot_tag,))
            self.create_line(right - 14, top + 18, left + 14, bottom - 18, fill="#ff3b30", width=5, tags=(slot_tag,))

    def _draw_feedback_events(self, events: list[ReplayFeedbackEvent], slot_centers: dict[tuple[str, int], tuple[float, float]]) -> None:
        skill_offsets: dict[tuple[str, int], int] = {}
        regular_offsets: dict[tuple[str, int], int] = {}
        for event in events:
            anchor_key = (event.anchor_side, event.anchor_position)
            center = slot_centers.get(anchor_key)
            if center is None:
                continue
            x, y = center
            font = ("Microsoft YaHei UI", 11, "bold")
            if event.style == "skill":
                offset = skill_offsets.get(anchor_key, 0)
                skill_offsets[anchor_key] = offset + 1
                font = ("Microsoft YaHei UI", 10, "bold")
                start_y = y - 106 - offset * 16
            else:
                offset = regular_offsets.get(anchor_key, 0)
                regular_offsets[anchor_key] = offset + 1
                start_y = y - 74 - offset * 18
            item_id = self.create_text(
                x,
                start_y,
                fill=event.color,
                font=font,
                text=event.text,
                tags=("feedback_text",),
            )
            reveal_step, last_move_step, move_y = self._feedback_animation_profile(event.style)
            if reveal_step > 1:
                self.itemconfigure(item_id, state="hidden")
            self._feedback_item_ids.append(item_id)
            self._feedback_animation_settings[item_id] = (reveal_step, last_move_step, move_y)

    def _setup_motion_animation(self, motion_event: ReplayMotionEvent | None, slot_centers: dict[tuple[str, int], tuple[float, float]]) -> None:
        self._motion_tags.clear()
        self._motion_offsets.clear()
        self._motion_sequences.clear()
        if motion_event is None:
            return
        actor_tag = self._slot_tag(motion_event.actor_side, motion_event.actor_position)
        actor_center = slot_centers.get((motion_event.actor_side, motion_event.actor_position))
        targets = [slot_centers.get((motion_event.target_side, position)) for position in motion_event.target_positions]
        resolved_targets = [item for item in targets if item is not None]
        if actor_center is None or not resolved_targets:
            return
        target_x = sum(item[0] for item in resolved_targets) / len(resolved_targets)
        target_y = sum(item[1] for item in resolved_targets) / len(resolved_targets)
        scale = 0.45 if motion_event.mode == "single" else 0.3
        dx = (target_x - actor_center[0]) * scale
        dy = (target_y - actor_center[1]) * scale
        sequence = [
            (dx * 0.18, dy * 0.18),
            (dx * 0.42, dy * 0.42),
            (dx * 0.72, dy * 0.72),
            (dx * 0.95, dy * 0.95),
            (dx * 0.45, dy * 0.45),
            (0.0, 0.0),
        ]
        self._motion_tags.append(actor_tag)
        self._motion_offsets[actor_tag] = (0.0, 0.0)
        self._motion_sequences[actor_tag] = sequence

    def stop_animations(self, *, reset_positions: bool = True) -> None:
        for after_id in self._animation_after_ids:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._animation_after_ids.clear()
        if reset_positions:
            for tag, current_offset in list(self._shake_offsets.items()):
                if current_offset:
                    self.move(tag, -current_offset, 0)
            for tag, (offset_x, offset_y) in list(self._motion_offsets.items()):
                if offset_x or offset_y:
                    self.move(tag, -offset_x, -offset_y)
        self._shake_offsets.clear()
        self._motion_offsets.clear()
        self._motion_sequences.clear()
        self._motion_tags.clear()
        self._feedback_animation_settings.clear()
        self._feedback_item_ids.clear()
        self._actor_glow_ids.clear()
        self._shake_tags.clear()

    def has_active_animation(self) -> bool:
        return bool(self._animation_after_ids)

    def _start_scene_animations(self, scene: BattlefieldSceneModel) -> None:
        if not scene.feedback_events and not self._actor_glow_ids and not self._shake_tags and not self._motion_tags:
            return
        total_steps = max(self.BASE_SCENE_ANIMATION_STEPS, self._max_feedback_animation_step())
        for step_index in range(1, total_steps + 1):
            after_id = self.after(step_index * self.FEEDBACK_STEP_INTERVAL_MS, lambda idx=step_index: self._run_animation_step(idx))
            self._animation_after_ids.append(after_id)
        final_id = self.after((total_steps + 1) * self.FEEDBACK_STEP_INTERVAL_MS, lambda: self.stop_animations(reset_positions=True))
        self._animation_after_ids.append(final_id)

    def _run_animation_step(self, step_index: int) -> None:
        for item_id in list(self._feedback_item_ids):
            if not self.type(item_id):
                continue
            reveal_step, last_move_step, move_y = self._feedback_animation_settings.get(item_id, (1, self.BASE_SCENE_ANIMATION_STEPS, self.REGULAR_FEEDBACK_MOVE_Y))
            if step_index < reveal_step:
                continue
            if self.itemcget(item_id, "state") == "hidden":
                self.itemconfigure(item_id, state="normal")
            if step_index <= last_move_step:
                self.move(item_id, 0, move_y)
        pulse_colors = ["#f8e16c", "#fff3bf", "#f1c40f", "#fff3bf", "#f8e16c", "#f1c40f"]
        pulse_widths = [3, 4, 5, 4, 3, 2]
        color = pulse_colors[min(step_index - 1, len(pulse_colors) - 1)]
        width = pulse_widths[min(step_index - 1, len(pulse_widths) - 1)]
        for item_id in self._actor_glow_ids:
            if self.type(item_id):
                self.itemconfigure(item_id, outline=color, width=width)

        shake_pattern = [0, -4, 4, -3, 3, 0]
        target_offset = shake_pattern[min(step_index - 1, len(shake_pattern) - 1)]
        for tag in self._shake_tags:
            current_offset = self._shake_offsets.get(tag, 0)
            dx = target_offset - current_offset
            if dx:
                self.move(tag, dx, 0)
                self._shake_offsets[tag] = target_offset
        for tag in self._motion_tags:
            sequence = self._motion_sequences.get(tag)
            if not sequence:
                continue
            target_x, target_y = sequence[min(step_index - 1, len(sequence) - 1)]
            current_x, current_y = self._motion_offsets.get(tag, (0.0, 0.0))
            move_x = target_x - current_x
            move_y = target_y - current_y
            if move_x or move_y:
                self.move(tag, move_x, move_y)
                self._motion_offsets[tag] = (target_x, target_y)

    @staticmethod
    def _slot_tag(side: str, position: int) -> str:
        return f"slot_{side}_{position}"

    @staticmethod
    def _resolve_outline_color(slot: object, highlight_role: str) -> str:
        if highlight_role == "actor":
            return "#f8e16c"
        if highlight_role == "target":
            return "#ff8fab"
        if getattr(slot, "is_highlighted", False):
            return "#f1c40f"
        return "#6dd5fa" if getattr(slot, "side", "ally") == "ally" else "#f8a5c2"

    @staticmethod
    def _impact_color(style: str) -> str:
        mapping = {
            "damage": "#ff6b6b",
            "heal": "#2ecc71",
            "energy": "#4dabf7",
            "status": "#c77dff",
            "shield": "#74c0fc",
            "system": "#f8e16c",
        }
        return mapping.get(style, "#ffffff")

    @staticmethod
    def _is_numeric_feedback_style(style: str) -> bool:
        return style in {"damage", "heal", "energy", "shield"}

    @classmethod
    def _feedback_animation_profile(cls, style: str) -> tuple[int, int, float]:
        if style == "skill":
            reveal_step = cls.ACTION_FEEDBACK_REVEAL_STEP
            active_steps = cls.ACTION_FEEDBACK_ACTIVE_STEPS
            move_y = cls.ACTION_FEEDBACK_MOVE_Y
        elif cls._is_numeric_feedback_style(style):
            reveal_step = cls.NUMERIC_FEEDBACK_REVEAL_STEP
            active_steps = cls.NUMERIC_FEEDBACK_ACTIVE_STEPS
            move_y = cls.NUMERIC_FEEDBACK_MOVE_Y
        else:
            reveal_step = cls.REGULAR_FEEDBACK_REVEAL_STEP
            active_steps = cls.REGULAR_FEEDBACK_ACTIVE_STEPS
            move_y = cls.REGULAR_FEEDBACK_MOVE_Y
        return reveal_step, reveal_step + active_steps - 1, move_y

    def _max_feedback_animation_step(self) -> int:
        if not self._feedback_animation_settings:
            return self.BASE_SCENE_ANIMATION_STEPS
        return max(last_move_step for _, last_move_step, _ in self._feedback_animation_settings.values())

    def _draw_bar(self, left: float, top: float, right: float, bottom: float, *, ratio: float, fill: str, bg: str, label: str, tag: str | None = None) -> None:
        ratio = max(0.0, min(1.0, ratio))
        tags = (tag,) if tag else ()
        self.create_rectangle(left, top, right, bottom, fill=bg, outline="", tags=tags)
        if ratio > 0:
            self.create_rectangle(left, top, left + (right - left) * ratio, bottom, fill=fill, outline="", tags=tags)
        self.create_text(left - 6, (top + bottom) / 2, anchor="e", fill="#d0d7de", font=("Microsoft YaHei UI", 7, "bold"), text=label, tags=tags)

