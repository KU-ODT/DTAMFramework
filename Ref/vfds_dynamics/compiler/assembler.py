"""
VFDS Dynamics Dispatch System — Script Assembler

MissionIR을 Jinja2 템플릿에 전달하여 실행 가능한 MAVSDK-Python 스크립트를 생성한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .mission_to_ir import MissionIR

logger = logging.getLogger(__name__)

# 템플릿 디렉토리
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class Assembler:
    """
    IR → Python 스크립트 컴파일러.

    Jinja2 템플릿을 사용하여 MissionIR을 MAVSDK-Python 스크립트로 렌더링한다.
    """

    def __init__(self, output_dir: str | Path = "./output"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def compile(self, ir: MissionIR) -> Path:
        """
        MissionIR을 Python 스크립트로 컴파일하고 파일로 저장한다.

        Returns:
            생성된 스크립트 파일의 절대 경로
        """
        # 템플릿 로드
        template = self._env.get_template("mission_script.py.j2")

        # 렌더링
        script_content = template.render(ir=ir)

        # 파일명 생성
        filename = self._generate_filename(ir)
        output_path = self._output_dir / filename

        # 파일 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info(
            "Compiled script: %s (FP%d → %s)",
            filename, ir.flight_plan_number, ir.aircraft_id,
        )

        return output_path.resolve()

    def compile_to_string(self, ir: MissionIR) -> str:
        """
        MissionIR을 Python 스크립트 문자열로 컴파일한다.
        (파일 저장 없이 문자열만 반환)
        """
        template = self._env.get_template("mission_script.py.j2")
        return template.render(ir=ir)

    @staticmethod
    def _generate_filename(ir: MissionIR) -> str:
        """
        스크립트 파일명 생성.
        형식: {aircraftId}_FP{number}_{date}_{std}.py
        """
        date_str = datetime.now().strftime("%Y%m%d")
        std_clean = ir.std.replace(":", "")[:4]  # "09:00:00" → "0900"
        return f"{ir.aircraft_id}_FP{ir.flight_plan_number}_{date_str}_{std_clean}.py"

    @property
    def output_dir(self) -> Path:
        return self._output_dir
