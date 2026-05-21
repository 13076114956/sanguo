from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from game.data.models import PlayerData, player_from_dict
from game.utility.crypto_utils import CryptoUtils, EncryptedPayload
from game.utility.json_utils import JsonUtils


class SQLiteRepository:
    """轻量 SQLite 封装，支持事务。"""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._connection
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._connection.execute(sql, parameters)

    def query_all(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cursor = self._connection.execute(sql, parameters)
        return [dict(row) for row in cursor.fetchall()]

    def insert(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        self._connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
        self._connection.commit()

    def update(self, table: str, values: dict[str, Any], where_clause: str, where_params: tuple[Any, ...]) -> None:
        set_clause = ", ".join(f"{key} = ?" for key in values)
        params = tuple(values.values()) + where_params
        self._connection.execute(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)
        self._connection.commit()

    def delete(self, table: str, where_clause: str, where_params: tuple[Any, ...]) -> None:
        self._connection.execute(f"DELETE FROM {table} WHERE {where_clause}", where_params)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class ConfigLoader:
    """JSON 配置加载与缓存。"""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self._cache: dict[str, Any] = {}

    def load(self, name: str, *, force_reload: bool = False) -> Any:
        if not force_reload and name in self._cache:
            return self._cache[name]
        path = self.config_dir / f"{name}.json"
        data = JsonUtils.load_from_file(path)
        self._cache[name] = data
        return data

    def clear(self) -> None:
        self._cache.clear()


class MigrationManager:
    """玩家数据版本迁移。

    当前仅保留旧 `normal_attack_skill` / `normal_attack` 到
    `passive_skill_3` / `passive_3` 的读入兼容；新存档统一写出新字段。
    """

    CURRENT_VERSION = 2

    def migrate(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        version = int(raw_data.get("version", 1) or 1)
        migrated = dict(raw_data)
        if version < 2:
            migrated = self._migrate_skill_slot_schema(migrated)
        migrated["version"] = self.CURRENT_VERSION
        return migrated

    def _migrate_skill_slot_schema(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        migrated = dict(raw_data)
        migrated["heroes"] = [self._migrate_hero_skill_slots(dict(hero)) for hero in raw_data.get("heroes", [])]
        return migrated

    @staticmethod
    def _migrate_hero_skill_slots(hero_data: dict[str, Any]) -> dict[str, Any]:
        # 旧存档中的第三被动仍可能写作 normal_attack_skill，这里在读档时升级。
        if "passive_skill_3" not in hero_data and "normal_attack_skill" in hero_data:
            hero_data["passive_skill_3"] = hero_data.pop("normal_attack_skill")
        # 旧奇珍锁位/节点引用在读档时统一收敛为 passive_3。
        hero_data["rare_treasure_locked_skill_slots"] = [
            "passive_3" if slot == "normal_attack" else slot
            for slot in hero_data.get("rare_treasure_locked_skill_slots", [])
        ]
        for node in hero_data.get("rare_treasure_nodes", []):
            if node.get("linked_skill_slot") == "normal_attack":
                node["linked_skill_slot"] = "passive_3"
        return hero_data


class SaveRepository:
    """本地存档仓库，支持 5 个槽位、加密、导入导出。"""

    MAX_SLOTS = 5

    def __init__(self, save_dir: Path, *, secret: str, migration_manager: MigrationManager | None = None) -> None:
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.secret = secret
        self.migration_manager = migration_manager or MigrationManager()

    def save(self, slot: int, player: PlayerData) -> Path:
        self._validate_slot(slot)
        payload = JsonUtils.dumps(player.to_dict())
        encrypted = CryptoUtils.encrypt_text(payload, secret=self.secret)
        path = self._path_for_slot(slot)
        path.write_text(JsonUtils.dumps({"cipher_text": encrypted.cipher_text, "checksum": encrypted.checksum}), encoding="utf-8")
        return path

    def load(self, slot: int) -> PlayerData:
        self._validate_slot(slot)
        path = self._path_for_slot(slot)
        raw = JsonUtils.load_from_file(path)
        payload = EncryptedPayload(cipher_text=raw["cipher_text"], checksum=raw["checksum"])
        plain_text = CryptoUtils.decrypt_text(payload, secret=self.secret)
        data = self.migration_manager.migrate(json.loads(plain_text))
        return player_from_dict(data)

    def delete(self, slot: int) -> None:
        self._validate_slot(slot)
        path = self._path_for_slot(slot)
        if path.exists():
            path.unlink()

    def list_slots(self) -> list[dict[str, Any]]:
        result = []
        for slot in range(1, self.MAX_SLOTS + 1):
            path = self._path_for_slot(slot)
            summary = {"slot": slot, "exists": path.exists(), "path": str(path)}
            if path.exists():
                try:
                    player = self.load(slot)
                    summary["summary"] = {
                        "name": player.profile.name,
                        "level": player.profile.level,
                        "power": player.profile.power,
                        "hero_count": len(player.heroes),
                    }
                except Exception as exc:
                    summary["summary"] = {"error": str(exc)}
            result.append(summary)
        return result

    def export_slot(self, slot: int, destination: Path) -> Path:
        self._validate_slot(slot)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self._path_for_slot(slot).read_text(encoding="utf-8"), encoding="utf-8")
        return destination

    def import_slot(self, slot: int, source: Path) -> Path:
        self._validate_slot(slot)
        raw = JsonUtils.load_from_file(source)
        if "cipher_text" not in raw or "checksum" not in raw:
            raise ValueError("导入存档格式非法")
        payload = EncryptedPayload(cipher_text=raw["cipher_text"], checksum=raw["checksum"])
        CryptoUtils.decrypt_text(payload, secret=self.secret)
        path = self._path_for_slot(slot)
        path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return path

    def _path_for_slot(self, slot: int) -> Path:
        return self.save_dir / f"slot_{slot}.sav"

    @staticmethod
    def _validate_slot(slot: int) -> None:
        if slot < 1 or slot > SaveRepository.MAX_SLOTS:
            raise ValueError("存档槽位必须在 1 到 5 之间")

