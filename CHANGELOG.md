# Changelog

## 2026-05-21

### 技能槽结构迁移

- 将旧的 `normal_attack_skill + passive_1 + passive_2 + ultimate` 结构迁移为 `passive_skill_3 + passive_1 + passive_2 + ultimate`
- 将基础普攻明确为战斗引擎内置默认动作，不再占技能槽
- 旧 `normal_attack_skill` 会在读取时自动迁移到 `passive_skill_3`
- 旧 `normal_attack` 槽位键会在读取时自动迁移到 `passive_3`
- 第三被动触发模式参数正式统一为 `passive_skill_3_mode`，旧 `normal_slot_mode` 仅保留读取兼容
- 配置、奇珍锁位、UI 文案、测试与文档已同步到新结构

