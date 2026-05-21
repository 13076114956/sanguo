from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game.core.app import GameApplication, GameConfig


if __name__ == "__main__":
    app = GameApplication(GameConfig.from_project_root(PROJECT_ROOT))
    app.initialize()
    hero_overviews = app.list_visible_hero_skill_overviews()
    result = app.run_battle_demo()
    print(app.present_messages())
    if hero_overviews:
        print(app.console_view.render_hero_skill_overview_list(hero_overviews))
        print(app.console_view.render_hero_skill_overview(hero_overviews[0]))
    print(app.battle_view.render_summary(result))
    print(app.battle_view.render_logs(result))

