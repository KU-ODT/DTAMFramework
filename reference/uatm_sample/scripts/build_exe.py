from __future__ import annotations

import argparse
import struct
import subprocess
import sys
from io import BytesIO
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> int:
    try:
        subprocess.run(cmd, check=True, cwd=str(cwd))
    except FileNotFoundError:
        return 2
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


def _read_png_size(png_path: Path) -> tuple[int, int, bytes]:
    data = png_path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a PNG file.")
    if data[12:16] != b"IHDR":
        raise ValueError("Invalid PNG header.")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height, data


def _resize_png_to_256(png_path: Path) -> tuple[int, int, bytes]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required to resize the icon.") from exc
    with Image.open(png_path) as img:
        img = img.convert("RGBA")
        img.thumbnail((256, 256), Image.LANCZOS)
        canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        offset = ((256 - img.width) // 2, (256 - img.height) // 2)
        canvas.paste(img, offset)
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return 256, 256, buffer.getvalue()


def _write_ico_from_png(png_path: Path, ico_path: Path) -> None:
    width, height, data = _read_png_size(png_path)
    if width < 1 or height < 1:
        raise ValueError("PNG size must be at least 1x1.")
    if width > 256 or height > 256:
        width, height, data = _resize_png_to_256(png_path)
    width_byte = 0 if width == 256 else width
    height_byte = 0 if height == 256 else height
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        width_byte,
        height_byte,
        0,
        0,
        1,
        32,
        len(data),
        6 + 16,
    )
    ico_path.write_bytes(header + entry + data)


def _ensure_icon(png_path: Path, ico_path: Path) -> bool:
    if not png_path.is_file():
        print(f"Missing icon PNG: {png_path}")
        return False
    if ico_path.exists():
        if ico_path.stat().st_mtime >= png_path.stat().st_mtime:
            return True
    try:
        _write_ico_from_png(png_path, ico_path)
    except Exception as exc:
        print(f"Failed to build icon: {exc}")
        return False
    return True


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build the TrafficS Windows executable.")
    parser.add_argument("--spec", default="UATM.spec", help="PyInstaller spec file.")
    parser.add_argument(
        "--distpath",
        default=str(root_dir / "product"),
        help="Output folder for the distribution bundle.",
    )
    parser.add_argument(
        "--workpath",
        default=str(root_dir / "build" / "pyinstaller"),
        help="Build workspace folder.",
    )
    parser.add_argument(
        "--icon-png",
        default="resources/TrafficSim.png",
        help="Source PNG icon.",
    )
    parser.add_argument(
        "--icon-ico",
        default="resources/TrafficSim.ico",
        help="Generated ICO icon path.",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Also build the Inno Setup installer.",
    )
    parser.add_argument(
        "--iscc",
        default=r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        help="Path to Inno Setup ISCC.exe.",
    )
    args = parser.parse_args()

    spec_path = (root_dir / args.spec).resolve()
    if not spec_path.is_file():
        print(f"Missing spec file: {spec_path}")
        return 1

    icon_png = (root_dir / args.icon_png).resolve()
    icon_ico = (root_dir / args.icon_ico).resolve()
    if not _ensure_icon(icon_png, icon_ico):
        return 1

    distpath = (root_dir / args.distpath).resolve()
    workpath = (root_dir / args.workpath).resolve()

    result = _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(distpath),
            "--workpath",
            str(workpath),
            str(spec_path),
        ],
        root_dir,
    )
    if result != 0:
        if result == 2:
            print("PyInstaller not found. Install with: pip install pyinstaller")
        return result

    if not args.installer:
        print("Executable build complete.")
        return 0

    iss_path = (root_dir / "UATM.iss").resolve()
    if not iss_path.is_file():
        print(f"Missing installer script: {iss_path}")
        return 1

    iscc_path = Path(args.iscc)
    if not iscc_path.is_file():
        print(f"ISCC.exe not found at: {iscc_path}")
        return 1

    result = _run([str(iscc_path), str(iss_path)], root_dir)
    if result == 0:
        print("Installer build complete.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
