from __future__ import annotations

from pathlib import Path
import tkinter as tk

from ..data.models import FormationData, HeroData, SkillEffectData
from ..core.app import GameApplication, GameConfig, HeroSkillOverview, StageOverview
from .display_text import display_name, display_param_name, display_param_value, display_skill_slot_name, display_status_filter_name, display_status_name
from .two_d_models import BattleReplayFrame, BattleReplayTimeline, build_battle_replay_timeline, build_battlefield_scene, build_stage_map_scene
from .two_d_views import BattlefieldCanvas, StageMapCanvas


class GameSceneWindow:
    """纯画面式主入口：以大厅/地图/战场为核心的简约游戏界面。"""

    BG = "#0f1722"
    PANEL = "#162334"
    PANEL_ALT = "#1c2d43"
    PANEL_SOFT = "#223650"
    GOLD = "#f7d774"
    TEXT = "#ecf3ff"
    MUTED = "#9fb3c8"
    ACCENT = "#59c3c3"
    DANGER = "#ff7a7a"
    SUCCESS = "#4dd599"
    AWAKENING_BORDER_COLORS = {
        "白色": "#d9e2ec",
        "绿色": "#66d17a",
        "蓝色": "#5dade2",
        "紫色": "#b084f5",
        "金色": "#f7d774",
        "橙色": "#ff9f43",
        "天蓝色": "#7ed6df",
        "红色": "#ff6b6b",
    }
    POSITION_LABELS = {
        1: "前军左翼",
        2: "前军中坚",
        3: "前军右翼",
        4: "后军左翼",
        5: "后军中军",
        6: "后军右翼",
    }

    def __init__(self, root: tk.Tk, app: GameApplication) -> None:
        self.root = root
        self.app = app
        self.root.title("欢乐战三国 - 游戏界面")
        self.root.geometry("1600x960")
        self.root.minsize(1320, 820)
        self.root.configure(bg=self.BG)

        self.status_var = tk.StringVar(value="已进入大厅")
        self.resource_var = tk.StringVar(value="资源同步中...")
        self.active_nav_var = tk.StringVar(value="战役")
        self.scene_mode_var = tk.StringVar(value="地图巡航")
        self.scene_banner_var = tk.StringVar(value="主城视野已展开，点击地图节点进入主线。")
        self.stage_title_var = tk.StringVar(value="主线关卡")
        self.stage_meta_var = tk.StringVar(value="请先选择关卡")
        self.stage_badge_var = tk.StringVar(value="章节待命")
        self.stage_progress_var = tk.StringVar(value="尚未锁定目标关卡")
        self.stage_hint_var = tk.StringVar(value="点击左侧地图节点，开始进入真正的游戏画面流程。")
        self.hero_title_var = tk.StringVar(value="武将详情")
        self.hero_meta_var = tk.StringVar(value="请在底部英雄条选择一名武将")
        self.hero_chip_vars = {
            "camp": tk.StringVar(value="阵营 --"),
            "role": tk.StringVar(value="定位 --"),
            "quality": tk.StringVar(value="品质 --"),
            "level": tk.StringVar(value="等级 --"),
            "power": tk.StringVar(value="战力 --"),
        }
        self.formation_power_var = tk.StringVar(value="阵容战力：0")
        self.formation_preset_var = tk.StringVar(value="阵容预设加载中...")
        self.formation_draft_var = tk.StringVar(value="布阵草稿同步中...")
        self.formation_filter_var = tk.StringVar(value="筛选：全部武将")
        self.save_var = tk.StringVar(value="存档槽位：1")
        self.replay_var = tk.StringVar(value="当前没有战斗回放")
        self.hero_collection_var = tk.StringVar(value="武将总览加载中...")
        self.my_profile_var = tk.StringVar(value="主公信息加载中...")
        self.my_progress_var = tk.StringVar(value="战役进度加载中...")
        self.my_idle_var = tk.StringVar(value="养成信息加载中...")
        self.my_save_detail_var = tk.StringVar(value="存档摘要加载中...")
        self.settlement_title_var = tk.StringVar(value="战斗结算")
        self.settlement_banner_var = tk.StringVar(value="胜负待定")
        self.settlement_subtitle_var = tk.StringVar(value="主线挑战结果")
        self.settlement_meta_var = tk.StringVar(value="回合：0｜状态：待定")
        self.settlement_rating_var = tk.StringVar(value="评级：整装待发")
        self.settlement_reward_title_var = tk.StringVar(value="战利品")
        self.settlement_summary_var = tk.StringVar(value="当前没有可展示的战斗结算")
        self.settlement_rewards_var = tk.StringVar(value="奖励：暂无")
        self.settlement_damage_var = tk.StringVar(value="输出摘要：暂无")
        self._settlement_star_vars = [tk.StringVar(value="☆") for _ in range(3)]
        self._settlement_chip_vars = [
            tk.StringVar(value="战斗评级 待定"),
            tk.StringVar(value="关卡结果 待定"),
            tk.StringVar(value="奖励状态 待定"),
        ]

        self._selected_stage_id: str | None = None
        self._selected_hero_ref: str | None = None
        self._selected_formation_position: int | None = None
        self._selected_save_slot = 1
        self._formation_filter_camp = "全部"
        self._formation_filter_quality = "全部"
        self._formation_filter_deployed = "全部"
        self._formation_draft_positions: dict[int, str] = {}
        self._formation_draft_base_positions: dict[int, str] = {}
        self._formation_draft_dirty = False
        self._formation_drag_source: tuple[str, str | int] | None = None
        self._hero_detail_current_ref: str | None = None
        self._replay_timeline: BattleReplayTimeline | None = None
        self._replay_frame_index = 0
        self._replay_after_id: str | None = None
        self._replay_scale_is_syncing = False
        self._stage_overviews: list[StageOverview] = []
        self._hero_overviews: list[HeroSkillOverview] = []
        self._hero_overview_by_ref: dict[str, HeroSkillOverview] = {}
        self._hero_card_frames: list[tk.Widget] = []
        self._formation_hero_card_frames: list[tk.Widget] = []
        self._hero_card_state_vars: dict[str, tk.StringVar] = {}
        self._formation_filter_button_vars = {
            "camp": tk.StringVar(value="阵营：全部"),
            "quality": tk.StringVar(value="品质：全部"),
            "deployed": tk.StringVar(value="状态：全部"),
        }
        self._nav_buttons: dict[str, tk.Button] = {}
        self._formation_slot_cards: dict[int, tk.Frame] = {}
        self._formation_slot_title_vars: dict[int, tk.StringVar] = {index: tk.StringVar(value=self.POSITION_LABELS[index]) for index in range(1, 7)}
        self._formation_slot_meta_vars: dict[int, tk.StringVar] = {index: tk.StringVar(value="点击选择站位后，可从下方武将列表直接上阵") for index in range(1, 7)}
        self._formation_slot_badge_vars: dict[int, tk.StringVar] = {index: tk.StringVar(value="待命") for index in range(1, 7)}
        self._settlement_visible = False
        self._last_battle_summary: dict[str, object] | None = None
        self._slot_label_vars: dict[int, tk.StringVar] = {
            index: tk.StringVar(value=f"{self.POSITION_LABELS[index]}\n待命")
            for index in range(1, 7)
        }
        self.hero_detail_hint_var = tk.StringVar(value="点击武将卡弹出详情菜单，可查看装备、专属奇珍与技能全等级说明。")
        self.hero_detail_selected_var = tk.StringVar(value="当前未选中武将")
        self._hero_detail_window: tk.Toplevel | None = None
        self._hero_detail_title_var = tk.StringVar(value="武将详情")
        self._hero_detail_meta_var = tk.StringVar(value="请选择一名武将查看详情")
        self._hero_detail_stats_var = tk.StringVar(value="暂无属性")
        self._hero_detail_equipment_var = tk.StringVar(value="当前装备加成：暂无")
        self._hero_detail_treasure_var = tk.StringVar(value="专属奇珍：未激活")
        self._hero_detail_equipment_frame: tk.Frame | None = None
        self._hero_detail_treasure_frame: tk.Frame | None = None
        self._hero_detail_skills_text: tk.Text | None = None
        self._hero_detail_equipment_labels: list[tk.Label] = []
        self._hero_detail_treasure_labels: list[tk.Label] = []

        self._build_layout()
        self.refresh_all(initial=True)

    def _build_layout(self) -> None:
        top_bar = tk.Frame(self.root, bg="#0b1220", height=72)
        top_bar.pack(side=tk.TOP, fill=tk.X)
        top_bar.pack_propagate(False)

        title_box = tk.Frame(top_bar, bg="#0b1220")
        title_box.pack(side=tk.LEFT, padx=18)
        tk.Label(title_box, text="欢乐战三国", fg=self.TEXT, bg="#0b1220", font=("Microsoft YaHei UI", 24, "bold")).pack(anchor="w")
        tk.Label(title_box, textvariable=self.status_var, fg=self.MUTED, bg="#0b1220", font=("Microsoft YaHei UI", 10)).pack(anchor="w")

        resource_box = tk.Frame(top_bar, bg="#0b1220")
        resource_box.pack(side=tk.LEFT, padx=22)
        tk.Label(resource_box, textvariable=self.resource_var, fg=self.GOLD, bg="#0b1220", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        tk.Label(resource_box, text="占位头像 / 背景 / 按钮底图后续可直接替换图片资源", fg=self.MUTED, bg="#0b1220", font=("Microsoft YaHei UI", 9)).pack(anchor="w")

        action_box = tk.Frame(top_bar, bg="#0b1220")
        action_box.pack(side=tk.RIGHT, padx=16)
        for text, command, color in [
            ("回到战役", lambda: self.show_section("战役"), self.ACCENT),
            ("领取挂机", self.claim_idle_rewards, self.SUCCESS),
            ("快速挂机", self.quick_idle, self.GOLD),
            ("快速存档", self.quick_save, self.ACCENT),
            ("全部刷新", self.refresh_all, self.PANEL_SOFT),
        ]:
            tk.Button(
                action_box,
                text=text,
                command=command,
                bg=color,
                fg="#08111d",
                activebackground=color,
                relief=tk.FLAT,
                font=("Microsoft YaHei UI", 10, "bold"),
                padx=14,
                pady=8,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=5)

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 8))

        self.scene_header = tk.Frame(body, bg=self.BG)
        self.scene_header.pack(fill=tk.X, pady=(0, 10))
        header_left = tk.Frame(self.scene_header, bg=self.BG)
        header_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_left, textvariable=self.stage_title_var, fg=self.TEXT, bg=self.BG, font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        tk.Label(header_left, textvariable=self.stage_meta_var, fg=self.MUTED, bg=self.BG, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(2, 0))

        header_hud = tk.Frame(self.scene_header, bg=self.BG)
        header_hud.pack(side=tk.RIGHT, anchor="ne")
        for variable, bg, fg in [
            (self.active_nav_var, "#102033", self.GOLD),
            (self.scene_mode_var, self.ACCENT, "#08111d"),
            (self.stage_badge_var, self.PANEL_SOFT, self.TEXT),
            (self.stage_progress_var, "#102033", self.GOLD),
        ]:
            tk.Label(
                header_hud,
                textvariable=variable,
                bg=bg,
                fg=fg,
                font=("Microsoft YaHei UI", 9, "bold"),
                padx=10,
                pady=6,
            ).pack(side=tk.LEFT, padx=4)

        self.scene_banner = tk.Label(
            body,
            textvariable=self.scene_banner_var,
            fg=self.TEXT,
            bg="#132131",
            anchor="w",
            padx=14,
            pady=8,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.scene_banner.pack(fill=tk.X, pady=(0, 10))

        self.page_container = tk.Frame(body, bg=self.BG)
        self.page_container.pack(fill=tk.BOTH, expand=True)

        self.campaign_page = tk.Frame(self.page_container, bg=self.BG)
        campaign_layout = tk.Frame(self.campaign_page, bg=self.BG)
        campaign_layout.pack(fill=tk.BOTH, expand=True)
        scene_column = tk.Frame(campaign_layout, bg=self.BG)
        scene_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scene_container = tk.Frame(scene_column, bg=self.BG)
        self.scene_container.pack(fill=tk.BOTH, expand=True)
        self.stage_map_canvas = StageMapCanvas(self.scene_container, on_stage_selected=self.select_stage, width=980, height=590)
        self.battle_canvas = BattlefieldCanvas(self.scene_container, width=980, height=590)
        self.stage_map_canvas.pack(fill=tk.BOTH, expand=True)
        self.battle_canvas.pack_forget()

        self.settlement_overlay = tk.Frame(self.scene_container, bg="#0d1623", highlightthickness=2, highlightbackground="#f7d774")
        overlay_inner = tk.Frame(self.settlement_overlay, bg="#162334")
        overlay_inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        title_row = tk.Frame(overlay_inner, bg="#162334")
        title_row.pack(fill=tk.X, pady=(4, 8))
        tk.Label(title_row, textvariable=self.settlement_title_var, fg=self.GOLD, bg="#162334", font=("Microsoft YaHei UI", 26, "bold")).pack(anchor="center")
        tk.Label(title_row, textvariable=self.settlement_subtitle_var, fg=self.MUTED, bg="#162334", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="center", pady=(4, 0))

        self.settlement_banner_label = tk.Label(overlay_inner, textvariable=self.settlement_banner_var, fg="#08111d", bg=self.GOLD, font=("Microsoft YaHei UI", 16, "bold"), padx=18, pady=10)
        self.settlement_banner_label.pack(anchor="center", pady=(0, 8))

        chip_row = tk.Frame(overlay_inner, bg="#162334")
        chip_row.pack(pady=(0, 10))
        self._settlement_chip_labels: list[tk.Label] = []
        for variable in self._settlement_chip_vars:
            label = tk.Label(chip_row, textvariable=variable, fg=self.TEXT, bg=self.PANEL_SOFT, font=("Microsoft YaHei UI", 9, "bold"), padx=10, pady=5)
            label.pack(side=tk.LEFT, padx=4)
            self._settlement_chip_labels.append(label)

        star_row = tk.Frame(overlay_inner, bg="#162334")
        star_row.pack(pady=(0, 10))
        self._settlement_star_labels: list[tk.Label] = []
        for variable in self._settlement_star_vars:
            label = tk.Label(star_row, textvariable=variable, fg=self.GOLD, bg="#1b2a3d", font=("Microsoft YaHei UI", 24, "bold"), padx=12, pady=4)
            label.pack(side=tk.LEFT)
            self._settlement_star_labels.append(label)

        summary_card = tk.Frame(overlay_inner, bg="#132131", highlightthickness=1, highlightbackground="#2a4362")
        summary_card.pack(fill=tk.X, pady=(0, 10))
        tk.Label(summary_card, textvariable=self.settlement_meta_var, justify=tk.LEFT, wraplength=560, fg=self.MUTED, bg="#132131", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        tk.Label(summary_card, textvariable=self.settlement_rating_var, justify=tk.LEFT, wraplength=560, fg=self.GOLD, bg="#132131", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=12, pady=(0, 4))
        tk.Label(summary_card, textvariable=self.settlement_summary_var, justify=tk.LEFT, wraplength=560, fg=self.TEXT, bg="#132131", font=("Microsoft YaHei UI", 11)).pack(anchor="w", padx=12, pady=(0, 10))

        reward_header = tk.Frame(overlay_inner, bg="#162334")
        reward_header.pack(fill=tk.X, pady=(0, 4))
        tk.Label(reward_header, textvariable=self.settlement_reward_title_var, justify=tk.LEFT, fg=self.ACCENT, bg="#162334", font=("Microsoft YaHei UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(reward_header, textvariable=self.settlement_rewards_var, justify=tk.LEFT, wraplength=420, fg=self.TEXT, bg="#162334", font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=12)
        self.settlement_rewards_frame = tk.Frame(overlay_inner, bg="#162334")
        self.settlement_rewards_frame.pack(fill=tk.X, pady=(0, 10))
        self._settlement_reward_labels: list[tk.Label] = []
        self.settlement_damage_label = tk.Label(overlay_inner, textvariable=self.settlement_damage_var, justify=tk.LEFT, wraplength=560, fg=self.TEXT, bg="#162334", font=("Microsoft YaHei UI", 10))
        self.settlement_damage_label.pack(anchor="w", pady=(0, 16))
        settlement_button_row = tk.Frame(overlay_inner, bg="#162334")
        settlement_button_row.pack(fill=tk.X)
        self.settlement_replay_button = tk.Button(settlement_button_row, text="再看一遍", command=self.restart_replay_from_start, bg=self.GOLD, fg="#08111d", activebackground=self.GOLD, relief=tk.FLAT, padx=26, pady=10, cursor="hand2", font=("Microsoft YaHei UI", 11, "bold"))
        self.settlement_replay_button.pack(side=tk.LEFT, padx=4)
        self.settlement_return_button = tk.Button(settlement_button_row, text="返回战役", command=self.return_to_campaign_from_settlement, bg=self.PANEL_SOFT, fg=self.TEXT, activebackground=self.PANEL_SOFT, relief=tk.FLAT, padx=24, pady=10, cursor="hand2", font=("Microsoft YaHei UI", 11, "bold"))
        self.settlement_return_button.pack(side=tk.LEFT, padx=8)
        self.settlement_overlay.place_forget()

        campaign_sidebar = tk.Frame(campaign_layout, bg=self.BG, width=380)
        campaign_sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        campaign_sidebar.pack_propagate(False)

        self.stage_panel = self._create_panel(campaign_sidebar, "战役")
        self.stage_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(self.stage_panel, textvariable=self.stage_hint_var, justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(6, 10))
        stage_button_row = tk.Frame(self.stage_panel, bg=self.PANEL)
        stage_button_row.pack(fill=tk.X, padx=12, pady=(0, 12))
        for text, command, color in [
            ("开始战斗", self.start_selected_stage_battle, self.DANGER),
            ("扫荡关卡", self.sweep_selected_stage, self.SUCCESS),
            ("刷新关卡", self.refresh_stage_scene, self.PANEL_SOFT),
        ]:
            tk.Button(stage_button_row, text=text, command=command, bg=color, fg="#09121c", relief=tk.FLAT, font=("Microsoft YaHei UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=4)

        self.formation_panel = self._create_panel(campaign_sidebar, "阵容概览")
        self.formation_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(self.formation_panel, textvariable=self.formation_power_var, fg=self.GOLD, bg=self.PANEL, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", padx=14, pady=(6, 8))
        tk.Label(self.formation_panel, text="阵容编辑已迁移到独立“布阵”界面。上方 3×3 布阵盘，下方全部武将列表，适合拖位式调整。", justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(0, 10))
        tk.Button(self.formation_panel, text="进入布阵", command=lambda: self.show_section("布阵"), bg=self.ACCENT, fg="#08111d", relief=tk.FLAT, font=("Microsoft YaHei UI", 10, "bold"), pady=8, cursor="hand2").pack(fill=tk.X, padx=12, pady=(0, 12))

        self.replay_panel = self._create_panel(campaign_sidebar, "战斗回放")
        self.replay_panel.pack(fill=tk.X)
        tk.Label(self.replay_panel, textvariable=self.replay_var, justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 8))
        replay_btn_row = tk.Frame(self.replay_panel, bg=self.PANEL)
        replay_btn_row.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Button(replay_btn_row, text="上一帧", command=lambda: self.step_replay(-1), bg=self.PANEL_SOFT, fg=self.TEXT, relief=tk.FLAT, padx=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=4)
        self.play_button = tk.Button(replay_btn_row, text="播放", command=self.toggle_replay, bg=self.GOLD, fg="#08111d", relief=tk.FLAT, padx=18, pady=6, cursor="hand2")
        self.play_button.pack(side=tk.LEFT, padx=4)
        tk.Button(replay_btn_row, text="下一帧", command=lambda: self.step_replay(1), bg=self.PANEL_SOFT, fg=self.TEXT, relief=tk.FLAT, padx=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=4)
        self.skip_button = tk.Button(replay_btn_row, text="跳过", command=self.skip_replay_to_result, bg=self.DANGER, fg="#08111d", relief=tk.FLAT, padx=12, pady=6, cursor="hand2")
        self.skip_button.pack(side=tk.LEFT, padx=4)
        self.replay_scale = tk.Scale(self.replay_panel, from_=0, to=0, orient=tk.HORIZONTAL, bg=self.PANEL, troughcolor=self.PANEL_SOFT, fg=self.TEXT, highlightthickness=0, command=self._on_replay_scale_changed)
        self.replay_scale.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.formation_page = tk.Frame(self.page_container, bg=self.BG)
        formation_layout = tk.Frame(self.formation_page, bg=self.BG)
        formation_layout.pack(fill=tk.BOTH, expand=True)

        formation_top = self._create_panel(formation_layout, "布阵")
        formation_top.pack(fill=tk.X, pady=(0, 12))
        tk.Label(formation_top, text="上方为 3×3 布阵盘，中间行为战场中线装饰，当前仅启用前后两排 6 个可上阵站位。", justify=tk.LEFT, wraplength=1180, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 10))
        formation_preset_row = tk.Frame(formation_top, bg=self.PANEL)
        formation_preset_row.pack(fill=tk.X, padx=14, pady=(0, 10))
        tk.Label(formation_preset_row, textvariable=self.formation_preset_var, fg=self.GOLD, bg=self.PANEL, font=("Microsoft YaHei UI", 10, "bold")).pack(side=tk.LEFT)
        self.formation_save_button = tk.Button(
            formation_preset_row,
            text="保存",
            command=self.apply_formation_draft,
            bg=self.SUCCESS,
            fg="#08111d",
            relief=tk.FLAT,
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=18,
            pady=7,
            cursor="hand2",
        )
        self.formation_save_button.pack(side=tk.RIGHT)
        tk.Label(formation_top, textvariable=self.formation_draft_var, justify=tk.LEFT, wraplength=1180, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", padx=14, pady=(0, 10))
        formation_board = tk.Frame(formation_top, bg=self.PANEL)
        formation_board.pack(padx=14, pady=(0, 12))
        board_position_map = {
            (0, 0): 1,
            (0, 1): 2,
            (0, 2): 3,
            (2, 0): 4,
            (2, 1): 5,
            (2, 2): 6,
        }
        for row in range(3):
            for column in range(3):
                position = board_position_map.get((row, column))
                if position is None:
                    placeholder = tk.Frame(formation_board, bg="#132131", width=180, height=168, highlightthickness=1, highlightbackground="#30445f")
                    placeholder.grid(row=row, column=column, padx=8, pady=8)
                    placeholder.grid_propagate(False)
                    tk.Label(placeholder, text="战场中线", bg="#132131", fg=self.MUTED, font=("Microsoft YaHei UI", 11, "bold")).pack(expand=True)
                    continue

                slot_card = tk.Frame(formation_board, bg=self.PANEL_ALT, width=180, height=168, highlightthickness=1, highlightbackground="#30445f")
                slot_card.grid(row=row, column=column, padx=8, pady=8)
                slot_card.grid_propagate(False)
                self._formation_slot_cards[position] = slot_card

                portrait = tk.Canvas(slot_card, width=112, height=58, bg="#243a52", highlightthickness=0)
                portrait.pack(pady=(10, 6))
                portrait.create_rectangle(12, 10, 100, 46, fill="#34506e", outline="")
                portrait.create_text(56, 28, text="头像位", fill=self.TEXT, font=("Microsoft YaHei UI", 10, "bold"))

                tk.Label(slot_card, textvariable=self._formation_slot_title_vars[position], bg=self.PANEL_ALT, fg=self.TEXT, font=("Microsoft YaHei UI", 10, "bold")).pack()
                tk.Label(slot_card, textvariable=self._slot_label_vars[position], bg=self.PANEL_ALT, fg=self.TEXT, font=("Microsoft YaHei UI", 11, "bold")).pack(pady=(2, 0))
                tk.Label(slot_card, textvariable=self._formation_slot_meta_vars[position], bg=self.PANEL_ALT, fg=self.MUTED, font=("Microsoft YaHei UI", 8), wraplength=154, justify=tk.CENTER).pack(pady=(3, 0))
                tk.Label(slot_card, textvariable=self._formation_slot_badge_vars[position], bg="#102033", fg=self.GOLD, font=("Microsoft YaHei UI", 8, "bold"), padx=10, pady=3).pack(pady=(5, 5))

                tk.Label(slot_card, text="空位点击选择｜已上阵点击下阵｜也支持拖拽换位", bg=self.PANEL_ALT, fg=self.MUTED, font=("Microsoft YaHei UI", 8), wraplength=154, justify=tk.CENTER).pack(pady=(0, 8))
                self._bind_drag_press_recursive(slot_card, lambda pos=position: self._begin_slot_drag(pos))
                self._bind_drag_release_recursive(slot_card, lambda pos=position: self._handle_slot_release(pos))

        formation_bottom = self._create_panel(formation_layout, "已拥有武将")
        formation_bottom.pack(fill=tk.BOTH, expand=True)
        tk.Label(formation_bottom, text="下方展示全部已拥有武将。支持先选武将再点站位，也支持拖拽武将卡到上方站位；站位之间也可直接拖拽换位。", justify=tk.LEFT, wraplength=1180, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 10))
        tk.Label(formation_bottom, textvariable=self.formation_filter_var, justify=tk.LEFT, wraplength=1180, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(0, 8))
        self.formation_hero_scroll_canvas = tk.Canvas(formation_bottom, bg=self.PANEL, highlightthickness=0, height=250)
        self.formation_hero_scroll_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 10))
        self.formation_hero_scroll_frame = tk.Frame(self.formation_hero_scroll_canvas, bg=self.PANEL)
        self.formation_hero_scroll_window = self.formation_hero_scroll_canvas.create_window((0, 0), window=self.formation_hero_scroll_frame, anchor="nw")
        self.formation_hero_scroll_canvas.bind("<Configure>", self._sync_formation_hero_strip_width)
        self.formation_hero_scroll_frame.bind("<Configure>", lambda _event: self.formation_hero_scroll_canvas.configure(scrollregion=self.formation_hero_scroll_canvas.bbox("all")))
        formation_hero_scrollbar = tk.Scrollbar(formation_bottom, orient=tk.HORIZONTAL, command=self.formation_hero_scroll_canvas.xview)
        formation_hero_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.formation_hero_scroll_canvas.configure(xscrollcommand=formation_hero_scrollbar.set)

        self.hero_page = tk.Frame(self.page_container, bg=self.BG)
        hero_layout = tk.Frame(self.hero_page, bg=self.BG)
        hero_layout.pack(fill=tk.BOTH, expand=True)
        hero_gallery_panel = tk.Frame(hero_layout, bg=self.PANEL, highlightthickness=1, highlightbackground="#2f415a")
        hero_gallery_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hero_header = tk.Frame(hero_gallery_panel, bg=self.PANEL)
        hero_header.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(hero_header, text="武将", fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 16, "bold")).pack(side=tk.LEFT)
        tk.Label(hero_header, textvariable=self.hero_collection_var, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT, padx=12)
        self.hero_scroll_canvas = tk.Canvas(hero_gallery_panel, bg=self.PANEL, highlightthickness=0, height=560)
        self.hero_scroll_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 10))
        self.hero_scroll_frame = tk.Frame(self.hero_scroll_canvas, bg=self.PANEL)
        self.hero_scroll_window = self.hero_scroll_canvas.create_window((0, 0), window=self.hero_scroll_frame, anchor="nw")
        self.hero_scroll_canvas.bind("<Configure>", self._sync_hero_strip_width)
        self.hero_scroll_frame.bind("<Configure>", lambda _event: self.hero_scroll_canvas.configure(scrollregion=self.hero_scroll_canvas.bbox("all")))
        hero_scrollbar = tk.Scrollbar(hero_gallery_panel, orient=tk.HORIZONTAL, command=self.hero_scroll_canvas.xview)
        hero_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.hero_scroll_canvas.configure(xscrollcommand=hero_scrollbar.set)

        hero_sidebar = tk.Frame(hero_layout, bg=self.BG, width=380)
        hero_sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        hero_sidebar.pack_propagate(False)
        hero_quick_panel = self._create_panel(hero_sidebar, "武将菜单")
        hero_quick_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(hero_quick_panel, textvariable=self.hero_detail_hint_var, justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 8))
        tk.Label(hero_quick_panel, textvariable=self.hero_detail_selected_var, justify=tk.LEFT, wraplength=320, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=14, pady=(0, 8))
        tk.Button(hero_quick_panel, text="查看当前武将详情", command=self.open_selected_hero_detail, bg=self.ACCENT, fg="#08111d", relief=tk.FLAT, font=("Microsoft YaHei UI", 10, "bold"), pady=8, cursor="hand2").pack(fill=tk.X, padx=12, pady=(0, 12))
        hero_help_panel = self._create_panel(hero_sidebar, "阵容提示")
        hero_help_panel.pack(fill=tk.X)
        tk.Label(hero_help_panel, text="这里展示全部武将。点击卡牌可直接打开详情菜单；若切回“战役”或“布阵”页，当前选中武将仍可用于快速上阵。", justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 12))

        self.profile_page = tk.Frame(self.page_container, bg=self.BG)
        profile_layout = tk.Frame(self.profile_page, bg=self.BG)
        profile_layout.pack(fill=tk.BOTH, expand=True)
        profile_left = tk.Frame(profile_layout, bg=self.BG)
        profile_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for title, variable in [("主公信息", self.my_profile_var), ("战役进度", self.my_progress_var), ("养成 / 挂机", self.my_idle_var)]:
            panel = self._create_panel(profile_left, title)
            panel.pack(fill=tk.X, pady=(0, 12))
            tk.Label(panel, textvariable=variable, justify=tk.LEFT, wraplength=860, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 12))

        profile_right = tk.Frame(profile_layout, bg=self.BG, width=380)
        profile_right.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        profile_right.pack_propagate(False)
        save_summary_panel = self._create_panel(profile_right, "我的")
        save_summary_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(save_summary_panel, textvariable=self.my_save_detail_var, justify=tk.LEFT, wraplength=320, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 12))

        self.save_panel = self._create_panel(profile_right, "存档槽位")
        self.save_panel.pack(fill=tk.X)
        tk.Label(self.save_panel, textvariable=self.save_var, fg=self.GOLD, bg=self.PANEL, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", padx=14, pady=(8, 8))
        save_btn_row = tk.Frame(self.save_panel, bg=self.PANEL)
        save_btn_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        for slot in range(1, 6):
            tk.Button(save_btn_row, text=str(slot), command=lambda s=slot: self.select_save_slot(s), width=4, bg=self.PANEL_ALT, fg=self.TEXT, relief=tk.FLAT, cursor="hand2", font=("Microsoft YaHei UI", 10, "bold")).pack(side=tk.LEFT, padx=4)
        save_action_row = tk.Frame(self.save_panel, bg=self.PANEL)
        save_action_row.pack(fill=tk.X, padx=12, pady=(0, 12))
        tk.Button(save_action_row, text="读档", command=self.load_selected_slot, bg=self.PANEL_SOFT, fg=self.TEXT, relief=tk.FLAT, padx=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(save_action_row, text="存档", command=self.quick_save, bg=self.ACCENT, fg="#08111d", relief=tk.FLAT, padx=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=4)

        nav_bar = tk.Frame(self.root, bg="#0b1220", height=78)
        nav_bar.pack(side=tk.BOTTOM, fill=tk.X)
        nav_bar.pack_propagate(False)
        for section in ["战役", "布阵", "武将", "我的"]:
            button = tk.Button(
                nav_bar,
                text=section,
                command=lambda name=section: self.show_section(name),
                bg=self.PANEL_ALT,
                fg=self.TEXT,
                activebackground=self.ACCENT,
                relief=tk.FLAT,
                font=("Microsoft YaHei UI", 12, "bold"),
                padx=22,
                pady=12,
                cursor="hand2",
            )
            button.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=12)
            self._nav_buttons[section] = button
        self.show_section("战役")

    def _create_panel(self, parent: tk.Widget, title: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=self.PANEL, highlightthickness=1, highlightbackground="#30445f")
        tk.Label(panel, text=title, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        return panel

    def _bind_click_recursive(self, widget: tk.Widget, callback) -> None:
        widget.bind("<Button-1>", lambda _event: callback())
        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _bind_drag_press_recursive(self, widget: tk.Widget, callback) -> None:
        widget.bind("<ButtonPress-1>", lambda _event: callback(), add="+")
        for child in widget.winfo_children():
            self._bind_drag_press_recursive(child, callback)

    def _bind_drag_release_recursive(self, widget: tk.Widget, callback) -> None:
        widget.bind("<ButtonRelease-1>", lambda _event: callback(), add="+")
        for child in widget.winfo_children():
            self._bind_drag_release_recursive(child, callback)

    def show_section(self, section: str) -> None:
        pages = {
            "战役": self.campaign_page,
            "布阵": self.formation_page,
            "武将": self.hero_page,
            "我的": self.profile_page,
        }
        if section not in pages:
            return
        for page in pages.values():
            page.pack_forget()
        pages[section].pack(fill=tk.BOTH, expand=True)
        self.active_nav_var.set(section)
        for name, button in self._nav_buttons.items():
            selected = name == section
            button.configure(bg=self.ACCENT if selected else self.PANEL_ALT, fg="#08111d" if selected else self.TEXT)

    def _hide_settlement_overlay(self) -> None:
        self._settlement_visible = False
        self.settlement_overlay.place_forget()

    def _set_settlement_reward_cards(self, rewards: dict[str, int]) -> None:
        for label in self._settlement_reward_labels:
            label.destroy()
        self._settlement_reward_labels.clear()
        reward_items = list(rewards.items()) or [("暂无奖励", 0)]
        for name, amount in reward_items[:4]:
            card = tk.Label(
                self.settlement_rewards_frame,
                text=f"{name}\n×{amount}",
                fg=self.TEXT,
                bg="#1b2a3d",
                relief=tk.FLAT,
                font=("Microsoft YaHei UI", 10, "bold"),
                padx=18,
                pady=12,
                justify=tk.CENTER,
                highlightthickness=1,
                highlightbackground="#2a4362",
            )
            card.pack(side=tk.LEFT, padx=6)
            self._settlement_reward_labels.append(card)

    def _update_settlement_cards(self) -> None:
        summary = self._last_battle_summary or {}
        winner = str(summary.get("winner_text", "战斗结算"))
        stars = int(summary.get("stars", 0) or 0)
        rounds = int(summary.get("rounds", 0) or 0)
        timed_out = bool(summary.get("timed_out", False))
        rewards = dict(summary.get("rewards", {})) if isinstance(summary.get("rewards", {}), dict) else {}
        top_damage = summary.get("top_damage_text", "输出摘要：暂无")
        stage_name = str(summary.get("stage_name", "当前关卡"))

        victory = "胜利" in winner
        banner_bg = self.GOLD if victory else self.DANGER
        banner_fg = "#08111d"
        self.settlement_banner_label.configure(bg=banner_bg, fg=banner_fg)
        self.settlement_banner_var.set(winner)
        self.settlement_subtitle_var.set(f"{stage_name} · 结算完成")
        self.settlement_meta_var.set(f"回合：{rounds}｜状态：{'超时结束' if timed_out else '正常结束'}")
        self.settlement_rating_var.set(_build_settlement_rating_text(stars, timed_out=timed_out))
        self.settlement_rewards_var.set(f"奖励：{rewards if rewards else '暂无'}")
        self.settlement_damage_var.set(str(top_damage))
        self.settlement_reward_title_var.set("战利品已入库")
        self._settlement_chip_vars[0].set(f"战斗评级 {stars} 星")
        self._settlement_chip_vars[1].set(f"关卡结果 {'完美通关' if stars >= 3 else ('顺利通关' if '胜利' in winner else '挑战失败')}")
        self._settlement_chip_vars[2].set(f"奖励状态 {'自动结算' if rewards else '暂无掉落'}")
        for index, variable in enumerate(self._settlement_star_vars, start=1):
            variable.set("★" if index <= stars else "☆")
        self._set_settlement_reward_cards(rewards)

    def _show_settlement_overlay(self, frame_title: str, frame_detail: str) -> None:
        self._settlement_visible = True
        self.settlement_title_var.set(frame_title)
        detail_lines = [line for line in frame_detail.splitlines() if line.strip()]
        summary_text = "\n".join(detail_lines[:3]) if detail_lines else "战斗已结束。"
        rewards_line = next((line for line in detail_lines if "奖励:" in line or "奖励：" in line), "奖励：暂无")
        self.settlement_summary_var.set(summary_text)
        self.settlement_rewards_var.set(rewards_line.replace("奖励:", "奖励："))
        if self._last_battle_summary is None:
            self.settlement_banner_var.set(frame_title)
            self.settlement_subtitle_var.set("当前战斗尚未写入结算数据")
            self.settlement_meta_var.set("回合：未知｜状态：待定")
            self.settlement_rating_var.set("评级：整装待发")
            self.settlement_damage_var.set("输出摘要：暂无")
            self.settlement_reward_title_var.set("战利品")
            self._settlement_chip_vars[0].set("战斗评级 待定")
            self._settlement_chip_vars[1].set("关卡结果 待定")
            self._settlement_chip_vars[2].set("奖励状态 待定")
            for variable in self._settlement_star_vars:
                variable.set("☆")
            self._set_settlement_reward_cards({})
        else:
            self._update_settlement_cards()
        self.settlement_overlay.place(relx=0.5, rely=0.52, anchor="center", width=700, height=430)

    def _is_final_replay_frame(self) -> bool:
        return self._replay_timeline is not None and bool(self._replay_timeline.frames) and self._replay_frame_index >= len(self._replay_timeline.frames) - 1

    def restart_replay_from_start(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.status_var.set("当前没有可重新播放的战斗回放")
            return
        self._hide_settlement_overlay()
        self._show_replay_frame(0)
        self._start_replay_autoplay()
        self.status_var.set("已从头重新播放战斗回放")

    def return_to_campaign_from_settlement(self) -> None:
        self.stop_replay()
        self._hide_settlement_overlay()
        self.show_map_scene()
        self.status_var.set("已返回战役界面")

    def refresh_all(self, initial: bool = False) -> None:
        self.stop_replay()
        self._hide_settlement_overlay()
        self._last_battle_summary = None
        self.refresh_resources()
        self._reset_formation_draft_from_active()
        self.refresh_heroes(initial=initial)
        self.refresh_stage_scene(initial=initial)
        self.refresh_formation_panel()
        self.refresh_save_panel()
        self.refresh_profile_page()
        self.status_var.set("大厅已同步刷新")

    def refresh_resources(self) -> None:
        overview = self.app.get_resource_overview()
        copper = overview.currencies.get("铜币", 0)
        ingot = overview.currencies.get("元宝", 0)
        hero_exp = overview.currencies.get("武将经验", 0)
        self.resource_var.set(f"体力 {overview.stamina}/{overview.max_stamina}   铜币 {copper}   元宝 {ingot}   武将经验 {hero_exp}")

    def refresh_heroes(self, *, initial: bool = False) -> None:
        self._hero_overviews = self.app.list_visible_hero_skill_overviews()
        self._hero_overview_by_ref = {}
        if not self._hero_overviews:
            self._selected_hero_ref = None
            self.hero_title_var.set("武将详情")
            self.hero_meta_var.set("当前没有可展示的武将")
            self.hero_collection_var.set("暂无武将")
            for variable in self.hero_chip_vars.values():
                variable.set("--")
            self._normalize_formation_filters()
            self._rebuild_hero_strip()
            self._rebuild_formation_hero_roster()
            return
        for overview in self._hero_overviews:
            self._hero_overview_by_ref[overview.template_id] = overview
            self._hero_overview_by_ref[overview.hero_id] = overview
        if initial or self._selected_hero_ref is None:
            self._selected_hero_ref = self._hero_overviews[0].template_id
        average_power = sum(item.final_power for item in self._hero_overviews) // max(1, len(self._hero_overviews))
        self.hero_collection_var.set(f"已拥有 {len(self._hero_overviews)} 名武将｜平均战力 {average_power}")
        self._normalize_formation_filters()
        self._rebuild_hero_strip()
        self._rebuild_formation_hero_roster()
        self._show_selected_hero_detail()
        if self._hero_detail_window is not None and self._hero_detail_window.winfo_exists() and self._hero_detail_current_ref is not None:
            self._populate_hero_detail(self._hero_detail_current_ref)

    def refresh_profile_page(self) -> None:
        player = self.app.state.player
        if player is None:
            self.my_profile_var.set("当前没有可展示的主公信息")
            self.my_progress_var.set("当前没有可展示的战役信息")
            self.my_idle_var.set("当前没有可展示的养成信息")
            self.my_save_detail_var.set("当前没有可展示的存档信息")
            return

        resource_overview = self.app.get_resource_overview()
        formation_overview = self.app.get_active_formation_overview()
        stage_overviews = self._stage_overviews or self.app.list_stage_overviews()
        unlocked_stages = [item for item in stage_overviews if item.unlocked]
        completed_stages = [item for item in stage_overviews if item.completed]
        best_stage = completed_stages[-1].stage_name if completed_stages else "尚未通关"
        save_overviews = self.app.list_save_slot_overviews()
        existing_saves = [item.slot for item in save_overviews if item.exists]

        self.my_profile_var.set(
            f"主公：{player.profile.name}\n"
            f"当前战力：{player.profile.power}\n"
            f"体力：{resource_overview.stamina}/{resource_overview.max_stamina}\n"
            f"当前阵容：{formation_overview.formation_name}｜上阵 {len(formation_overview.slots)} 名武将"
        )
        self.my_progress_var.set(
            f"已解锁关卡：{len(unlocked_stages)} / {len(stage_overviews)}\n"
            f"已通关关卡：{len(completed_stages)}\n"
            f"主线进度：{best_stage}\n"
            f"当前选中关卡：{self._selected_stage_id or '无'}"
        )
        self.my_idle_var.set(
            f"挂机关卡：{resource_overview.idle_stage_name or '暂无'}\n"
            f"快速挂机剩余：{resource_overview.quick_idle_remaining}/{resource_overview.quick_idle_limit}\n"
            f"体力购买剩余：{resource_overview.stamina_purchase_remaining}/{resource_overview.stamina_purchase_limit}\n"
            f"挂机预览：{resource_overview.idle_rewards_preview or {'暂无': 0}}"
        )
        self.my_save_detail_var.set(
            f"当前槽位：{self.app.state.current_slot}\n"
            f"可用存档：{existing_saves or ['暂无']}\n"
            f"选中槽位：{self._selected_save_slot}\n"
            f"已激活导航：{self.active_nav_var.get()}"
        )

    def refresh_stage_scene(self, *, initial: bool = False) -> None:
        self._stage_overviews = self.app.list_stage_overviews()
        if not self._stage_overviews:
            self.stage_map_canvas.render(None)
            self.stage_title_var.set("主线关卡")
            self.stage_meta_var.set("当前没有可展示关卡")
            self.stage_badge_var.set("章节待命")
            self.stage_progress_var.set("暂无关卡")
            self.scene_banner_var.set("地图尚未生成可进入节点。")
            return
        if initial or self._selected_stage_id is None:
            unlocked = next((item.stage_id for item in self._stage_overviews if item.unlocked), None)
            self._selected_stage_id = unlocked or self._stage_overviews[0].stage_id
        self.stage_map_canvas.render(build_stage_map_scene(self._stage_overviews, selected_stage_id=self._selected_stage_id))
        self.show_map_scene()
        self._show_selected_stage_detail()

    def refresh_formation_panel(self) -> None:
        overview = self.app.get_active_formation_overview()
        draft_power = self._resolve_formation_power(self._formation_draft_positions)
        self.formation_power_var.set(
            f"阵容战力：{overview.power}" if not self._formation_draft_dirty else f"阵容战力：{overview.power}｜草稿 {draft_power}"
        )
        self.formation_preset_var.set(
            f"当前预设：{overview.formation_name}"
            f"{'｜草稿待应用' if self._formation_draft_dirty else ''}"
        )
        self._normalize_formation_filters()
        self._update_formation_filter_summary()
        self._update_formation_draft_summary()
        player = self.app.state.player
        current_positions = dict(self._formation_draft_positions)
        selected_position = self._find_active_formation_position_for_hero(self._selected_hero_ref) if self._selected_hero_ref is not None else None
        for position, slot_card in self._formation_slot_cards.items():
            hero_ref = current_positions.get(position)
            resolved_hero = self.app.hero_service.resolve_best_card(player.heroes, hero_ref) if player is not None and hero_ref is not None else None
            hero_name = resolved_hero.name if resolved_hero is not None else None
            hero_overview = None
            if resolved_hero is not None:
                hero_overview = self._hero_overview_by_ref.get(resolved_hero.template_id) or self._hero_overview_by_ref.get(resolved_hero.id)
            self._formation_slot_title_vars[position].set(self.POSITION_LABELS[position])
            self._slot_label_vars[position].set(hero_name or "待命")
            if hero_overview is not None:
                self._formation_slot_meta_vars[position].set(f"{hero_overview.camp} · {hero_overview.hero_quality} · Lv.{hero_overview.hero_level}")
                self._formation_slot_badge_vars[position].set("草稿上阵")
            else:
                self._formation_slot_meta_vars[position].set("点击或拖拽到此站位部署武将")
                self._formation_slot_badge_vars[position].set("空位")
            if self._selected_formation_position is not None and position == self._selected_formation_position:
                card_bg = self.ACCENT
                badge_bg = "#08111d"
                badge_fg = self.GOLD
                badge_text = "当前站位"
            elif position == selected_position:
                card_bg = self.GOLD
                badge_bg = "#5b3f00"
                badge_fg = self.GOLD
                badge_text = "选中武将所在位"
            elif self._formation_draft_dirty and hero_ref != self._formation_draft_base_positions.get(position):
                card_bg = self.GOLD
                badge_bg = "#5b3f00"
                badge_fg = self.GOLD
                badge_text = "草稿变更"
            elif hero_name is not None:
                card_bg = self.PANEL_SOFT
                badge_bg = "#102033"
                badge_fg = self.GOLD
                badge_text = "已驻守"
            else:
                card_bg = self.PANEL_ALT
                badge_bg = "#1b2a3d"
                badge_fg = self.MUTED
                badge_text = "待部署"
            self._formation_slot_badge_vars[position].set(badge_text)
            slot_card.configure(bg=card_bg, highlightbackground=self._resolve_awakening_border_color(hero_overview.awakening_color if hero_overview is not None else None))
            for child in slot_card.winfo_children():
                if isinstance(child, (tk.Frame, tk.Label)):
                    current_bg = child.cget("bg")
                    if current_bg in {self.PANEL_ALT, self.PANEL_SOFT, self.ACCENT, self.GOLD}:
                        child.configure(bg=card_bg)
            badge_label = slot_card.winfo_children()[4]
            if isinstance(badge_label, tk.Label):
                badge_label.configure(bg=badge_bg, fg=badge_fg)

    def _available_formation_filter_values(self, filter_key: str) -> list[str]:
        if filter_key == "camp":
            return ["全部", *sorted({overview.camp for overview in self._hero_overviews})]
        if filter_key == "quality":
            quality_order = {"S+": 0, "S": 1, "A": 2, "B": 3, "C": 4}
            qualities = sorted({overview.hero_quality for overview in self._hero_overviews}, key=lambda item: (quality_order.get(item, 99), item))
            return ["全部", *qualities]
        return ["全部", "未上阵", "已上阵"]

    def _normalize_formation_filters(self) -> None:
        for filter_key in ("camp", "quality", "deployed"):
            options = self._available_formation_filter_values(filter_key)
            attr_name = f"_formation_filter_{filter_key}"
            if getattr(self, attr_name) not in options:
                setattr(self, attr_name, "全部")

    def _filtered_formation_hero_overviews(self) -> list[HeroSkillOverview]:
        filtered: list[HeroSkillOverview] = []
        for overview in self._hero_overviews:
            deployed_position = self._find_active_formation_position_for_hero(overview.template_id)
            if self._formation_filter_camp != "全部" and overview.camp != self._formation_filter_camp:
                continue
            if self._formation_filter_quality != "全部" and overview.hero_quality != self._formation_filter_quality:
                continue
            if self._formation_filter_deployed == "未上阵" and deployed_position is not None:
                continue
            if self._formation_filter_deployed == "已上阵" and deployed_position is None:
                continue
            filtered.append(overview)
        return filtered

    def _update_formation_filter_summary(self) -> None:
        self._formation_filter_button_vars["camp"].set(f"阵营：{self._formation_filter_camp}")
        self._formation_filter_button_vars["quality"].set(f"品质：{self._formation_filter_quality}")
        deployed_label = "全部" if self._formation_filter_deployed == "全部" else self._formation_filter_deployed
        self._formation_filter_button_vars["deployed"].set(f"状态：{deployed_label}")
        filtered_count = len(self._filtered_formation_hero_overviews())
        total_count = len(self._hero_overviews)
        active_tags = []
        if self._formation_filter_camp != "全部":
            active_tags.append(f"阵营 {self._formation_filter_camp}")
        if self._formation_filter_quality != "全部":
            active_tags.append(f"品质 {self._formation_filter_quality}")
        if self._formation_filter_deployed != "全部":
            active_tags.append(self._formation_filter_deployed)
        summary = f"筛选：{'｜'.join(active_tags) if active_tags else '全部武将'}｜显示 {filtered_count}/{total_count}"
        if self._selected_hero_ref is not None and filtered_count > 0 and all(item.template_id != self._selected_hero_ref for item in self._filtered_formation_hero_overviews()):
            summary += "｜当前选中武将未在筛选结果中"
        self.formation_filter_var.set(summary)

    def _set_formation_filter(self, filter_key: str, value: str, *, announce: bool = False) -> None:
        options = self._available_formation_filter_values(filter_key)
        normalized_value = value if value in options else "全部"
        setattr(self, f"_formation_filter_{filter_key}", normalized_value)
        self._update_formation_filter_summary()
        self._rebuild_formation_hero_roster()
        if announce:
            self.status_var.set(f"布阵筛选已更新：{self.formation_filter_var.get()}")

    def _cycle_formation_filter(self, filter_key: str) -> None:
        options = self._available_formation_filter_values(filter_key)
        current = getattr(self, f"_formation_filter_{filter_key}")
        current_index = options.index(current) if current in options else 0
        self._set_formation_filter(filter_key, options[(current_index + 1) % len(options)], announce=True)

    def _reset_formation_filters(self) -> None:
        self._formation_filter_camp = "全部"
        self._formation_filter_quality = "全部"
        self._formation_filter_deployed = "全部"
        self._update_formation_filter_summary()
        self._rebuild_formation_hero_roster()
        self.status_var.set("已重置布阵筛选条件")

    def _resolve_formation_power(self, positions: dict[int, str]) -> int:
        player = self.app.state.player
        if player is None:
            return 0
        formation = FormationData(id="formation_draft", name="当前草稿", positions=dict(positions))
        return self.app.formation_service.calculate_power(formation, player.heroes)

    def _update_formation_draft_summary(self) -> None:
        draft_power = self._resolve_formation_power(self._formation_draft_positions)
        hero_count = len(self._formation_draft_positions)
        if self._formation_draft_dirty:
            self.formation_draft_var.set(f"草稿编辑中：上阵 {hero_count}/6｜草稿战力 {draft_power}｜尚未覆盖当前活动阵容")
        else:
            self.formation_draft_var.set(f"草稿状态：已与当前活动阵容同步｜上阵 {hero_count}/6｜战力 {draft_power}")

    def _set_formation_draft_positions(self, positions: dict[int, str]) -> None:
        self._formation_draft_positions = {int(position): hero_ref for position, hero_ref in sorted(positions.items()) if hero_ref}
        self._formation_draft_dirty = self._formation_draft_positions != self._formation_draft_base_positions
        self._update_formation_draft_summary()

    def _build_formation_draft(self) -> FormationData:
        active = self.app.get_active_formation()
        formation_name = active.name if active is not None else "当前阵容"
        return FormationData(id="formation_draft", name=f"{formation_name}草稿", positions=dict(self._formation_draft_positions))

    def _reset_formation_draft_from_active(self) -> None:
        active = self.app.get_active_formation()
        positions = dict(active.positions) if active is not None else {}
        self._formation_draft_base_positions = dict(positions)
        self._formation_drag_source = None
        self._set_formation_draft_positions(positions)

    def _find_active_formation_position_for_hero(self, hero_ref: str) -> int | None:
        player = self.app.state.player
        for position, current_ref in self._formation_draft_positions.items():
            if hero_ref == current_ref:
                return position
            if player is None:
                continue
            resolved = self.app.hero_service.resolve_best_card(player.heroes, current_ref)
            if resolved is not None and hero_ref in {resolved.id, resolved.template_id}:
                return position
        return None

    def refresh_save_panel(self) -> None:
        self.save_var.set(f"存档槽位：{self._selected_save_slot}（当前已加载 {self.app.state.current_slot}）")

    def _resolve_awakening_border_color(self, awakening_color: str | None) -> str:
        if not awakening_color:
            return "#39506f"
        return self.AWAKENING_BORDER_COLORS.get(awakening_color, "#39506f")

    def _rebuild_hero_strip(self) -> None:
        for widget in self._hero_card_frames:
            widget.destroy()
        self._hero_card_frames.clear()
        self._hero_card_state_vars.clear()
        for overview in self._hero_overviews:
            selected = overview.template_id == self._selected_hero_ref
            deployed_position = self._find_active_formation_position_for_hero(overview.template_id)
            card_bg = self.ACCENT if selected else (self.PANEL_SOFT if deployed_position is not None else self.PANEL_ALT)
            fg = "#08111d" if selected else self.TEXT
            state_var = tk.StringVar(value=(f"已上阵 {self.POSITION_LABELS.get(deployed_position, '')}" if deployed_position is not None else "待命卡牌"))
            self._hero_card_state_vars[overview.template_id] = state_var
            card = tk.Frame(
                self.hero_scroll_frame,
                bg=card_bg,
                width=190,
                height=162,
                highlightthickness=2 if selected else 1,
                highlightbackground=self._resolve_awakening_border_color(overview.awakening_color),
            )
            card.pack(side=tk.LEFT, padx=8, pady=6)
            card.pack_propagate(False)
            badge_row = tk.Frame(card, bg=card_bg)
            badge_row.pack(fill=tk.X, padx=8, pady=(8, 2))
            tk.Label(badge_row, text=overview.camp, bg="#102033", fg=self.GOLD, font=("Microsoft YaHei UI", 8, "bold"), padx=8, pady=3).pack(side=tk.LEFT)
            tk.Label(badge_row, textvariable=state_var, bg=(self.GOLD if deployed_position is not None else self.PANEL_ALT), fg=("#08111d" if deployed_position is not None else fg), font=("Microsoft YaHei UI", 8, "bold"), padx=8, pady=3).pack(side=tk.RIGHT)
            portrait = tk.Canvas(card, width=150, height=52, bg="#2d4666", highlightthickness=0)
            portrait.pack(pady=(2, 4))
            portrait.create_rectangle(10, 8, 140, 44, fill="#3e5f85", outline="")
            portrait.create_text(75, 18, text=overview.hero_quality, fill=self.GOLD, font=("Microsoft YaHei UI", 9, "bold"))
            portrait.create_text(75, 32, text="立绘占位 / 可替换资源", fill=self.TEXT, font=("Microsoft YaHei UI", 9, "bold"))
            tk.Label(card, text=overview.hero_name, bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 11, "bold")).pack()
            tk.Label(card, text=f"{overview.role} · {overview.hero_quality} · {overview.awakening_level}", bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 9)).pack()
            tk.Label(card, text=f"Lv.{overview.hero_level} ｜ 战力 {overview.final_power}", bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 9)).pack()
            tk.Button(card, text=("查看详情" if selected else "点我查看"), command=lambda ref=overview.template_id: self.open_hero_detail(ref), bg=self.GOLD, fg="#08111d", relief=tk.FLAT, cursor="hand2", font=("Microsoft YaHei UI", 9, "bold"), padx=12, pady=4).pack(pady=(10, 0))
            self._bind_click_recursive(card, lambda ref=overview.template_id: self.open_hero_detail(ref))
            self._hero_card_frames.append(card)
        self.hero_scroll_canvas.configure(scrollregion=self.hero_scroll_canvas.bbox("all"))

    def _sync_hero_strip_width(self, event: tk.Event[tk.Misc]) -> None:
        self.hero_scroll_canvas.itemconfigure(self.hero_scroll_window, height=event.height)
        self.hero_scroll_canvas.configure(scrollregion=self.hero_scroll_canvas.bbox("all"))

    def _sync_formation_hero_strip_width(self, event: tk.Event[tk.Misc]) -> None:
        self.formation_hero_scroll_canvas.itemconfigure(self.formation_hero_scroll_window, height=event.height)
        self.formation_hero_scroll_canvas.configure(scrollregion=self.formation_hero_scroll_canvas.bbox("all"))

    def _rebuild_formation_hero_roster(self) -> None:
        for widget in self._formation_hero_card_frames:
            widget.destroy()
        self._formation_hero_card_frames.clear()
        filtered_overviews = self._filtered_formation_hero_overviews()
        self._update_formation_filter_summary()
        if not filtered_overviews:
            empty_card = tk.Frame(
                self.formation_hero_scroll_frame,
                bg="#132131",
                width=260,
                height=150,
                highlightthickness=1,
                highlightbackground="#30445f",
            )
            empty_card.pack(side=tk.LEFT, padx=8, pady=6)
            empty_card.pack_propagate(False)
            tk.Label(empty_card, text="当前筛选下暂无武将", bg="#132131", fg=self.TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(expand=True)
            tk.Label(empty_card, text="可尝试切换阵营 / 品质 / 状态筛选", bg="#132131", fg=self.MUTED, font=("Microsoft YaHei UI", 9)).pack(pady=(0, 18))
            self._formation_hero_card_frames.append(empty_card)
            self.formation_hero_scroll_canvas.configure(scrollregion=self.formation_hero_scroll_canvas.bbox("all"))
            return
        for overview in filtered_overviews:
            selected = overview.template_id == self._selected_hero_ref
            deployed_position = self._find_active_formation_position_for_hero(overview.template_id)
            is_deployed = deployed_position is not None
            card_bg = self.PANEL_SOFT if is_deployed else (self.ACCENT if selected else self.PANEL_ALT)
            fg = "#08111d" if selected else self.TEXT
            card = tk.Frame(
                self.formation_hero_scroll_frame,
                bg=card_bg,
                width=190,
                height=150,
                highlightthickness=2 if selected and not is_deployed else 1,
                highlightbackground=self._resolve_awakening_border_color(overview.awakening_color),
            )
            card.pack(side=tk.LEFT, padx=8, pady=6)
            card.pack_propagate(False)
            badge_row = tk.Frame(card, bg=card_bg)
            badge_row.pack(fill=tk.X, padx=8, pady=(8, 4))
            tk.Label(badge_row, text=overview.camp, bg="#102033", fg=self.GOLD, font=("Microsoft YaHei UI", 8, "bold"), padx=8, pady=3).pack(side=tk.LEFT)
            state_text = f"已上阵 {self.POSITION_LABELS.get(deployed_position, '')}" if is_deployed else "点击上阵"
            tk.Label(badge_row, text=state_text, bg=(self.GOLD if deployed_position is not None else self.PANEL_ALT), fg=("#08111d" if deployed_position is not None else fg), font=("Microsoft YaHei UI", 8, "bold"), padx=8, pady=3).pack(side=tk.RIGHT)
            portrait = tk.Canvas(card, width=156, height=48, bg="#2d4666", highlightthickness=0)
            portrait.pack(pady=(0, 4))
            portrait.create_rectangle(12, 8, 144, 40, fill="#3e5f85", outline="")
            portrait.create_text(78, 24, text="阵容武将卡", fill=self.TEXT, font=("Microsoft YaHei UI", 10, "bold"))
            tk.Label(card, text=overview.hero_name, bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 11, "bold")).pack()
            tk.Label(card, text=f"{overview.role} · {overview.hero_quality} · Lv.{overview.hero_level}", bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 9)).pack()
            tk.Label(card, text=f"战力 {overview.final_power} ｜ {overview.awakening_level}", bg=card_bg, fg=fg, font=("Microsoft YaHei UI", 9)).pack()
            footer_text = "已上阵" if is_deployed else ("点击立即上阵" if self._selected_formation_position is not None else "请先选站位")
            tk.Label(card, text=footer_text, bg=card_bg, fg=(self.GOLD if is_deployed else fg), font=("Microsoft YaHei UI", 9, "bold")).pack(pady=(10, 0))
            if not is_deployed:
                self._bind_click_recursive(card, lambda ref=overview.template_id: self._on_formation_hero_card_clicked(ref))
                self._bind_drag_press_recursive(card, lambda ref=overview.template_id: self._begin_hero_drag(ref))
            self._formation_hero_card_frames.append(card)
        self.formation_hero_scroll_canvas.configure(scrollregion=self.formation_hero_scroll_canvas.bbox("all"))

    def _on_formation_hero_card_clicked(self, hero_ref: str) -> None:
        if self._find_active_formation_position_for_hero(hero_ref) is not None:
            self.status_var.set("该武将已上阵，无法重复选择")
            return
        self._selected_hero_ref = hero_ref
        if self._selected_formation_position is None:
            self._rebuild_hero_strip()
            self._rebuild_formation_hero_roster()
            self._show_selected_hero_detail()
            self.status_var.set("请先选择一个阵位，再点击武将完成上阵")
            return
        self.deploy_selected_hero_to_slot()

    def select_hero(self, hero_ref: str) -> None:
        self._selected_hero_ref = hero_ref
        self._rebuild_hero_strip()
        self._rebuild_formation_hero_roster()
        self.refresh_formation_panel()
        self._show_selected_hero_detail()
        self.status_var.set(f"已选中武将：{self.hero_title_var.get()}")

    def open_selected_hero_detail(self) -> None:
        if self._selected_hero_ref is None:
            self.status_var.set("当前没有可查看详情的武将")
            return
        self.open_hero_detail(self._selected_hero_ref)

    def open_hero_detail(self, hero_ref: str) -> None:
        self.select_hero(hero_ref)
        self._ensure_hero_detail_window()
        self._populate_hero_detail(hero_ref)
        if self._hero_detail_window is not None and self._hero_detail_window.winfo_exists():
            self._hero_detail_window.deiconify()
            self._hero_detail_window.lift()
            self._hero_detail_window.focus_force()
        self.status_var.set(f"已打开 {self.hero_title_var.get()} 详情菜单")

    def _show_selected_hero_detail(self) -> None:
        if self._selected_hero_ref is None:
            self.hero_title_var.set("武将详情")
            self.hero_meta_var.set("请在底部英雄条选择一名武将")
            self.hero_detail_selected_var.set("当前未选中武将")
            for variable in self.hero_chip_vars.values():
                variable.set("--")
            return
        overview = self.app.get_hero_skill_overview(self._selected_hero_ref)
        self.hero_title_var.set(overview.hero_name)
        self.hero_chip_vars["camp"].set(f"阵营 {overview.camp}")
        self.hero_chip_vars["role"].set(f"定位 {overview.role}")
        self.hero_chip_vars["quality"].set(f"品质 {overview.hero_quality}")
        self.hero_chip_vars["level"].set(f"等级 Lv.{overview.hero_level}")
        self.hero_chip_vars["power"].set(f"战力 {overview.final_power}")
        skill_names = " ｜ ".join(skill.skill_name for skill in overview.skills)
        treasure_text = "已激活" if overview.has_rare_treasure else "未激活"
        self.hero_detail_selected_var.set(f"当前选中：{overview.hero_name}｜点击按钮或卡牌可查看完整详情")
        self.hero_meta_var.set(
            f"职业：{overview.profession}｜觉醒：{overview.awakening_level}｜奇珍：{treasure_text}\n"
            f"技能阵列：{skill_names}\n"
            f"来源：{overview.obtained_from}"
        )

    def select_stage(self, stage_id: str) -> None:
        self.stop_replay()
        self._hide_settlement_overlay()
        self._selected_stage_id = stage_id
        self.stage_map_canvas.render(build_stage_map_scene(self._stage_overviews, selected_stage_id=self._selected_stage_id))
        self._show_selected_stage_detail()
        self.status_var.set(f"已选择关卡：{stage_id}")

    def _show_selected_stage_detail(self) -> None:
        if self._selected_stage_id is None:
            self.stage_title_var.set("主线关卡")
            self.stage_meta_var.set("请先选择关卡")
            self.stage_badge_var.set("章节待命")
            self.stage_progress_var.set("尚未锁定目标")
            self.scene_banner_var.set("主城视野已展开，点击地图节点进入主线。")
            return
        stage_overview = next((item for item in self._stage_overviews if item.stage_id == self._selected_stage_id), None)
        try:
            preparation = self.app.open_stage_battle_entry(self._selected_stage_id, formation_positions=dict(self._formation_draft_positions))
            self.stage_title_var.set(f"{preparation.stage_name} · {preparation.stage_id}")
            self.stage_meta_var.set(
                f"推荐战力 {preparation.recommended_power} ｜ 当前战力 {preparation.current_power} ｜ 体力 {preparation.current_stamina} ｜ 消耗 {preparation.challenge_cost}"
            )
            if stage_overview is not None:
                progress_text = f"{stage_overview.chapter_name} · {'已通关' if stage_overview.completed else '推进中'}"
                if stage_overview.completed:
                    progress_text += f" · {stage_overview.stars}★"
                self.stage_badge_var.set(progress_text)
                self.stage_progress_var.set(f"推荐 {stage_overview.recommended_power} / 当前 {stage_overview.current_power}")
            else:
                self.stage_badge_var.set("当前章节")
                self.stage_progress_var.set(f"推荐 {preparation.recommended_power}")
            self.stage_hint_var.set("当前为主线地图视图。点击“开始战斗”切入全屏战场，点击“扫荡关卡”快速结算。")
            self.scene_banner_var.set(f"地图目标已锁定：{preparation.stage_name}，阵容确认后即可开战。")
        except ValueError as exc:
            self.stage_title_var.set(self._selected_stage_id)
            self.stage_meta_var.set("当前关卡尚不可进入")
            if stage_overview is not None:
                self.stage_badge_var.set(f"{stage_overview.chapter_name} · 未解锁")
                self.stage_progress_var.set(stage_overview.lock_reason or "条件不足")
            else:
                self.stage_badge_var.set("未解锁")
                self.stage_progress_var.set("条件不足")
            self.stage_hint_var.set(str(exc))
            self.scene_banner_var.set(f"关卡 {self._selected_stage_id} 暂不可进入。")

    def show_map_scene(self) -> None:
        self.show_section("战役")
        self._hide_settlement_overlay()
        self.battle_canvas.pack_forget()
        self.stage_map_canvas.pack(fill=tk.BOTH, expand=True)
        self.play_button.configure(state=tk.NORMAL)
        self.scene_mode_var.set("地图巡航")

    def show_battle_scene(self) -> None:
        self.show_section("战役")
        self.stage_map_canvas.pack_forget()
        self.battle_canvas.pack(fill=tk.BOTH, expand=True)
        self.scene_mode_var.set("战场回放")

    def _highlight_formation_position(self, position: int) -> None:
        self._selected_formation_position = position
        self.refresh_formation_panel()

    def select_formation_position(self, position: int) -> None:
        if position in self._formation_draft_positions:
            self._highlight_formation_position(position)
            self.undeploy_selected_slot()
            return
        self._highlight_formation_position(position)
        self.status_var.set(f"已选择阵容站位：{self.POSITION_LABELS.get(position, f'{position}号位')}")

    def _begin_hero_drag(self, hero_ref: str) -> None:
        self._formation_drag_source = ("hero", hero_ref)
        hero_name = self._hero_overview_by_ref.get(hero_ref).hero_name if hero_ref in self._hero_overview_by_ref else self.app.get_hero_skill_overview(hero_ref).hero_name
        self.status_var.set(f"已抓取武将卡：{hero_name}，释放到上方站位即可快速布阵")

    def _begin_slot_drag(self, position: int) -> None:
        self._highlight_formation_position(position)
        if position in self._formation_draft_positions:
            self._formation_drag_source = ("slot", position)
            self.status_var.set(f"已抓取 {self.POSITION_LABELS.get(position, f'{position}号位')}，释放到其他站位即可换位")
        else:
            self.status_var.set(f"已选择阵容站位：{self.POSITION_LABELS.get(position, f'{position}号位')}")

    def _handle_slot_release(self, position: int) -> None:
        if self._formation_drag_source is None:
            self.select_formation_position(position)
            return
        source_kind, source_value = self._formation_drag_source
        self._formation_drag_source = None
        if source_kind == "hero":
            self._selected_hero_ref = str(source_value)
            self._selected_formation_position = position
            self.deploy_selected_hero_to_slot()
            return
        source_position = int(source_value)
        if source_position == position:
            if position in self._formation_draft_positions:
                self.undeploy_slot(position)
            else:
                self.select_formation_position(position)
            return
        player = self.app.state.player
        if player is None:
            self.status_var.set("当前没有可编辑阵容的玩家数据")
            return
        try:
            draft = self._build_formation_draft()
            self.app.formation_service.swap_positions(draft, source_position, position)
            self.app.formation_service.validate_or_raise(draft, player.heroes)
            self._set_formation_draft_positions(draft.positions)
            self._selected_formation_position = position
            self._sync_views_after_formation_change()
            self.scene_banner_var.set(f"草稿换位完成：{self.POSITION_LABELS.get(source_position)} → {self.POSITION_LABELS.get(position)}")
            self.status_var.set(f"已拖拽调整 {source_position} 与 {position} 号位")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def _sync_views_after_formation_change(self) -> None:
        current_section = self.active_nav_var.get()
        self.refresh_resources()
        self.refresh_stage_scene()
        self.refresh_formation_panel()
        self._rebuild_hero_strip()
        self._rebuild_formation_hero_roster()
        self.refresh_profile_page()
        if current_section != "战役":
            self.show_section(current_section)

    def _switch_formation_preset(self, formation_id: str) -> None:
        try:
            formation = self.app.switch_formation_preset(formation_id)
            self._reset_formation_draft_from_active()
            self._sync_views_after_formation_change()
            self.scene_banner_var.set(f"当前活动阵容已切换为：{formation.name}，布阵草稿已同步重置。")
            self.status_var.set(f"已切换阵容预设：{formation.name}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def quick_fill_formation(self) -> None:
        player = self.app.state.player
        if player is None:
            self.status_var.set("当前没有可编辑阵容的玩家数据")
            return
        occupied_positions = set(self._formation_draft_positions)
        empty_positions = [position for position in range(1, 7) if position not in occupied_positions]
        if not empty_positions:
            self.status_var.set("当前草稿已满，无需一键补阵")
            return
        candidates = [item for item in self._filtered_formation_hero_overviews() if self._find_active_formation_position_for_hero(item.template_id) is None]
        if not candidates:
            self.status_var.set("当前筛选结果中没有可自动上阵的武将")
            return
        assigned: list[tuple[str, int]] = []
        try:
            draft = self._build_formation_draft()
            for position, hero_overview in zip(empty_positions, candidates):
                self.app.formation_service.deploy_hero(draft, player.heroes, position, hero_overview.template_id)
                assigned.append((hero_overview.hero_name, position))
            self.app.formation_service.validate_or_raise(draft, player.heroes)
            self._set_formation_draft_positions(draft.positions)
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self._sync_views_after_formation_change()
        preview_text = "、".join(f"{name}->{position}号位" for name, position in assigned[:3])
        if len(assigned) > 3:
            preview_text += "…"
        self.scene_banner_var.set(f"已按当前筛选补全布阵草稿：{preview_text}")
        self.status_var.set(f"已为草稿一键补阵 {len(assigned)} 名武将")

    def clear_active_formation(self) -> None:
        occupied_positions = list(self._formation_draft_positions)
        if not occupied_positions:
            self.status_var.set("当前布阵草稿已为空")
            return
        self._set_formation_draft_positions({})
        self._sync_views_after_formation_change()
        self.scene_banner_var.set("当前布阵草稿已清空，可重新拖拽或点击布阵。")
        self.status_var.set(f"已清空草稿中的 {len(occupied_positions)} 名武将")

    def apply_formation_draft(self) -> None:
        active = self.app.get_active_formation()
        if active is None:
            self.status_var.set("当前没有可应用草稿的活动阵容")
            return
        try:
            self.app.save_formation_preset(active.id, dict(self._formation_draft_positions), name=active.name)
            self._reset_formation_draft_from_active()
            self._sync_views_after_formation_change()
            self.scene_banner_var.set(f"布阵草稿已应用到当前活动阵容：{active.name}")
            self.status_var.set("已应用布阵草稿")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def discard_formation_draft(self) -> None:
        if not self._formation_draft_dirty:
            self.status_var.set("当前没有待放弃的布阵草稿改动")
            return
        self._set_formation_draft_positions(self._formation_draft_base_positions)
        self._formation_drag_source = None
        self._sync_views_after_formation_change()
        self.scene_banner_var.set("已放弃布阵草稿，当前展示活动阵容原始站位。")
        self.status_var.set("已放弃布阵草稿")

    def deploy_selected_hero_to_slot(self) -> None:
        if self._selected_hero_ref is None:
            self.status_var.set("请先选择一名武将")
            return
        if self._selected_formation_position is None:
            self.status_var.set("请先选择一个阵位")
            return
        player = self.app.state.player
        if player is None:
            self.status_var.set("当前没有可编辑阵容的玩家数据")
            return
        try:
            draft = self._build_formation_draft()
            current_position = self._find_active_formation_position_for_hero(self._selected_hero_ref)
            if current_position == self._selected_formation_position:
                self.refresh_formation_panel()
                self.status_var.set(f"当前武将已在 {self._selected_formation_position} 号位")
                return

            if current_position is not None:
                self.app.formation_service.swap_positions(draft, current_position, self._selected_formation_position)
                status_text = f"已在草稿中将武将从 {current_position} 号位调整到 {self._selected_formation_position} 号位"
            else:
                self.app.formation_service.deploy_hero(draft, player.heroes, self._selected_formation_position, self._selected_hero_ref)
                status_text = f"已将武将加入草稿并布阵到 {self._selected_formation_position} 号位"

            self.app.formation_service.validate_or_raise(draft, player.heroes)
            self._set_formation_draft_positions(draft.positions)
            self._sync_views_after_formation_change()
            self.scene_banner_var.set(f"布阵草稿已更新：{self.hero_title_var.get()} -> {self.POSITION_LABELS.get(self._selected_formation_position, f'{self._selected_formation_position}号位')}")
            self.status_var.set(status_text)
        except ValueError as exc:
            self.status_var.set(str(exc))

    def undeploy_selected_slot(self) -> None:
        if self._selected_formation_position is None:
            self.status_var.set("请先选择一个阵位")
            return
        self.undeploy_slot(self._selected_formation_position)

    def undeploy_slot(self, position: int) -> None:
        player = self.app.state.player
        if player is None:
            self.status_var.set("当前没有可编辑阵容的玩家数据")
            return
        try:
            draft = self._build_formation_draft()
            self.app.formation_service.undeploy_hero(draft, position)
            self.app.formation_service.validate_or_raise(draft, player.heroes)
            self._set_formation_draft_positions(draft.positions)
            self._selected_formation_position = position
            self._sync_views_after_formation_change()
            self.scene_banner_var.set(f"{self.POSITION_LABELS.get(position, f'{position}号位')} 已从草稿中撤离出阵。")
            self.status_var.set(f"已从草稿下阵 {position} 号位武将")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def _ensure_hero_detail_window(self) -> None:
        if self._hero_detail_window is not None and self._hero_detail_window.winfo_exists():
            return
        window = tk.Toplevel(self.root)
        window.withdraw()
        window.title("武将详情")
        window.geometry("980x760")
        window.minsize(880, 680)
        window.configure(bg=self.BG)
        window.transient(self.root)
        window.bind("<Escape>", lambda _event: self._close_hero_detail_window())
        window.protocol("WM_DELETE_WINDOW", self._close_hero_detail_window)

        header = tk.Frame(window, bg="#0b1220", height=88)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, textvariable=self._hero_detail_title_var, fg=self.TEXT, bg="#0b1220", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(header, textvariable=self._hero_detail_meta_var, fg=self.MUTED, bg="#0b1220", font=("Microsoft YaHei UI", 10), wraplength=900, justify=tk.LEFT).pack(anchor="w", padx=18, pady=(0, 12))

        content = tk.Frame(window, bg=self.BG)
        content.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        left_column = tk.Frame(content, bg=self.BG, width=300)
        left_column.pack(side=tk.LEFT, fill=tk.Y)
        left_column.pack_propagate(False)
        right_column = tk.Frame(content, bg=self.BG)
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(14, 0))

        stats_panel = self._create_panel(left_column, "属性")
        stats_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(stats_panel, textvariable=self._hero_detail_stats_var, justify=tk.LEFT, wraplength=250, fg=self.TEXT, bg=self.PANEL, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(8, 12))

        equipment_panel = self._create_panel(left_column, "装备")
        equipment_panel.pack(fill=tk.X, pady=(0, 12))
        tk.Label(equipment_panel, textvariable=self._hero_detail_equipment_var, justify=tk.LEFT, wraplength=250, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(8, 8))
        self._hero_detail_equipment_frame = tk.Frame(equipment_panel, bg=self.PANEL)
        self._hero_detail_equipment_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        treasure_panel = self._create_panel(left_column, "专属奇珍 × 9")
        treasure_panel.pack(fill=tk.X)
        tk.Label(treasure_panel, textvariable=self._hero_detail_treasure_var, justify=tk.LEFT, wraplength=250, fg=self.MUTED, bg=self.PANEL, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(8, 8))
        self._hero_detail_treasure_frame = tk.Frame(treasure_panel, bg=self.PANEL)
        self._hero_detail_treasure_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        skills_panel = self._create_panel(right_column, "技能详情")
        skills_panel.pack(fill=tk.BOTH, expand=True)
        skills_container = tk.Frame(skills_panel, bg=self.PANEL)
        skills_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))
        skills_scrollbar = tk.Scrollbar(skills_container)
        skills_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._hero_detail_skills_text = tk.Text(
            skills_container,
            bg="#102033",
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),
            yscrollcommand=skills_scrollbar.set,
            padx=12,
            pady=12,
        )
        self._hero_detail_skills_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        skills_scrollbar.configure(command=self._hero_detail_skills_text.yview)
        self._hero_detail_skills_text.tag_configure("skill_title", foreground=self.GOLD, font=("Microsoft YaHei UI", 12, "bold"))
        self._hero_detail_skills_text.tag_configure("skill_meta", foreground=self.MUTED, font=("Microsoft YaHei UI", 9, "bold"))
        self._hero_detail_skills_text.tag_configure("skill_current", background="#26445f", foreground=self.GOLD)

        footer = tk.Frame(window, bg="#0b1220", height=54)
        footer.pack(fill=tk.X)
        footer.pack_propagate(False)
        tk.Button(footer, text="关闭", command=self._close_hero_detail_window, bg=self.PANEL_SOFT, fg=self.TEXT, relief=tk.FLAT, padx=20, pady=8, cursor="hand2", font=("Microsoft YaHei UI", 10, "bold")).pack(side=tk.RIGHT, padx=14, pady=10)

        self._hero_detail_window = window

    def _close_hero_detail_window(self) -> None:
        if self._hero_detail_window is not None and self._hero_detail_window.winfo_exists():
            self._hero_detail_window.destroy()
        self._hero_detail_window = None

    def _populate_hero_detail(self, hero_ref: str) -> None:
        hero = self._resolve_player_hero(hero_ref)
        if hero is None:
            self.status_var.set(f"武将不存在：{hero_ref}")
            return
        overview = self.app.get_hero_skill_overview(hero_ref)
        self._hero_detail_current_ref = hero_ref
        self._hero_detail_title_var.set(f"{overview.hero_name}｜详情菜单")
        self._hero_detail_meta_var.set(
            f"阵营 {overview.camp}｜职业 {overview.profession}｜定位 {overview.role}｜品质 {overview.hero_quality}｜觉醒 {overview.awakening_level}\n"
            f"等级 Lv.{overview.hero_level}/{overview.hero_level_cap}｜战力 {overview.final_power}｜来源 {overview.obtained_from}｜奇珍 {'已激活' if overview.has_rare_treasure else '未激活'}"
        )
        self._hero_detail_stats_var.set(
            f"生命 {int(overview.final_stats.hp)}\n"
            f"攻击 {int(overview.final_stats.attack)}\n"
            f"防御 {int(overview.final_stats.defense)}\n"
            f"速度 {int(overview.final_stats.speed)}\n"
            f"暴击 {overview.final_stats.crit_rate * 100:.0f}%｜暴伤 {overview.final_stats.crit_damage * 100:.0f}%\n"
            f"破甲 {overview.final_stats.armor_break * 100:.0f}%｜命中 {overview.final_stats.effect_hit * 100:.0f}%｜抵抗 {overview.final_stats.effect_resist * 100:.0f}%"
        )
        equipped_slots = [slot for slot in hero.equipment_slots if slot.is_equipped]
        self._hero_detail_equipment_var.set(
            f"当前装备：已穿戴 {len(equipped_slots)}/{len(hero.equipment_slots)}\n"
            f"装备总加成：{self._format_bonus_summary(hero.current_equipment_bonus())}"
        )
        unlocked_treasure_nodes = [node for node in hero.rare_treasure_nodes if node.is_unlocked]
        locked_slots = "、".join(self._skill_slot_name(slot) for slot in overview.rare_treasure_locked_skill_slots) or "无"
        self._hero_detail_treasure_var.set(
            f"专属奇珍：已激活 {len(unlocked_treasure_nodes)}/{len(hero.rare_treasure_nodes)}\n"
            f"当前 4 级受奇珍限制的槽位：{locked_slots}"
        )
        self._rebuild_hero_detail_equipment(hero)
        self._rebuild_hero_detail_treasures(hero)
        self._render_hero_skill_details(hero, overview)

    def _resolve_player_hero(self, hero_ref: str) -> HeroData | None:
        player = self.app.state.player
        if player is None:
            return None
        return self.app.hero_service.resolve_best_card(player.heroes, hero_ref)

    def _rebuild_hero_detail_equipment(self, hero: HeroData) -> None:
        if self._hero_detail_equipment_frame is None:
            return
        for widget in self._hero_detail_equipment_frame.winfo_children():
            widget.destroy()
        self._hero_detail_equipment_labels.clear()
        for index, slot in enumerate(hero.equipment_slots):
            equipped = slot.is_equipped
            title = slot.item_name or slot.slot_name
            detail_parts = []
            if slot.quality:
                detail_parts.append(slot.quality)
            if slot.level > 0:
                detail_parts.append(f"Lv.{slot.level}")
            detail_line = "｜".join(detail_parts) if detail_parts else ("未装备" if not equipped else "已装备")
            bonus_line = self._format_bonus_summary(slot.stat_bonuses)
            label = tk.Label(
                self._hero_detail_equipment_frame,
                text=f"{slot.slot_name}\n{title}\n{detail_line}\n{bonus_line}",
                bg=(self.GOLD if equipped else self.PANEL_ALT),
                fg=("#08111d" if equipped else self.TEXT),
                font=("Microsoft YaHei UI", 8, "bold"),
                width=10,
                height=5,
                justify=tk.CENTER,
                relief=tk.FLAT,
            )
            label.grid(row=index // 2, column=index % 2, padx=6, pady=6, sticky="nsew")
            self._hero_detail_equipment_labels.append(label)

    def _rebuild_hero_detail_treasures(self, hero: HeroData) -> None:
        if self._hero_detail_treasure_frame is None:
            return
        for widget in self._hero_detail_treasure_frame.winfo_children():
            widget.destroy()
        self._hero_detail_treasure_labels.clear()
        for index, node in enumerate(hero.rare_treasure_nodes):
            node_title = node.node_name
            state_text = "已激活" if node.is_unlocked else "未激活"
            linked_text = self._skill_slot_name(node.linked_skill_slot) if node.linked_skill_slot else "属性位"
            label = tk.Label(
                self._hero_detail_treasure_frame,
                text=f"{node_title}\n{state_text}\n{linked_text}",
                bg=(self.GOLD if node.is_unlocked else self.PANEL_ALT),
                fg=("#08111d" if node.is_unlocked else self.TEXT),
                font=("Microsoft YaHei UI", 8, "bold"),
                width=9,
                height=3,
                justify=tk.CENTER,
                relief=tk.FLAT,
            )
            label.grid(row=index // 3, column=index % 3, padx=4, pady=4, sticky="nsew")
            self._hero_detail_treasure_labels.append(label)

    def _render_hero_skill_details(self, hero: HeroData, overview: HeroSkillOverview) -> None:
        if self._hero_detail_skills_text is None:
            return
        skill_level_map = {skill.slot_key: skill for skill in overview.skills}
        skills = [
            ("passive_1", hero.passive_skills[0]),
            ("passive_2", hero.passive_skills[1]),
            ("passive_3", hero.passive_skill_3),
            ("ultimate", hero.ultimate_skill),
        ]
        text = self._hero_detail_skills_text
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert(tk.END, "基础普攻｜默认动作\n", ("skill_title",))
        text.insert(tk.END, "类型 普攻｜目标 单体｜触发 行动时自动｜固定 100% 攻击\n\n", ("skill_meta",))
        for slot_key, skill in skills:
            current = skill_level_map[slot_key]
            lock_note = "｜4 级受奇珍限制" if current.needs_rare_treasure_for_level_four else ""
            text.insert(tk.END, f"{self._skill_slot_name(slot_key)}｜{skill.name}\n", ("skill_title",))
            text.insert(tk.END, f"类型 {skill.skill_type}｜目标 {skill.target_type}｜触发 {skill.trigger_timing}｜当前 Lv.{current.level}{lock_note}\n", ("skill_meta",))
            max_level = max(
                4,
                max(skill.damage_by_level.keys(), default=skill.level),
                max(skill.hit_count_by_level.keys(), default=skill.level),
                max(skill.effects_by_level.keys(), default=skill.level),
                max(skill.round_start_effects_by_level.keys(), default=skill.level),
            )
            for level in range(1, max_level + 1):
                damage_value = skill.damage_by_level.get(level, skill.damage_coefficient)
                hit_count = skill.hit_count_by_level.get(level, skill.hit_count)
                effects = skill.effects_by_level.get(level, skill.effects)
                round_start_effects = skill.round_start_effects_by_level.get(level, skill.round_start_effects)
                level_tags = ("skill_current",) if level == current.level else ()
                current_mark = "【当前】" if level == current.level else ""
                text.insert(tk.END, f"Lv.{level}{current_mark} 伤害 {self._format_ratio_as_percent(damage_value)}｜段数 x{hit_count}｜能量 {skill.energy_cost}\n", level_tags)
                detail_lines: list[str] = []
                if effects:
                    detail_lines.extend(f"效果：{self._describe_skill_effect(effect)}" for effect in effects)
                if round_start_effects:
                    detail_lines.extend(f"回合开始：{self._describe_skill_effect(effect)}" for effect in round_start_effects)
                if skill.params:
                    detail_lines.append(f"参数：{self._format_params(skill.params)}")
                if not detail_lines:
                    detail_lines.append("无额外效果")
                for line in detail_lines:
                    text.insert(tk.END, f"  - {line}\n", level_tags)
                text.insert(tk.END, "\n")
        text.configure(state=tk.DISABLED)

    @staticmethod
    def _format_ratio(value: float) -> str:
        text = f"{value:.2f}"
        return text.rstrip("0").rstrip(".")

    @classmethod
    def _format_ratio_as_percent(cls, value: float) -> str:
        return f"{cls._format_ratio(value * 100)}% 攻击"

    @staticmethod
    def _skill_slot_name(slot_key: str) -> str:
        return display_skill_slot_name(slot_key)

    @classmethod
    def _format_bonus_summary(cls, bonuses: dict[str, float]) -> str:
        if not bonuses:
            return "暂无"
        stat_names = {
            "hp": "生命",
            "attack": "攻击",
            "defense": "防御",
            "speed": "速度",
            "crit_rate": "暴击",
            "crit_damage": "暴伤",
            "armor_break": "破甲",
            "effect_hit": "命中",
            "effect_resist": "抵抗",
        }
        parts = [f"{stat_names.get(key, key)} {cls._format_ratio(value * 100)}%" for key, value in bonuses.items() if value]
        return "、".join(parts) if parts else "暂无"

    @classmethod
    def _format_params(cls, params: dict[str, object]) -> str:
        formatted: list[str] = []
        for key, value in params.items():
            formatted.append(f"{display_param_name(str(key))}={display_param_value(str(key), value)}")
        return "；".join(formatted)

    @classmethod
    def _describe_skill_effect(cls, effect: SkillEffectData) -> str:
        effect_name = display_name(effect.effect_type)
        chance_text = "" if effect.chance >= 1 else f"，概率 {cls._format_ratio(effect.chance * 100)}%"
        duration_text = ""
        if effect.duration > 0:
            duration_text = f"，持续 {effect.duration} 回合"
        elif effect.duration < 0:
            duration_text = "，持续永久"
        if effect.effect_type in {"heal", "shield", "shield_regen", "bonus_damage_if_target_has_status", "bonus_damage_per_stack"}:
            base = f"{effect_name} {cls._format_ratio(effect.value * 100)}%"
        elif effect.effect_type in {"attack_bonus", "defense_bonus", "speed_bonus", "damage_reduction", "crit_rate_bonus", "crit_damage_bonus"}:
            sign = "+" if effect.value >= 0 else ""
            base = f"{effect_name} {sign}{cls._format_ratio(effect.value * 100)}%"
        elif effect.effect_type == "percent_hp_damage":
            cap = effect.params.get("cap_attack_multiplier")
            base = f"百分比生命伤害 {cls._format_ratio(effect.value * 100)}%"
            if cap is not None:
                base += f"（上限攻击 x{cap}）"
        elif effect.effect_type == "gain_energy_and_heal_on_enemy_death":
            heal_ratio = effect.params.get("heal_attack_ratio")
            heal_text = f"，回血 {cls._format_ratio(float(heal_ratio) * 100)}% 攻击" if heal_ratio is not None else ""
            base = f"敌方阵亡回怒 {int(effect.value)}{heal_text}"
        elif effect.effect_type in {"gain_attack_bonus_on_kill", "crit_rate_bonus_on_kill"}:
            base = f"{effect_name} {cls._format_ratio(effect.value * 100)}%"
        elif effect.effect_type == "gain_extra_turn_on_kill":
            base = f"击杀后额外行动 {int(effect.value)} 次"
        elif effect.effect_type == "apply_status":
            status_name = display_status_name(str(effect.params.get("status_effect_type", effect.status_filter or "未知状态")))
            status_duration = effect.params.get("status_duration", effect.duration)
            base = f"施加 {status_name} {status_duration} 回合"
        elif effect.effect_type == "apply_status_to_attacker_on_receive_attack":
            status_name = display_status_name(str(effect.params.get("status_effect_type", "未知状态")))
            base = f"向攻击者施加 {status_name}"
        elif effect.effect_type == "gain_stack":
            base = f"获得 {display_status_name(str(effect.params.get('stack_name', '层数')))} {cls._format_ratio(effect.value)} 层"
        elif effect.effect_type == "gain_stack_on_receive_attack":
            base = f"受击时获得 {display_status_name(str(effect.params.get('stack_name', '层数')))} {cls._format_ratio(effect.value)} 层（上限 {effect.params.get('max_stacks', '∞')}）"
        elif effect.effect_type == "transform_stack_to_status_on_threshold":
            base = (
                f"{display_status_name(str(effect.params.get('stack_name', '层数')))} 达到 {effect.params.get('threshold', '?')} 层后，"
                f"转为 {display_status_name(str(effect.params.get('status_effect_type', '形态')))}"
            )
        elif effect.effect_type == "follow_up_attack_on_receive_attack_stack_threshold":
            base = (
                f"{display_status_name(str(effect.params.get('stack_name', '层数')))} 达到 {effect.params.get('threshold', '?')} 层时，"
                f"触发 {display_name(str(effect.params.get('action_name', '追击')))}，{effect.params.get('hit_count', 1)} 段，每段 {cls._format_ratio(effect.value * 100)}%"
            )
        elif effect.effect_type == "damage_multiplier_by_target_hp":
            thresholds = effect.params.get("thresholds", [])
            threshold_text = "；".join(
                f"血量≤{cls._format_ratio(float(item.get('max_hp_ratio', 0)) * 100)}% 时 x{cls._format_ratio(float(item.get('multiplier', 1)))}"
                for item in thresholds
                if isinstance(item, dict)
            )
            base = f"按目标血线增伤：{threshold_text or '见技能参数'}"
        elif effect.effect_type == "survive_once":
            base = "受到致命伤害时免疫一次"
        elif effect.effect_type in {"cleanse", "cleanse_random_allies", "dispel"}:
            target = display_status_filter_name(effect.status_filter) or "指定状态"
            base = f"{effect_name} {int(effect.value)} 层 {target}"
        else:
            base = f"{effect_name} 数值={cls._format_ratio(effect.value)}"
        if effect.status_filter and effect.effect_type not in {"apply_status", "cleanse", "cleanse_random_allies", "dispel"}:
            base += f"，关联 {display_status_filter_name(effect.status_filter)}"
        if effect.params and effect.effect_type not in {
            "percent_hp_damage",
            "gain_energy_and_heal_on_enemy_death",
            "apply_status",
            "apply_status_to_attacker_on_receive_attack",
            "gain_stack",
            "gain_stack_on_receive_attack",
            "transform_stack_to_status_on_threshold",
            "follow_up_attack_on_receive_attack_stack_threshold",
            "damage_multiplier_by_target_hp",
            "survive_once",
        }:
            base += f"（{cls._format_params(effect.params)}）"
        return f"{base}{duration_text}{chance_text}"

    def start_selected_stage_battle(self) -> None:
        if self._selected_stage_id is None:
            self.status_var.set("请先选择关卡")
            return
        try:
            draft_positions = dict(self._formation_draft_positions)
            preparation = self.app.open_stage_battle_entry(self._selected_stage_id, formation_positions=draft_positions)
            result = self.app.start_stage_battle(self._selected_stage_id, formation_positions=draft_positions)
            self.refresh_resources()
            self.refresh_stage_scene()
            self.refresh_formation_panel()
            self.refresh_profile_page()
            winner_text = "我方胜利" if result.winner == "ally" else "敌方胜利"
            top_damage = sorted(result.damage_statistics.items(), key=lambda item: item[1], reverse=True)[:3]
            top_damage_text = "输出摘要：" + ("；".join(f"{name} {int(value)}" for name, value in top_damage) if top_damage else "暂无")
            self._last_battle_summary = {
                "stage_name": preparation.stage_name,
                "winner_text": winner_text,
                "stars": result.stars,
                "rounds": result.rounds,
                "timed_out": result.timed_out,
                "rewards": dict(result.rewards),
                "top_damage_text": top_damage_text,
            }
            self.show_battle_scene()
            self.root.update_idletasks()
            try:
                self._replay_timeline = build_battle_replay_timeline(preparation, result, self.app.battle_engine)
            except Exception:
                fallback_scene = build_battlefield_scene(preparation, result)
                self._replay_timeline = BattleReplayTimeline(
                    stage_id=preparation.stage_id,
                    stage_name=preparation.stage_name,
                    frames=[
                        BattleReplayFrame(
                            frame_index=0,
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
                            scene=fallback_scene,
                            feedback_events=(),
                            focus_unit_ids=(),
                        )
                    ],
                )
            if not self._replay_timeline.frames:
                fallback_scene = build_battlefield_scene(preparation, result)
                self._replay_timeline = BattleReplayTimeline(
                    stage_id=preparation.stage_id,
                    stage_name=preparation.stage_name,
                    frames=[
                        BattleReplayFrame(
                            frame_index=0,
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
                            scene=fallback_scene,
                            feedback_events=(),
                            focus_unit_ids=(),
                        )
                    ],
                )
            self._hide_settlement_overlay()
            self._show_replay_frame(0)
            self.stage_hint_var.set(f"战斗过程正在回放：{preparation.stage_name}。点击“跳过”可直接查看结算。")
            self.status_var.set(f"已进入战场回放：{self._selected_stage_id}")
            if len(self._replay_timeline.frames) > 1:
                self._start_replay_autoplay()
        except ValueError as exc:
            self.status_var.set(str(exc))

    def sweep_selected_stage(self) -> None:
        if self._selected_stage_id is None:
            self.status_var.set("请先选择关卡")
            return
        try:
            result = self.app.sweep_stage(self._selected_stage_id)
            self.refresh_resources()
            self.refresh_stage_scene()
            self.refresh_profile_page()
            self.scene_banner_var.set(f"扫荡完成：{result.stage_name}，奖励已自动入库。")
            self.status_var.set(f"扫荡完成：{result.stage_name}，获得 {result.rewards}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def claim_idle_rewards(self) -> None:
        try:
            result = self.app.claim_idle_rewards()
            self.refresh_resources()
            self.refresh_profile_page()
            self.scene_banner_var.set(f"挂机战利品已结算：{result.rewards if result.rewards else '暂无收益'}")
            self.status_var.set(f"挂机收益：{result.rewards if result.rewards else '暂无'}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def quick_idle(self) -> None:
        try:
            result = self.app.quick_idle()
            self.refresh_resources()
            self.refresh_profile_page()
            self.scene_banner_var.set(f"快速挂机已执行：剩余次数 {result.remaining_times}")
            self.status_var.set(f"快速挂机完成：{result.rewards}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def select_save_slot(self, slot: int) -> None:
        self._selected_save_slot = slot
        self.refresh_save_panel()
        self.refresh_profile_page()
        self.status_var.set(f"已选择存档槽位：{slot}")

    def quick_save(self) -> None:
        try:
            self.app.save_to_slot(self._selected_save_slot)
            self.refresh_save_panel()
            self.refresh_profile_page()
            self.scene_banner_var.set(f"存档快照已写入槽位 {self._selected_save_slot}。")
            self.status_var.set(f"已存档到槽位 {self._selected_save_slot}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def load_selected_slot(self) -> None:
        try:
            self.app.load_slot(self._selected_save_slot)
            self._replay_timeline = None
            self.refresh_all()
            self._hide_settlement_overlay()
            self.scene_banner_var.set(f"已从槽位 {self._selected_save_slot} 恢复当前进度。")
            self.status_var.set(f"已读取槽位 {self._selected_save_slot}")
        except ValueError as exc:
            self.status_var.set(str(exc))

    def _show_replay_frame(self, index: int) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.replay_var.set("当前没有战斗回放")
            self.replay_scale.configure(to=0)
            self.replay_scale.set(0)
            return
        self._replay_frame_index = max(0, min(index, len(self._replay_timeline.frames) - 1))
        frame = self._replay_timeline.frames[self._replay_frame_index]
        self.battle_canvas.render(frame.scene)
        self.show_battle_scene()
        frame_detail = frame.detail_text.splitlines()[-1]
        self.replay_var.set(f"{frame.title}｜第 {self._replay_frame_index + 1}/{len(self._replay_timeline.frames)} 帧\n{frame_detail}")
        self.scene_banner_var.set(f"{frame.title} · 第 {self._replay_frame_index + 1}/{len(self._replay_timeline.frames)} 帧 · {frame_detail}")
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self._show_settlement_overlay(frame.title, frame.detail_text)
            self.stage_hint_var.set("当前已停留在战斗结算界面，可手动拖动时间轴回看过程。")
            self.status_var.set("战斗回放已播放至结算")
        else:
            self._hide_settlement_overlay()
            self.stage_hint_var.set("当前正在展示战斗过程，可播放、逐帧查看或点击“跳过”直接看结算。")
        self.replay_scale.configure(to=len(self._replay_timeline.frames) - 1)
        if int(self.replay_scale.get()) != self._replay_frame_index:
            self._replay_scale_is_syncing = True
            try:
                self.replay_scale.set(self._replay_frame_index)
            finally:
                self._replay_scale_is_syncing = False

    def _on_replay_scale_changed(self, value: str) -> None:
        if self._replay_scale_is_syncing:
            return
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        self._show_replay_frame(int(float(value)))

    def step_replay(self, delta: int) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        self.stop_replay()
        self._show_replay_frame(self._replay_frame_index + delta)

    def toggle_replay(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.status_var.set("当前没有可播放的战斗回放")
            return
        if self._replay_after_id is not None:
            self.stop_replay()
            self.status_var.set("战斗回放已暂停")
            return
        self._start_replay_autoplay()

    def _start_replay_autoplay(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self._show_replay_frame(0)
        self.play_button.configure(text="暂停")
        self.status_var.set("战斗回放播放中")
        self._schedule_next_replay_step()

    def skip_replay_to_result(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.status_var.set("当前没有可跳过的战斗回放")
            return
        self.stop_replay()
        self._show_replay_frame(len(self._replay_timeline.frames) - 1)
        self.scene_banner_var.set("已跳过战斗过程，当前显示战斗结算。")
        self.status_var.set("已跳过回放并进入战斗结算")

    def _schedule_next_replay_step(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.stop_replay()
            return
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self.stop_replay()
            return
        self._replay_after_id = self.root.after(720, self._advance_replay)

    def _advance_replay(self) -> None:
        self._replay_after_id = None
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self.stop_replay()
            return
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self.stop_replay()
            return
        self._show_replay_frame(self._replay_frame_index + 1)
        if self._replay_timeline is None or self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self.stop_replay()
            self.status_var.set("战斗回放已自动播放完毕")
            return
        self.play_button.configure(text="暂停")
        self._schedule_next_replay_step()

    def stop_replay(self) -> None:
        if self._replay_after_id is not None:
            self.root.after_cancel(self._replay_after_id)
            self._replay_after_id = None
        self.battle_canvas.stop_animations(reset_positions=True)
        self.play_button.configure(text="播放")


def build_game_application(project_root: Path | None = None) -> GameApplication:
    resolved_root = project_root or Path(__file__).resolve().parents[3]
    app = GameApplication(GameConfig.from_project_root(resolved_root))
    app.initialize()
    return app


def _build_settlement_rating_text(stars: int, *, timed_out: bool) -> str:
    if timed_out:
        return "评级：鏖战未决"
    if stars >= 3:
        return "评级：完美通关"
    if stars == 2:
        return "评级：漂亮收官"
    if stars == 1:
        return "评级：险胜突围"
    return "评级：重整旗鼓"


def create_game_scene_window(project_root: Path | None = None, *, withdraw: bool = False) -> tuple[tk.Tk, GameSceneWindow]:
    root = tk.Tk()
    if withdraw:
        root.withdraw()
    window = GameSceneWindow(root, build_game_application(project_root))
    return root, window


def run_game_scene_app(project_root: Path | None = None) -> None:
    root, _window = create_game_scene_window(project_root)
    root.mainloop()


