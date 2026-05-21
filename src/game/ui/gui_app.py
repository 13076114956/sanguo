from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from game.core.app import GameApplication, GameConfig
from game.ui.two_d_models import BattleReplayTimeline, build_battle_replay_timeline, build_battlefield_scene, build_stage_map_scene
from game.ui.two_d_views import BattlefieldCanvas, StageMapCanvas


class GameDesktopWindow:
    """阶段三 GUI 预览：在完整管理页基础上新增 2D 地图与战场场景。"""

    def __init__(self, root: tk.Tk, app: GameApplication) -> None:
        self.root = root
        self.app = app
        self.message_log: list[str] = []
        self.status_var = tk.StringVar(value="GUI 已启动")
        self._hero_options: dict[str, str] = {}
        self._formation_hero_options: dict[str, str] = {}
        self._formation_preset_options: dict[str, str] = {}
        self._stage_options: dict[str, str] = {}
        self._chapter_options: dict[str, str] = {}
        self._save_slot_options: dict[str, int] = {}
        self._card_options: dict[str, str] = {}
        self._hero_card_by_id: dict[str, object] = {}
        self._stage_overviews_cache: list[object] = []
        self._stage_id_to_chapter_id: dict[str, str] = {}
        self._scene_selection_stage_id: str | None = None
        self._last_stage_preparation: object | None = None
        self._last_battle_result: object | None = None
        self._last_battle_stage_id: str | None = None
        self._replay_timeline: BattleReplayTimeline | None = None
        self._replay_frame_index = 0
        self._replay_after_id: str | None = None

        self.root.title("欢乐战三国 - GUI 阶段三预览")
        self.root.geometry("1440x920")
        self.root.minsize(1180, 760)

        self._build_layout()
        self.refresh_all()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="欢乐战三国 - 桌面 GUI（阶段三预览）", font=("Microsoft YaHei UI", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="全部刷新", command=self.refresh_all).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(container)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.overview_tab = ttk.Frame(notebook, padding=8)
        self.formation_tab = ttk.Frame(notebook, padding=8)
        self.hero_tab = ttk.Frame(notebook, padding=8)
        self.card_tab = ttk.Frame(notebook, padding=8)
        self.stage_tab = ttk.Frame(notebook, padding=8)
        self.scene_tab = ttk.Frame(notebook, padding=8)
        self.save_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.overview_tab, text="资源与招募")
        notebook.add(self.formation_tab, text="阵容管理")
        notebook.add(self.hero_tab, text="武将")
        notebook.add(self.card_tab, text="武将卡片")
        notebook.add(self.stage_tab, text="章节与扫荡")
        notebook.add(self.scene_tab, text="2D 场景")
        notebook.add(self.save_tab, text="存档管理")

        self._build_overview_tab()
        self._build_formation_tab()
        self._build_hero_tab()
        self._build_card_tab()
        self._build_stage_tab()
        self._build_scene_tab()
        self._build_save_tab()

        status_bar = ttk.Label(container, textvariable=self.status_var, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(8, 0))

    def _build_overview_tab(self) -> None:
        actions = ttk.Frame(self.overview_tab)
        actions.pack(fill=tk.X, pady=(0, 8))
        for text, command in [
            ("刷新资源", self.refresh_overview),
            ("领取挂机收益", self._claim_idle_rewards),
            ("快速挂机", self._quick_idle),
            ("购买体力", self._purchase_stamina),
            ("单抽", lambda: self._summon(1)),
            ("十连", lambda: self._summon(10)),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side=tk.LEFT, padx=(0, 6))

        upper = ttk.Panedwindow(self.overview_tab, orient=tk.HORIZONTAL)
        upper.pack(fill=tk.BOTH, expand=True)

        resource_frame = ttk.Labelframe(upper, text="资源概览")
        result_frame = ttk.Labelframe(upper, text="最近操作结果")
        upper.add(resource_frame, weight=1)
        upper.add(result_frame, weight=1)

        self.resource_text = ScrolledText(resource_frame, wrap=tk.WORD, height=20)
        self.resource_text.pack(fill=tk.BOTH, expand=True)
        self.overview_result_text = ScrolledText(result_frame, wrap=tk.WORD, height=20)
        self.overview_result_text.pack(fill=tk.BOTH, expand=True)

        message_frame = ttk.Labelframe(self.overview_tab, text="消息日志")
        message_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.message_text = ScrolledText(message_frame, wrap=tk.WORD, height=12)
        self.message_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.message_text, "")

    def _build_formation_tab(self) -> None:
        preset_row = ttk.Frame(self.formation_tab)
        preset_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(preset_row, text="当前预设：").pack(side=tk.LEFT)
        self.formation_preset_combo = ttk.Combobox(preset_row, state="readonly", width=38)
        self.formation_preset_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.formation_preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_selected_preset_fields())
        ttk.Button(preset_row, text="刷新阵容", command=self.refresh_formation).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(preset_row, text="切换到所选预设", command=self._switch_selected_formation_preset).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(preset_row, text="保存 ID：").pack(side=tk.LEFT, padx=(12, 0))
        self.formation_preset_id_entry = ttk.Entry(preset_row, width=16)
        self.formation_preset_id_entry.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(preset_row, text="名称：").pack(side=tk.LEFT)
        self.formation_preset_name_entry = ttk.Entry(preset_row, width=18)
        self.formation_preset_name_entry.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(preset_row, text="保存当前阵容为预设", command=self._save_current_formation_as_preset).pack(side=tk.LEFT)

        deploy_row = ttk.Frame(self.formation_tab)
        deploy_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(deploy_row, text="上阵武将：").pack(side=tk.LEFT)
        self.formation_hero_combo = ttk.Combobox(deploy_row, state="readonly", width=44)
        self.formation_hero_combo.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(deploy_row, text="目标站位：").pack(side=tk.LEFT)
        self.formation_position_combo = ttk.Combobox(deploy_row, state="readonly", width=6, values=[str(index) for index in range(1, 7)])
        self.formation_position_combo.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(deploy_row, text="上阵 / 替换", command=self._deploy_selected_hero_to_formation).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(deploy_row, text="下阵当前站位", command=self._undeploy_selected_formation_position).pack(side=tk.LEFT)

        swap_row = ttk.Frame(self.formation_tab)
        swap_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(swap_row, text="换位：").pack(side=tk.LEFT)
        self.formation_left_position_combo = ttk.Combobox(swap_row, state="readonly", width=6, values=[str(index) for index in range(1, 7)])
        self.formation_left_position_combo.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(swap_row, text="↔").pack(side=tk.LEFT)
        self.formation_right_position_combo = ttk.Combobox(swap_row, state="readonly", width=6, values=[str(index) for index in range(1, 7)])
        self.formation_right_position_combo.pack(side=tk.LEFT, padx=(6, 6))
        ttk.Button(swap_row, text="执行换位", command=self._swap_formation_positions).pack(side=tk.LEFT)

        top = ttk.Panedwindow(self.formation_tab, orient=tk.HORIZONTAL)
        top.pack(fill=tk.BOTH, expand=True)

        current_frame = ttk.Labelframe(top, text="当前活动阵容")
        preset_frame = ttk.Labelframe(top, text="预设列表")
        selectable_frame = ttk.Labelframe(top, text="可上阵武将")
        top.add(current_frame, weight=1)
        top.add(preset_frame, weight=1)
        top.add(selectable_frame, weight=1)

        self.formation_text = ScrolledText(current_frame, wrap=tk.WORD, height=22)
        self.formation_text.pack(fill=tk.BOTH, expand=True)
        self.formation_preset_text = ScrolledText(preset_frame, wrap=tk.WORD, height=22)
        self.formation_preset_text.pack(fill=tk.BOTH, expand=True)
        self.formation_hero_pool_text = ScrolledText(selectable_frame, wrap=tk.WORD, height=22)
        self.formation_hero_pool_text.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.Labelframe(self.formation_tab, text="阵容操作结果")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.formation_result_text = ScrolledText(result_frame, wrap=tk.WORD, height=10)
        self.formation_result_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.formation_result_text, "请选择武将、站位或预设后进行阵容操作。")

    def _build_hero_tab(self) -> None:
        controls = ttk.Frame(self.hero_tab)
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(controls, text="当前英雄：").pack(side=tk.LEFT)
        self.hero_combo = ttk.Combobox(controls, state="readonly", width=48)
        self.hero_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.hero_combo.bind("<<ComboboxSelected>>", lambda _event: self._show_selected_hero_detail())

        for text, command in [
            ("刷新武将", self.refresh_heroes),
            ("查看详情", self._show_selected_hero_detail),
            ("升级 +1", lambda: self._upgrade_selected_hero(use_max=False)),
            ("尽可能升级", lambda: self._upgrade_selected_hero(use_max=True)),
            ("激活奇珍", self._activate_selected_hero_treasure),
        ]:
            ttk.Button(controls, text=text, command=command).pack(side=tk.LEFT, padx=(0, 6))

        top = ttk.Panedwindow(self.hero_tab, orient=tk.HORIZONTAL)
        top.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Labelframe(top, text="武将列表")
        detail_frame = ttk.Labelframe(top, text="武将详情 / 操作结果")
        top.add(list_frame, weight=1)
        top.add(detail_frame, weight=2)

        self.hero_list_text = ScrolledText(list_frame, wrap=tk.WORD, height=28)
        self.hero_list_text.pack(fill=tk.BOTH, expand=True)
        self.hero_detail_text = ScrolledText(detail_frame, wrap=tk.WORD, height=28)
        self.hero_detail_text.pack(fill=tk.BOTH, expand=True)

    def _build_card_tab(self) -> None:
        controls = ttk.Frame(self.card_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(controls, text="刷新卡片", command=self.refresh_cards).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(controls, text="左侧卡片：").pack(side=tk.LEFT)
        self.card_left_combo = ttk.Combobox(controls, state="readonly", width=42)
        self.card_left_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.card_left_combo.bind("<<ComboboxSelected>>", lambda _event: self._show_card_selection_hint())
        ttk.Label(controls, text="右侧卡片：").pack(side=tk.LEFT)
        self.card_right_combo = ttk.Combobox(controls, state="readonly", width=42)
        self.card_right_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.card_right_combo.bind("<<ComboboxSelected>>", lambda _event: self._show_card_selection_hint())
        ttk.Button(controls, text="执行觉醒合成", command=self._fuse_selected_cards).pack(side=tk.LEFT)

        top = ttk.Panedwindow(self.card_tab, orient=tk.HORIZONTAL)
        top.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Labelframe(top, text="武将卡片列表")
        detail_frame = ttk.Labelframe(top, text="合成说明 / 结果")
        top.add(list_frame, weight=2)
        top.add(detail_frame, weight=1)

        self.card_list_text = ScrolledText(list_frame, wrap=tk.WORD, height=28)
        self.card_list_text.pack(fill=tk.BOTH, expand=True)
        self.card_detail_text = ScrolledText(detail_frame, wrap=tk.WORD, height=28)
        self.card_detail_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.card_detail_text, "请选择两张卡片进行觉醒合成。")

    def _build_stage_tab(self) -> None:
        filter_row = ttk.Frame(self.stage_tab)
        filter_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(filter_row, text="章节筛选：").pack(side=tk.LEFT)
        self.chapter_combo = ttk.Combobox(filter_row, state="readonly", width=40)
        self.chapter_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.chapter_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_stages())
        ttk.Button(filter_row, text="刷新关卡", command=self.refresh_stages).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(filter_row, text="一键扫荡当前/所选章节", command=self._sweep_selected_chapter).pack(side=tk.LEFT)

        stage_row = ttk.Frame(self.stage_tab)
        stage_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(stage_row, text="当前关卡：").pack(side=tk.LEFT)
        self.stage_combo = ttk.Combobox(stage_row, state="readonly", width=48)
        self.stage_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.stage_combo.bind("<<ComboboxSelected>>", lambda _event: self._handle_stage_selected())
        for text, command in [
            ("查看备战", self._show_stage_preparation),
            ("开始战斗", self._start_selected_stage_battle),
            ("扫荡关卡", self._sweep_selected_stage),
        ]:
            ttk.Button(stage_row, text=text, command=command).pack(side=tk.LEFT, padx=(0, 6))

        top = ttk.Panedwindow(self.stage_tab, orient=tk.HORIZONTAL)
        top.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Labelframe(top, text="章节 / 关卡列表")
        prep_frame = ttk.Labelframe(top, text="关卡备战")
        top.add(list_frame, weight=1)
        top.add(prep_frame, weight=1)

        self.stage_list_text = ScrolledText(list_frame, wrap=tk.WORD, height=18)
        self.stage_list_text.pack(fill=tk.BOTH, expand=True)
        self.stage_detail_text = ScrolledText(prep_frame, wrap=tk.WORD, height=18)
        self.stage_detail_text.pack(fill=tk.BOTH, expand=True)

        battle_frame = ttk.Labelframe(self.stage_tab, text="战斗 / 扫荡结果")
        battle_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.battle_text = ScrolledText(battle_frame, wrap=tk.WORD, height=16)
        self.battle_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.battle_text, "可在本页查看关卡备战、单关扫荡与章节一键扫荡结果。")

    def _build_scene_tab(self) -> None:
        header = ttk.Frame(self.scene_tab)
        header.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(header, text="刷新 2D 场景", command=self.refresh_scene_tab).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(header, text="开始当前关卡战斗", command=self._start_selected_stage_battle).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(header, text="同步到章节页备战", command=self._show_stage_preparation).pack(side=tk.LEFT)

        self.scene_stage_var = tk.StringVar(value="当前关卡：尚未选择")
        self.scene_hint_var = tk.StringVar(value="左侧点击地图节点，右侧查看 2D 战场编排。")
        self.replay_status_var = tk.StringVar(value="战斗回放：暂无")
        self.replay_play_button_var = tk.StringVar(value="播放回放")
        ttk.Label(header, textvariable=self.scene_stage_var, font=("Microsoft YaHei UI", 11, "bold")).pack(side=tk.RIGHT)

        ttk.Label(self.scene_tab, textvariable=self.scene_hint_var, foreground="#5c6b73").pack(fill=tk.X, pady=(0, 8))

        replay_controls = ttk.Frame(self.scene_tab)
        replay_controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(replay_controls, text="上一帧", command=lambda: self._step_replay(-1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(replay_controls, textvariable=self.replay_play_button_var, command=self._toggle_replay).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(replay_controls, text="下一帧", command=lambda: self._step_replay(1)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(replay_controls, text="播放进度：").pack(side=tk.LEFT)
        self.replay_scale = tk.Scale(
            replay_controls,
            from_=0,
            to=0,
            orient=tk.HORIZONTAL,
            length=360,
            showvalue=False,
            command=self._on_replay_scale_changed,
        )
        self.replay_scale.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(replay_controls, text="速度：").pack(side=tk.LEFT)
        self.replay_speed_combo = ttk.Combobox(replay_controls, state="readonly", width=8, values=["0.5x", "1.0x", "2.0x"])
        self.replay_speed_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.replay_speed_combo.set("1.0x")
        ttk.Label(replay_controls, textvariable=self.replay_status_var, foreground="#4b5563").pack(side=tk.LEFT)

        body = ttk.Panedwindow(self.scene_tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        map_frame = ttk.Labelframe(body, text="章节地图（2D 节点）")
        battle_frame = ttk.Labelframe(body, text="战场预览（2D 布阵）")
        body.add(map_frame, weight=1)
        body.add(battle_frame, weight=2)

        self.stage_map_canvas = StageMapCanvas(map_frame, on_stage_selected=self._handle_scene_stage_selected, width=420, height=560)
        self.stage_map_canvas.pack(fill=tk.BOTH, expand=True)
        self.battlefield_canvas = BattlefieldCanvas(battle_frame, width=900, height=560)
        self.battlefield_canvas.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.Labelframe(self.scene_tab, text="2D 场景摘要")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.scene_result_text = ScrolledText(result_frame, wrap=tk.WORD, height=10)
        self.scene_result_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.scene_result_text, "等待选择关卡后生成 2D 地图与战场预览。")

    def _build_save_tab(self) -> None:
        controls = ttk.Frame(self.save_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls, text="目标槽位：").pack(side=tk.LEFT)
        self.save_slot_combo = ttk.Combobox(controls, state="readonly", width=28)
        self.save_slot_combo.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls, text="刷新槽位", command=self.refresh_saves).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="手动存档", command=self._save_to_selected_slot).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="切换读档", command=self._load_selected_slot).pack(side=tk.LEFT)

        top = ttk.Panedwindow(self.save_tab, orient=tk.HORIZONTAL)
        top.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Labelframe(top, text="槽位概览")
        result_frame = ttk.Labelframe(top, text="存档操作结果")
        top.add(list_frame, weight=2)
        top.add(result_frame, weight=1)

        self.save_list_text = ScrolledText(list_frame, wrap=tk.WORD, height=28)
        self.save_list_text.pack(fill=tk.BOTH, expand=True)
        self.save_result_text = ScrolledText(result_frame, wrap=tk.WORD, height=28)
        self.save_result_text.pack(fill=tk.BOTH, expand=True)
        self._set_text(self.save_result_text, "请选择槽位后执行手动存档或切换读档。")

    def refresh_all(self) -> None:
        self._stop_replay()
        previous_message_count = len(self.message_log)
        self.refresh_overview()
        self.refresh_formation()
        self.refresh_heroes()
        self.refresh_cards()
        self.refresh_stages()
        self.refresh_saves()
        self._consume_messages()
        if len(self.message_log) == previous_message_count:
            self._set_status("已刷新全部页面")

    def refresh_overview(self) -> None:
        overview = self.app.get_resource_overview()
        rendered = self.app.console_view.render_resource_overview(overview)
        self._set_text(self.resource_text, rendered)

    def refresh_formation(self) -> None:
        active_overview = self.app.get_active_formation_overview()
        preset_overviews = self.app.list_formation_preset_overviews()
        hero_overviews = self.app.list_visible_hero_skill_overviews()
        current_preset_id = self._selected_preset_id()
        current_hero_ref = self._selected_formation_hero_ref()

        self._set_text(self.formation_text, self.app.console_view.render_formation_overview(active_overview))
        self._set_text(self.formation_preset_text, self.app.console_view.render_formation_preset_list(preset_overviews))
        self._set_text(self.formation_hero_pool_text, self.app.console_view.render_hero_selection_menu(hero_overviews))

        self._formation_preset_options = {
            f"{'[当前] ' if item.is_active else ''}{item.formation_name} ({item.formation_id}) | {item.hero_count}人 / {item.power}战力": item.formation_id
            for item in preset_overviews
        }
        self._sync_combobox_mapping(
            self.formation_preset_combo,
            self._formation_preset_options,
            preferred_value=current_preset_id or active_overview.formation_id,
        )

        self._formation_hero_options = {
            f"{item.hero_name} [{item.hero_quality}/{item.awakening_level}] Lv.{item.hero_level} ({item.template_id})": item.template_id
            for item in hero_overviews
        }
        self._sync_combobox_mapping(self.formation_hero_combo, self._formation_hero_options, preferred_value=current_hero_ref)

        if not self.formation_position_combo.get():
            self.formation_position_combo.set("1")
        if not self.formation_left_position_combo.get():
            self.formation_left_position_combo.set("1")
        if not self.formation_right_position_combo.get():
            self.formation_right_position_combo.set("2")
        if not self.formation_preset_id_entry.get().strip():
            self._set_entry_text(self.formation_preset_id_entry, self._suggest_next_formation_id())

    def refresh_heroes(self) -> None:
        overviews = self.app.list_visible_hero_skill_overviews()
        rendered = self.app.console_view.render_hero_skill_overview_list(overviews)
        self._set_text(self.hero_list_text, rendered)
        current_ref = self._selected_hero_ref()
        self._hero_options = {
            f"{item.hero_name} [{item.hero_quality}/{item.awakening_level}] ({item.template_id})": item.template_id
            for item in overviews
        }
        self._sync_combobox_mapping(self.hero_combo, self._hero_options, preferred_value=current_ref)
        if not self._hero_options:
            self._set_text(self.hero_detail_text, "当前没有可展示的武将。")
            return
        self._show_selected_hero_detail(silent=True)

    def refresh_cards(self) -> None:
        cards = self.app.list_hero_card_overviews()
        current_left_id = self._selected_card_id(self.card_left_combo)
        current_right_id = self._selected_card_id(self.card_right_combo)

        self._hero_card_by_id = {item.hero_id: item for item in cards}
        self._card_options = {
            self._format_card_option(item): item.hero_id
            for item in cards
        }
        self._set_text(self.card_list_text, self.app.console_view.render_hero_card_list(cards))
        self._sync_combobox_mapping(self.card_left_combo, self._card_options, preferred_value=current_left_id)
        self._sync_combobox_mapping(self.card_right_combo, self._card_options, preferred_value=current_right_id, fallback_index=1)
        if not self._card_options:
            self._set_text(self.card_detail_text, "当前没有可展示的武将卡。")
            return
        self._show_card_selection_hint()

    def refresh_stages(self) -> None:
        overviews = self.app.list_stage_overviews()
        self._stage_overviews_cache = overviews
        self._stage_id_to_chapter_id = {item.stage_id: item.chapter_id for item in overviews}
        current_chapter_id = self._selected_chapter_id()
        current_stage_id = self._scene_selection_stage_id or self._selected_stage_id()

        chapter_meta: dict[str, dict[str, object]] = {}
        for item in overviews:
            entry = chapter_meta.setdefault(
                item.chapter_id,
                {
                    "chapter_name": item.chapter_name,
                    "chapter_unlocked": item.chapter_unlocked,
                    "chapter_completed": item.chapter_completed,
                    "chapter_unlock_condition": item.chapter_unlock_condition,
                    "stage_count": 0,
                    "completed_count": 0,
                },
            )
            entry["stage_count"] = int(entry["stage_count"]) + 1
            if item.completed:
                entry["completed_count"] = int(entry["completed_count"]) + 1

        self._chapter_options = {"全部章节（列表） / 当前推进章节（扫荡）": ""}
        for chapter_id, meta in chapter_meta.items():
            chapter_status = "已解锁" if bool(meta["chapter_unlocked"]) else "未解锁"
            chapter_completed = " / 已通关" if bool(meta["chapter_completed"]) else ""
            progress = f" / 已通关关卡 {int(meta['completed_count'])}/{int(meta['stage_count'])}"
            lock_reason = "" if bool(meta["chapter_unlocked"]) else f" / {meta['chapter_unlock_condition']}"
            display = f"{chapter_id} {meta['chapter_name']} [{chapter_status}{chapter_completed}{progress}{lock_reason}]"
            self._chapter_options[display] = chapter_id
        self._sync_combobox_mapping(self.chapter_combo, self._chapter_options, preferred_value=current_chapter_id or "")

        selected_chapter_id = self._selected_chapter_id()
        filtered_overviews = [
            item for item in overviews
            if selected_chapter_id is None or item.chapter_id == selected_chapter_id
        ]
        self._stage_options = {
            f"{item.stage_id} {item.stage_name}": item.stage_id
            for item in filtered_overviews
        }
        self._sync_combobox_mapping(self.stage_combo, self._stage_options, preferred_value=current_stage_id)

        chapter_summary = self._render_chapter_summary(overviews, filtered_overviews, selected_chapter_id)
        if filtered_overviews:
            rendered = chapter_summary + "\n\n" + self.app.console_view.render_stage_list(filtered_overviews)
        else:
            rendered = chapter_summary + "\n\n=== 主线关卡列表 ===\n当前筛选下暂无可展示关卡。"
        self._set_text(self.stage_list_text, rendered)

        if not self._stage_options:
            self._set_text(self.stage_detail_text, "当前筛选下没有可查看的关卡。")
            self.refresh_scene_tab(silent=True)
            return
        self._show_stage_preparation(silent=True)
        self.refresh_scene_tab(silent=True)

    def refresh_saves(self) -> None:
        overviews = self.app.list_save_slot_overviews()
        self._set_text(self.save_list_text, self.app.console_view.render_save_slot_list(overviews))
        current_slot = self._selected_save_slot() or self.app.state.current_slot
        self._save_slot_options = {
            self._format_save_slot_option(item): item.slot
            for item in overviews
        }
        self._sync_combobox_mapping(self.save_slot_combo, self._save_slot_options, preferred_value=current_slot)

    def _show_selected_hero_detail(self, *, silent: bool = False) -> None:
        hero_ref = self._selected_hero_ref()
        if hero_ref is None:
            self._set_text(self.hero_detail_text, "请先选择一个武将。")
            return
        overview = self.app.get_hero_skill_overview(hero_ref)
        self._set_text(self.hero_detail_text, self.app.console_view.render_hero_skill_overview(overview))
        if not silent:
            self._set_status(f"已加载武将详情：{overview.hero_name}")

    def _deploy_selected_hero_to_formation(self) -> None:
        hero_ref = self._selected_formation_hero_ref()
        position = self._selected_position(self.formation_position_combo)
        if hero_ref is None or position is None:
            self._show_error("请先选择要上阵的武将和目标站位")
            return
        try:
            self.app.deploy_hero_to_active_formation(position, hero_ref)
            self.refresh_formation()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.formation_result_text, self.app.console_view.render_formation_overview(self.app.get_active_formation_overview()))
            self._set_status(f"已将武将上阵到 {position} 号位")
        except ValueError as exc:
            self._show_error(str(exc))

    def _undeploy_selected_formation_position(self) -> None:
        position = self._selected_position(self.formation_position_combo)
        if position is None:
            self._show_error("请先选择要下阵的站位")
            return
        try:
            self.app.undeploy_hero_from_active_formation(position)
            self.refresh_formation()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.formation_result_text, self.app.console_view.render_formation_overview(self.app.get_active_formation_overview()))
            self._set_status(f"已下阵 {position} 号位武将")
        except ValueError as exc:
            self._show_error(str(exc))

    def _swap_formation_positions(self) -> None:
        left = self._selected_position(self.formation_left_position_combo)
        right = self._selected_position(self.formation_right_position_combo)
        if left is None or right is None:
            self._show_error("请先选择两个站位")
            return
        try:
            self.app.swap_active_formation_positions(left, right)
            self.refresh_formation()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.formation_result_text, self.app.console_view.render_formation_overview(self.app.get_active_formation_overview()))
            self._set_status(f"已交换 {left} 与 {right} 号位")
        except ValueError as exc:
            self._show_error(str(exc))

    def _switch_selected_formation_preset(self) -> None:
        formation_id = self._selected_preset_id()
        if formation_id is None:
            self._show_error("请先选择一个阵容预设")
            return
        try:
            formation = self.app.switch_formation_preset(formation_id)
            self.refresh_formation()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.formation_result_text, self.app.console_view.render_formation_overview(self.app.get_active_formation_overview()))
            self._set_status(f"已切换阵容预设：{formation.name}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _save_current_formation_as_preset(self) -> None:
        current = self.app.get_active_formation()
        if current is None:
            self._show_error("当前没有可保存的活动阵容")
            return
        formation_id = self.formation_preset_id_entry.get().strip() or self._suggest_next_formation_id()
        name = self.formation_preset_name_entry.get().strip() or None
        try:
            formation = self.app.save_formation_preset(formation_id, dict(current.positions), name=name)
            self.refresh_formation()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.formation_result_text, self.app.console_view.render_formation_preset_list(self.app.list_formation_preset_overviews()))
            self._set_status(f"已保存阵容预设：{formation.name}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _sync_selected_preset_fields(self) -> None:
        formation_id = self._selected_preset_id()
        if formation_id is None:
            return
        preset = next(
            (item for item in self.app.list_formation_preset_overviews() if item.formation_id == formation_id),
            None,
        )
        if preset is None:
            return
        self._set_entry_text(self.formation_preset_id_entry, preset.formation_id)
        self._set_entry_text(self.formation_preset_name_entry, preset.formation_name)
        self._set_status(f"已选择阵容预设：{preset.formation_name}")

    def _show_card_selection_hint(self) -> None:
        left_id = self._selected_card_id(self.card_left_combo)
        right_id = self._selected_card_id(self.card_right_combo)
        if left_id is None or right_id is None:
            self._set_text(self.card_detail_text, "请选择左右两张卡片后查看合成提示。")
            return
        left = self._hero_card_by_id.get(left_id)
        right = self._hero_card_by_id.get(right_id)
        if left is None or right is None:
            self._set_text(self.card_detail_text, "当前卡片选择无效，请重新选择。")
            return
        lines = [
            "=== 觉醒合成检查 ===",
            f"左侧: {left.hero_name} [{left.awakening_level}] / 卡片ID: {left.hero_id}",
            f"右侧: {right.hero_name} [{right.awakening_level}] / 卡片ID: {right.hero_id}",
        ]
        if left_id == right_id:
            lines.append("说明: 同一张卡片不能同时作为左右两侧材料。")
        elif left.template_id != right.template_id:
            lines.append("说明: 仅支持同名武将卡进行觉醒合成。")
        elif left.awakening_level != right.awakening_level:
            lines.append("说明: 仅支持同阶觉醒卡进行两两合成。")
        else:
            lines.append("说明: 当前组合满足觉醒合成条件，可直接执行。")
        self._set_text(self.card_detail_text, "\n".join(lines))

    def _fuse_selected_cards(self) -> None:
        left_id = self._selected_card_id(self.card_left_combo)
        right_id = self._selected_card_id(self.card_right_combo)
        if left_id is None or right_id is None:
            self._show_error("请先选择左右两张卡片")
            return
        try:
            fused = self.app.fuse_hero_awakening(left_id, right_id)
            rendered = self.app.console_view.render_awakening_fusion_result(fused)
            rendered += "\n\n" + self.app.console_view.render_hero_card_list(self.app.list_hero_card_overviews())
            self.refresh_formation()
            self.refresh_heroes()
            self.refresh_cards()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.card_detail_text, rendered)
            self._set_status(f"已完成觉醒合成：{fused.name}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _upgrade_selected_hero(self, *, use_max: bool) -> None:
        hero_ref = self._selected_hero_ref()
        if hero_ref is None:
            self._show_error("请先选择一个武将")
            return
        try:
            result = self.app.upgrade_hero_level(hero_ref, use_max=use_max, levels=1)
            detail = self.app.console_view.render_hero_level_up_result(result)
            detail += "\n\n" + self.app.console_view.render_hero_skill_overview(self.app.get_hero_skill_overview(result.hero_id))
            self.refresh_overview()
            self.refresh_heroes()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.hero_detail_text, detail)
            self._set_status(f"已升级武将：{result.hero_name}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _activate_selected_hero_treasure(self) -> None:
        hero_ref = self._selected_hero_ref()
        if hero_ref is None:
            self._show_error("请先选择一个武将")
            return
        try:
            hero = self.app.activate_rare_treasure(hero_ref)
            self.refresh_overview()
            self.refresh_heroes()
            self.refresh_cards()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.hero_detail_text, self.app.console_view.render_hero_skill_overview(self.app.get_hero_skill_overview(hero.id)))
            self._set_status(f"已激活奇珍：{hero.name}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _show_stage_preparation(self, silent: bool = False) -> None:
        stage_id = self._selected_stage_id()
        if stage_id is None:
            self._set_text(self.stage_detail_text, "请先选择一个关卡。")
            return
        try:
            preparation = self.app.open_stage_battle_entry(stage_id)
            self._scene_selection_stage_id = stage_id
            self._last_stage_preparation = preparation
            rendered = self.app.console_view.render_stage_battle_preparation(preparation)
            self._set_text(self.stage_detail_text, rendered)
            self.refresh_scene_tab(silent=True)
            if not silent:
                self._set_status(f"已加载关卡备战：{stage_id}")
        except ValueError as exc:
            self._set_text(self.stage_detail_text, str(exc))
            self.refresh_scene_tab(silent=True)
            if not silent:
                self._show_error(str(exc))

    def _start_selected_stage_battle(self) -> None:
        stage_id = self._selected_stage_id()
        if stage_id is None:
            self._show_error("请先选择一个关卡")
            return
        try:
            result = self.app.start_stage_battle(stage_id)
            self._scene_selection_stage_id = stage_id
            self._last_battle_result = result
            self._last_battle_stage_id = stage_id
            rendered = self.app.battle_view.render_summary(result) + "\n\n" + self.app.battle_view.render_logs(result, limit=30)
            self.refresh_overview()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.battle_text, rendered)
            self.refresh_scene_tab(silent=True)
            self._set_status(f"已完成关卡挑战：{stage_id}")
        except ValueError as exc:
            self._show_error(str(exc))

    def refresh_scene_tab(self, *, silent: bool = False) -> None:
        overviews = self._stage_overviews_cache or self.app.list_stage_overviews()
        selected_stage_id = self._scene_selection_stage_id or self._selected_stage_id()
        self.stage_map_canvas.render(build_stage_map_scene(overviews, selected_stage_id=selected_stage_id))

        if selected_stage_id is None:
            self._set_replay_timeline(None)
            self.scene_stage_var.set("当前关卡：尚未选择")
            self.scene_hint_var.set("左侧点击地图节点，右侧查看 2D 战场编排。")
            self.battlefield_canvas.render(None)
            self._set_text(self.scene_result_text, "请先在“章节与扫荡”页或左侧 2D 地图中选择一个关卡。")
            return

        self.scene_stage_var.set(f"当前关卡：{selected_stage_id}")
        try:
            preparation = self.app.open_stage_battle_entry(selected_stage_id)
            self._last_stage_preparation = preparation
            result = self._last_battle_result if self._last_battle_stage_id == selected_stage_id else None
            if result is not None:
                timeline = build_battle_replay_timeline(preparation, result, self.app.battle_engine)
                preferred_index = min(self._replay_frame_index, len(timeline.frames) - 1) if self._replay_timeline and self._replay_timeline.stage_id == selected_stage_id else len(timeline.frames) - 1
                self._set_replay_timeline(timeline, preferred_index=preferred_index)
                self.scene_hint_var.set("当前关卡已生成 2D 战斗回放，可使用播放控件按帧查看战斗过程。")
            else:
                self._set_replay_timeline(None)
                scene = build_battlefield_scene(preparation, None)
                self.battlefield_canvas.render(scene)
                self.scene_hint_var.set("已生成 2D 地图与战场布阵；点击“开始当前关卡战斗”可直接验证结果。")
                self._set_text(self.scene_result_text, "\n".join(scene.summary_lines))
            if not silent:
                self._set_status(f"已刷新 2D 场景：{selected_stage_id}")
        except ValueError as exc:
            self._set_replay_timeline(None)
            self.scene_hint_var.set("当前关卡尚不可进入战场预览，可先查看解锁条件。")
            self.battlefield_canvas.render(None)
            self._set_text(self.scene_result_text, f"=== 2D 场景加载失败 ===\n关卡: {selected_stage_id}\n原因: {exc}")
            if not silent:
                self._set_status(str(exc))

    def _handle_stage_selected(self) -> None:
        self._stop_replay()
        stage_id = self._selected_stage_id()
        self._scene_selection_stage_id = stage_id
        self._show_stage_preparation(silent=True)
        self.refresh_scene_tab(silent=True)

    def _handle_scene_stage_selected(self, stage_id: str) -> None:
        self._stop_replay()
        self._scene_selection_stage_id = stage_id
        chapter_id = self._stage_id_to_chapter_id.get(stage_id)
        if chapter_id is not None:
            self._select_combobox_value(self.chapter_combo, self._chapter_options, chapter_id)
            self.refresh_stages()
        self._select_combobox_value(self.stage_combo, self._stage_options, stage_id)
        self._show_stage_preparation(silent=True)
        self.refresh_scene_tab(silent=True)
        self._set_status(f"已从 2D 地图选择关卡：{stage_id}")

    def _set_replay_timeline(self, timeline: BattleReplayTimeline | None, *, preferred_index: int = 0) -> None:
        self._stop_replay()
        self._replay_timeline = timeline
        if timeline is None or not timeline.frames:
            self._replay_frame_index = 0
            self.replay_scale.configure(to=0)
            self.replay_scale.set(0)
            self.replay_status_var.set("战斗回放：暂无")
            self.replay_play_button_var.set("播放回放")
            return

        target_index = max(0, min(preferred_index, len(timeline.frames) - 1))
        self.replay_scale.configure(to=len(timeline.frames) - 1)
        self._show_replay_frame(target_index)

    def _show_replay_frame(self, index: int) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        self._replay_frame_index = max(0, min(index, len(self._replay_timeline.frames) - 1))
        frame = self._replay_timeline.frames[self._replay_frame_index]
        self.battlefield_canvas.render(frame.scene)
        self._set_text(self.scene_result_text, frame.detail_text)
        self.replay_status_var.set(
            f"战斗回放：帧 {self._replay_frame_index + 1}/{len(self._replay_timeline.frames)} · {frame.title}"
        )
        if int(self.replay_scale.get()) != self._replay_frame_index:
            self.replay_scale.set(self._replay_frame_index)

    def _on_replay_scale_changed(self, value: str) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        self._show_replay_frame(int(float(value)))

    def _step_replay(self, delta: int) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        self._stop_replay()
        self._show_replay_frame(self._replay_frame_index + delta)

    def _toggle_replay(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            return
        if self._replay_after_id is not None:
            self._stop_replay()
            return
        self.replay_play_button_var.set("暂停回放")
        self._schedule_replay_step()

    def _schedule_replay_step(self) -> None:
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self._stop_replay()
            return
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self._stop_replay()
            return
        delay = self._replay_delay_ms()
        self._replay_after_id = self.root.after(delay, self._advance_replay)

    def _advance_replay(self) -> None:
        self._replay_after_id = None
        if self._replay_timeline is None or not self._replay_timeline.frames:
            self._stop_replay()
            return
        if self._replay_frame_index >= len(self._replay_timeline.frames) - 1:
            self._stop_replay()
            return
        self._show_replay_frame(self._replay_frame_index + 1)
        self._schedule_replay_step()

    def _stop_replay(self) -> None:
        if self._replay_after_id is not None:
            self.root.after_cancel(self._replay_after_id)
            self._replay_after_id = None
        self.battlefield_canvas.stop_animations(reset_positions=True)
        self.replay_play_button_var.set("播放回放")

    def _replay_delay_ms(self) -> int:
        speed_text = self.replay_speed_combo.get().strip() or "1.0x"
        speed_map = {"0.5x": 1400, "1.0x": 800, "2.0x": 400}
        return speed_map.get(speed_text, 800)

    def _sweep_selected_stage(self) -> None:
        stage_id = self._selected_stage_id()
        if stage_id is None:
            self._show_error("请先选择一个关卡")
            return
        try:
            result = self.app.sweep_stage(stage_id)
            self.refresh_overview()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.battle_text, self.app.console_view.render_stage_sweep_result(result))
            self._set_status(f"已扫荡关卡：{stage_id}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _sweep_selected_chapter(self) -> None:
        chapter_id = self._selected_chapter_id()
        try:
            result = self.app.sweep_chapter(chapter_id)
            self.refresh_overview()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.battle_text, self.app.console_view.render_chapter_sweep_result(result))
            self._set_status(f"已完成章节扫荡：{result.chapter_id}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _save_to_selected_slot(self) -> None:
        slot = self._selected_save_slot()
        if slot is None:
            self._show_error("请先选择一个存档槽位")
            return
        try:
            path = self.app.save_to_slot(slot)
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.save_result_text, f"=== 手动存档结果 ===\n槽位: {slot}\n路径: {path}")
            self._set_status(f"已手动存档到槽位 {slot}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _load_selected_slot(self) -> None:
        slot = self._selected_save_slot()
        if slot is None:
            self._show_error("请先选择一个存档槽位")
            return
        try:
            player = self.app.load_slot(slot)
            self.refresh_all()
            self._set_text(
                self.save_result_text,
                "\n".join(
                    [
                        "=== 切换读档结果 ===",
                        f"当前槽位: {slot}",
                        f"玩家: {player.profile.name}",
                        f"等级: {player.profile.level}",
                        f"战力: {player.profile.power}",
                    ]
                ),
            )
            self._set_status(f"已切换读档：槽位 {slot}")
        except ValueError as exc:
            self._show_error(str(exc))

    def _claim_idle_rewards(self) -> None:
        try:
            result = self.app.claim_idle_rewards()
            self.refresh_overview()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.overview_result_text, self.app.console_view.render_idle_claim_result(result))
            self._set_status("已处理挂机收益领取")
        except ValueError as exc:
            self._show_error(str(exc))

    def _quick_idle(self) -> None:
        try:
            result = self.app.quick_idle()
            self.refresh_overview()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.overview_result_text, self.app.console_view.render_quick_idle_result(result))
            self._set_status("已完成快速挂机")
        except ValueError as exc:
            self._show_error(str(exc))

    def _purchase_stamina(self) -> None:
        try:
            result = self.app.purchase_stamina()
            self.refresh_overview()
            self.refresh_stages()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.overview_result_text, self.app.console_view.render_stamina_purchase_result(result))
            self._set_status("已购买体力")
        except ValueError as exc:
            self._show_error(str(exc))

    def _summon(self, count: int) -> None:
        try:
            result = self.app.summon_heroes(count=count)
            self.refresh_overview()
            self.refresh_formation()
            self.refresh_heroes()
            self.refresh_cards()
            self.refresh_saves()
            self._consume_messages()
            self._set_text(self.overview_result_text, self.app.console_view.render_summon_result(result))
            self._set_status(f"已完成 {count} 次元宝招募")
        except ValueError as exc:
            self._show_error(str(exc))

    def _consume_messages(self) -> None:
        messages = self.app.ui_manager.flush_messages()
        if not messages:
            return
        self.message_log.extend(messages)
        self._set_text(self.message_text, "\n".join(self.message_log[-200:]))
        self._set_status(messages[-1])

    def _render_chapter_summary(self, all_overviews: list[object], filtered_overviews: list[object], chapter_id: str | None) -> str:
        total_chapters = len({item.chapter_id for item in all_overviews})
        if chapter_id is None:
            return (
                "=== 当前章节筛选 ===\n"
                f"范围: 全部章节（列表展示 {total_chapters} 章 / {len(all_overviews)} 关）\n"
                "说明: 若执行“一键扫荡当前/所选章节”，当筛选为“全部章节”时将按当前推进章节进行扫荡。"
            )
        target = next((item for item in filtered_overviews if item.chapter_id == chapter_id), None)
        if target is None:
            return f"=== 当前章节筛选 ===\n范围: {chapter_id}\n说明: 当前筛选下暂无关卡。"
        completed_count = len([item for item in filtered_overviews if item.completed])
        return (
            "=== 当前章节筛选 ===\n"
            f"范围: {target.chapter_id} {target.chapter_name}\n"
            f"章节状态: {'已解锁' if target.chapter_unlocked else '未解锁'}{' / 已通关' if target.chapter_completed else ''}\n"
            f"关卡进度: {completed_count}/{len(filtered_overviews)}\n"
            f"推荐提示: 当前战力 {target.current_power}，可对照各关卡推荐战力决定是否推进或扫荡。"
        )

    def _suggest_next_formation_id(self) -> str:
        existing_ids = {item.formation_id for item in self.app.list_formation_preset_overviews()}
        for index in range(1, self.app.formation_service.MAX_PRESETS + 2):
            candidate = f"formation_{index}"
            if candidate not in existing_ids:
                return candidate
        return f"formation_{len(existing_ids) + 1}"

    def _selected_hero_ref(self) -> str | None:
        return self._hero_options.get(self.hero_combo.get())

    def _selected_formation_hero_ref(self) -> str | None:
        return self._formation_hero_options.get(self.formation_hero_combo.get())

    def _selected_preset_id(self) -> str | None:
        return self._formation_preset_options.get(self.formation_preset_combo.get())

    def _selected_stage_id(self) -> str | None:
        return self._stage_options.get(self.stage_combo.get())

    def _selected_chapter_id(self) -> str | None:
        chapter_id = self._chapter_options.get(self.chapter_combo.get())
        return chapter_id or None

    def _selected_save_slot(self) -> int | None:
        return self._save_slot_options.get(self.save_slot_combo.get())

    def _selected_card_id(self, combo: ttk.Combobox) -> str | None:
        return self._card_options.get(combo.get())

    @staticmethod
    def _selected_position(combo: ttk.Combobox) -> int | None:
        raw = combo.get().strip()
        if not raw.isdigit():
            return None
        position = int(raw)
        return position if 1 <= position <= 6 else None

    def _show_error(self, message: str) -> None:
        messagebox.showerror("操作失败", message)
        self.message_log.append(f"操作失败：{message}")
        self._set_text(self.message_text, "\n".join(self.message_log[-200:]))
        self._set_status(message)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    @staticmethod
    def _set_text(widget: ScrolledText, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.DISABLED)

    @staticmethod
    def _set_entry_text(entry: ttk.Entry, value: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, value)

    @staticmethod
    def _format_card_option(card: object) -> str:
        visible_tag = " / 当前最高卡" if getattr(card, "is_visible", False) else ""
        treasure_tag = " / 奇珍已激活" if getattr(card, "has_rare_treasure", False) else ""
        return (
            f"{card.hero_name} [{card.hero_quality}/{card.awakening_level}]"
            f" / 卡片ID: {card.hero_id} / 模板ID: {card.template_id}{visible_tag}{treasure_tag}"
        )

    @staticmethod
    def _format_save_slot_option(overview: object) -> str:
        status = "当前槽位" if overview.is_current else ("已存在" if overview.exists else "空槽位")
        return f"槽位 {overview.slot} [{status}]"

    @staticmethod
    def _select_combobox_value(combo: ttk.Combobox, mapping: dict[str, object], target_value: object | None) -> bool:
        if target_value is None:
            return False
        for label, value in mapping.items():
            if value == target_value:
                combo.set(label)
                return True
        return False

    @staticmethod
    def _sync_combobox_mapping(
        combo: ttk.Combobox,
        mapping: dict[str, object],
        *,
        preferred_value: object | None = None,
        fallback_index: int = 0,
    ) -> None:
        values = list(mapping.keys())
        combo["values"] = values
        if not values:
            combo.set("")
            return
        target_index = min(fallback_index, len(values) - 1)
        if preferred_value is not None:
            for index, value in enumerate(mapping.values()):
                if value == preferred_value:
                    target_index = index
                    break
        combo.current(target_index)


def build_game_application(project_root: Path | None = None) -> GameApplication:
    resolved_root = project_root or Path(__file__).resolve().parents[3]
    app = GameApplication(GameConfig.from_project_root(resolved_root))
    app.initialize()
    return app


def create_desktop_window(project_root: Path | None = None, *, withdraw: bool = False) -> tuple[tk.Tk, GameDesktopWindow]:
    root = tk.Tk()
    if withdraw:
        root.withdraw()
    window = GameDesktopWindow(root, build_game_application(project_root))
    return root, window


def run_desktop_app(project_root: Path | None = None) -> None:
    root, _window = create_desktop_window(project_root)
    root.mainloop()

