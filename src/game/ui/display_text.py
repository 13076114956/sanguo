from __future__ import annotations

from typing import Any

DISPLAY_NAME_MAP: dict[str, str] = {
    "ally": "我方",
    "enemies": "敌方",
    "enemy": "敌方",
    "self": "自身",
    "hp": "生命",
    "max_hp": "最大生命",
    "attack": "攻击",
    "defense": "防御",
    "speed": "速度",
    "crit_rate": "暴击",
    "crit_damage": "暴伤",
    "armor_break": "破甲",
    "effect_hit": "效果命中",
    "effect_resist": "效果抵抗",
    "lightning": "雷电",
    # 仅兼容旧槽位键名展示；新数据统一写作 passive_3。
    "normal_attack": "被动三",
    "passive_1": "被动一",
    "passive_2": "被动二",
    "passive_3": "被动三",
    "ultimate": "必杀",
    "apply_status": "施加状态",
    "apply_status_to_attacker_on_receive_attack": "受击反施状态",
    "bonus_damage_if_target_has_status": "状态追伤",
    "percent_hp_damage": "百分比生命伤害",
    "heal": "治疗",
    "shield": "护盾",
    "shield_regen": "护盾回春",
    "cleanse": "净化",
    "cleanse_random_allies": "随机净化友军",
    "dispel": "驱散",
    "energy_gain": "回怒",
    "energy": "怒气",
    "attack_bonus": "攻击加成",
    "defense_bonus": "防御加成",
    "speed_bonus": "速度加成",
    "damage_reduction": "伤害减免",
    "conditional_damage_reduction": "条件减伤",
    "crit_rate_bonus": "暴击加成",
    "crit_damage_bonus": "暴伤加成",
    "gain_stack": "获得层数",
    "grant_stack": "叠层",
    "gain_stack_on_receive_attack": "受击叠层",
    "transform_stack_to_status_on_threshold": "叠层转化",
    "follow_up_attack_on_receive_attack_stack_threshold": "达层追击",
    "gain_energy_and_heal_on_enemy_death": "敌亡回怒回血",
    "gain_attack_bonus_on_kill": "击杀叠攻",
    "gain_extra_turn_on_kill": "击杀再行动",
    "crit_rate_bonus_on_kill": "击杀加暴击",
    "damage_multiplier_by_target_hp": "按血量增伤",
    "bonus_damage_per_stack": "按层增伤",
    "survive_once": "绝境续命",
    "grant_team_shield": "全队护盾",
    "protect_highest_attack_ally": "护卫主将",
    "damage_reduction_from_stat": "按属性转减伤",
    "shield_by_stats": "属性护盾",
    "grant_team_frontline_damage_bonus": "全队前排增伤",
    "heal_by_caster_max_hp": "按施法者生命治疗",
    "follow_up_attack": "追击",
    "same_row_command_buff": "同排统御强化",
    "backline_burst_if_first_target_backline": "后排爆发",
    "gain_energy_on_skill_tag": "按技能标签回怒",
    "apply_status_on_skill_targets": "对技能目标施加状态",
    "apply_random_status_to_side": "随机施加状态",
    "follow_up_on_ally_actions": "友军行动追击",
    "chance_follow_up_on_ally_action": "概率援护追击",
    "gain_stack_when_column_front_enemy_damaged": "前列受伤叠层",
    "guo_jia_shadow_reaction": "棋影反应",
    "counterattack_on_receive_attack": "受击反击",
    "retreat_on_low_hp_once": "低血撤退",
    "rescue_on_hp_threshold_or_death_once": "危急援护",
    "revive_ally_next_round": "下回合复活友军",
    "heal_side": "群体治疗",
    "apply_status_to_side": "群体施加状态",
    "clear_status_from_side": "群体清除状态",
    "max_hp_bonus": "生命上限提升",
    "skill_damage_bonus": "技能伤害加成",
    "heal_over_time": "持续治疗",
    "control_immunity": "免疫控制",
    "heal_on_receive_attack": "受击治疗",
    "delayed_heal": "延迟治疗",
    "anger_mark": "怒意标记",
    "wood_mark": "木之印记",
    "pending_revive": "待复活",
    "revive_cooldown": "复活冷却",
    "weiyan_battle_soul": "战魂",
    "revive_ally_next_round_used": "复活次数",
    "burn": "灼烧",
    "poison": "中毒",
    "bleed": "流血",
    "stun": "眩晕",
    "silence": "沉默",
    "freeze": "冰冻",
    "taunt": "嘲讽",
    "invincible": "无敌",
    "untargetable": "不可选中",
    "damage_share": "伤害分担",
    "frontline_damage_bonus": "前排增伤",
    "incoming_damage_bonus": "畏服",
    "lightning_mark": "雷电印记",
    "extra_turn": "再行动",
    "kill_attack_bonus": "击杀攻势",
    "guan_yu_wu_sheng_mark": "武圣印记",
    "guan_yu_wuhun_guard": "武魂护体",
    "guan_yu_war_intent": "战意",
    "guan_yu_divine_form": "神威形态",
    "guo_jia_chess_shadow": "棋影",
    "guo_jia_shadow_crit_bonus": "棋影暴伤",
    "guo_jia_ultimate_splash": "波及伤害",
    "guo_jia_survive_once_used": "续命已触发",
    "cao_cao_alliance": "魏武之盟",
    "cao_cao_fatal_immunity_cooldown": "魏武续命冷却",
    "sun_ce_battle_fury": "激昂",
    "sun_ce_spear_bonus": "长枪增势",
    "sun_quan_heroism": "豪气",
    "wind_spirit": "风灵",
    "retreat_on_low_hp_once_used": "撤退已触发",
    "rescue_on_hp_threshold_or_death_once_used": "援护已触发",
    "buff": "增益",
    "debuff": "减益",
    "control": "控制",
    "damage_over_time": "持续伤害",
    "attribute": "属性",
    "protect": "护持",
    "special": "特殊",
}

PARAM_NAME_MAP: dict[str, str] = {
    "status_effect_type": "状态类型",
    "status_duration": "持续回合",
    "status_value": "状态数值",
    "status_params": "状态参数",
    "stack_name": "层数名称",
    "max_stacks": "层数上限",
    "threshold": "触发阈值",
    "action_name": "动作名称",
    "hit_count": "段数",
    "target_side": "目标阵营",
    "target_type": "目标类型",
    "target": "作用目标",
    "count": "数量",
    "scale_stat": "加成属性",
    "required_skill_id": "要求技能ID",
    "required_skill_type": "要求技能类型",
    "required_skill_tag": "要求技能标签",
    "required_status_effect": "要求状态",
    "forbidden_status_effect": "排斥状态",
    "bonus_status": "关联状态",
    "bonus_value": "追加系数",
    "granted_stack_name": "授予层数",
    "granted_stack_amount": "授予层数值",
    "granted_stack_duration": "授予层持续",
    "granted_stack_max": "授予层上限",
    "granted_stack_action_name": "授予动作名",
    "clear_stack_name": "清除层数",
    "consumed_stack_name": "消耗层数",
    "used_marker_effect_type": "已触发标记",
    "linked_damage_reduction": "连线减伤",
    "heal_ratio_if_has_shield": "护盾回血系数",
    "heal_attack_ratio": "回血攻击系数",
    "shield_ratio": "护盾系数",
    "max_hp_ratio": "生命比例",
    "cap_attack_multiplier": "攻击倍率上限",
    "ally_trigger_chance": "友军触发概率",
    "splash_count": "溅射数量",
    "source_attack": "来源攻击",
    "damage_reduction": "伤害减免",
    "attack_bonus": "攻击加成",
    "crit_rate_bonus": "暴击加成",
    "invincible_duration": "无敌回合",
    "untargetable_duration": "不可选中回合",
    "blocked_by_control": "受控禁用",
    "blocked_by_tags": "受限标签",
    "blocked_by_effect_types": "受限状态",
    "hp_threshold": "生命阈值",
    "heal_scale": "治疗倍率来源",
    "delay_rounds": "延迟回合",
    "cooldown_rounds": "冷却回合",
    "max_triggers": "触发上限",
    "selection": "筛选方式",
    "row_filter": "排位筛选",
    "exclude_actor": "排除自身",
    "become_untargetable": "进入不可选中",
    "used_marker": "触发标记",
    "usage_marker": "次数标记",
    "usage_action_name": "次数动作名",
    "prepare_action_name": "准备动作名",
    "trigger_on_death": "阵亡时触发",
    "heal_action_name": "治疗动作名",
    "attack_bonus_per_stack": "每层攻击加成",
    "allowed_skill_types": "允许技能类型",
    "apply_effects_each_hit": "每段独立结算效果",
    "apply_effects_on_first_target_only": "仅首目标结算效果",
    "armor_break_per_stack": "每层破甲加成",
    "bonus_armor_break_from_status": "按状态追加破甲",
    "bonus_hit_count_from_status": "按状态追加段数",
    "hit_threshold": "受击阈值",
    "chainable": "可连锁",
    "convert_to_random_hits_if_frontline_below": "前排人数低于该值时转随机多段",
    "converted_hit_count": "转化后段数",
    "critical_bonus_ratio": "暴击追加系数",
    "energy_gain_chance": "回怒概率",
    "exclude_self": "排除自身",
    "guaranteed_first_target": "首目标必定命中",
    "invincible_pierce_ratio": "无敌穿透比例",
    "kill_bonus_action_name": "击杀追加动作",
    "kill_bonus_hit_count_by_level": "击杀追加段数",
    "kill_bonus_hit_count_status": "击杀叠加段数状态",
    "layers": "层数",
    "limit_per_round": "每回合上限",
    "lost_hp_damage_ratio": "已损血伤害比例",
    "low_hp_threshold": "低血线阈值",
    "max_times": "最多次数",
    "min_times": "最少次数",
    "multiplier": "倍率",
    "once_per_battle": "每场战斗一次",
    "per_round_limit": "每回合限制",
    "required_actions": "所需行动次数",
    "requires_last_skill_type": "要求上次技能类型",
    "retarget_per_hit": "每段重新选目标",
    "shield_duration": "护盾回合",
    "shield_ratio_per_stack": "每层护盾系数",
    "skill_tags": "技能标签",
    "stack_duration": "层数持续",
    "stat_name": "属性名称",
    "target_scope": "作用范围",
    "thresholds": "阈值列表",
    "attack_trigger_control_chance": "攻击时控制概率",
}

_IDENTIFIER_PARAM_KEYS = {
    "status_effect_type",
    "required_status_effect",
    "forbidden_status_effect",
    "bonus_status",
    "granted_stack_name",
    "stack_name",
    "clear_stack_name",
    "consumed_stack_name",
    "bonus_hit_count_from_status",
    "kill_bonus_hit_count_status",
    "bonus_armor_break_from_status",
    "consume_status_on_cast",
    "used_marker_effect_type",
    "status_filter",
    "blocked_by_effect_types",
}

_SIDE_PARAM_KEYS = {"target_side", "target"}
_SLOT_PARAM_KEYS = {"linked_skill_slot"}
_DISPLAY_NAME_PARAM_KEYS = {
    "scale_stat",
    "stat_name",
    "required_skill_tag",
    "skill_tags",
    "target_scope",
    "requires_last_skill_type",
    "required_skill_type",
    "allowed_skill_types",
    "blocked_by_tags",
}

_ACTION_SUFFIXES = ("被抵抗", "生效", "刷新", "覆盖", "解除")
_ACTION_PREFIXES = ("清除", "消耗")


def display_name(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    return DISPLAY_NAME_MAP.get(text, text)


def display_skill_slot_name(slot_key: str | None) -> str:
    return display_name(slot_key)


def display_status_name(status: str | None) -> str:
    return display_name(status)


def display_status_filter_name(status_filter: str | None) -> str:
    return display_name(status_filter)


def display_battle_action(action: str | None, metadata: dict[str, Any] | None = None) -> str:
    if action is None:
        return ""
    text = str(action)
    if not text:
        return ""
    for suffix in _ACTION_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return f"{display_status_name(text[: -len(suffix)])}{suffix}"
    for prefix in _ACTION_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            return f"{prefix}{display_status_name(text[len(prefix):])}"
    if text.startswith("移除 ") and len(text) > 3:
        return f"移除 {display_status_name(text[3:])}"
    if metadata:
        effect_type = metadata.get("effect_type") or metadata.get("status_delta")
        if text == effect_type:
            return display_status_name(str(effect_type))
    return display_name(text)


def display_status_list(statuses: list[str] | tuple[str, ...]) -> list[str]:
    return [display_status_name(status) for status in statuses]


def display_param_name(key: str) -> str:
    return PARAM_NAME_MAP.get(key, display_name(key))


def display_param_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, dict):
        nested = ", ".join(f"{display_param_name(str(nested_key))}={display_param_value(str(nested_key), nested_value)}" for nested_key, nested_value in value.items())
        return f"{{{nested}}}"
    if isinstance(value, list):
        return "[" + ", ".join(display_param_value(key, item) for item in value) + "]"
    if isinstance(value, tuple):
        return "(" + ", ".join(display_param_value(key, item) for item in value) + ")"
    if isinstance(value, str):
        if value.lower() in {"true", "false"}:
            return "是" if value.lower() == "true" else "否"
        if key in _IDENTIFIER_PARAM_KEYS:
            return display_status_name(value)
        if key in _SIDE_PARAM_KEYS:
            return display_name(value)
        if key in _SLOT_PARAM_KEYS:
            return display_skill_slot_name(value)
        if key in _DISPLAY_NAME_PARAM_KEYS:
            return display_name(value)
        return value if value not in DISPLAY_NAME_MAP else display_name(value)
    return str(value)

