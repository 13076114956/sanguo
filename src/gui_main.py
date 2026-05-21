from __future__ import annotations

from pathlib import Path

from game.ui.game_scene_app import run_game_scene_app


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    run_game_scene_app(project_root)


if __name__ == "__main__":
    main()

