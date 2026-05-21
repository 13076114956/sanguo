# 技能槽迁移说明

## 背景

项目已将旧技能槽语义：

- `normal_attack_skill + passive_1 + passive_2 + ultimate`

迁移为新的正式结构：

- `passive_skill_3 + passive_1 + passive_2 + ultimate`

对应玩法含义为：

- **基础普攻** 不再占技能槽
- 基础普攻由战斗引擎内置为默认动作：`单体 / 100%攻击 / 行动时自动`
- 原“普攻被动槽”正式升格为 **第三被动槽**

## 当前正式写出结构

新配置、新存档、新序列化统一写为：

- 字段：`passive_skill_3`
- 槽位键：`passive_3`

## 兼容读取策略

为兼容旧配置和旧存档，读取阶段仍支持：

- 旧字段：`normal_attack_skill`
- 旧槽位键：`normal_attack`

在读入时会自动迁移为：

- `normal_attack_skill -> passive_skill_3`
- `normal_attack -> passive_3`

适用范围包括：

- 英雄配置反序列化
- 本地存档版本迁移
- 奇珍锁位与奇珍节点的旧引用

## 兼容边界说明

当前兼容仅用于：

- **读取旧数据**
- **展示旧日志或旧键名时的本地化映射**

当前代码不会再把以下名称作为新的正式结构继续写出：

- `normal_attack_skill`
- `normal_attack`
- `normal_slot_mode`

## 维护建议

后续若继续收敛兼容层，建议至少保留以下两处边界兼容：

1. `src/game/data/models.py` 的旧字段反序列化
2. `src/game/storage/repository.py` 的旧存档迁移

