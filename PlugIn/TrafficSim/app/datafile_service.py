from __future__ import annotations
import csv
import io
import os
import shutil
import time
from pathlib import Path
from typing import Optional
def _safe_join(base_dir: Path, request_path: str) -> Optional[Path]:
    safe_path = os.path.normpath(request_path).lstrip("/\\")
    full = (base_dir / safe_path).resolve()
    if base_dir != full and base_dir not in full.parents:
        return None
    return full
def _parse_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
class DatafileService:
    def __init__(self, data_dir: Path, api: object) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.api = api
    def clone_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self._clone_datafile(payload)
    def append_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self._append_datafile(payload)
    def update_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self._update_datafile(payload)
    def delete_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        return self._delete_datafile(payload)
    def apply_datafiles(self, payload: dict[str, object]) -> dict[str, object]:
        return self._apply_datafiles(payload)
    def resolve_datafile_path(self, value: object) -> Optional[Path]:
        if value:
            text = str(value).strip()
            if text.startswith('/api/data/'):
                value = '/data/' + text[len('/api/data/'):]
            elif text.startswith('api/data/'):
                value = '/data/' + text[len('api/data/'):]
        return self._resolve_datafile_path(value)

    def _clone_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "vertiport":
            source_name = "vertiport_default.csv"
            prefix = "vertiport_"
        elif kind == "corridor":
            source_name = "corridor_default.csv"
            prefix = "corridor_"
        elif kind == "basestation":
            source_name = "basestation_default.csv"
            prefix = "basestation_"
        else:
            return {"ok": False, "message": "Invalid data file type."}

        default_dir = (self.data_dir / "default").resolve()
        custom_dir = (self.data_dir / "customed").resolve()
        source_path = (default_dir / source_name).resolve()
        if not source_path.is_file():
            return {"ok": False, "message": "Source data file not found."}

        timestamp = time.strftime("%y%m%d%H%M")
        base_name = f"{prefix}{timestamp}.csv"
        try:
            custom_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"ok": False, "message": "Failed to create custom data folder."}
        target_path = (custom_dir / base_name).resolve()
        if target_path.exists():
            counter = 1
            while True:
                candidate = f"{prefix}{timestamp}_{counter:02d}.csv"
                target_path = (custom_dir / candidate).resolve()
                if not target_path.exists():
                    break
                counter += 1

        try:
            shutil.copy2(source_path, target_path)
        except OSError:
            return {"ok": False, "message": "Failed to copy data file."}

        return {
            "ok": True,
            "name": target_path.name,
            "url": f"/data/customed/{target_path.name}",
        }

    def _append_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "corridor":
            return self._append_corridor_datafile(payload)
        if kind == "basestation":
            return self._append_basestation_datafile(payload)
        if kind != "vertiport":
            return {"ok": False, "message": "Invalid data file type."}

        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        entry = payload.get("entry")
        if not isinstance(entry, dict):
            return {"ok": False, "message": "Missing entry payload."}

        name = str(entry.get("name") or "").strip()
        class_name = str(entry.get("class") or "").strip().lower()
        if not name:
            return {"ok": False, "message": "Missing vertiport name."}
        if class_name not in ("port", "hub"):
            return {"ok": False, "message": "Invalid vertiport class."}

        lat = _parse_float(entry.get("lat"))
        lon = _parse_float(entry.get("lon"))
        if lat is None or lon is None:
            return {"ok": False, "message": "Invalid coordinates."}

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text = text.rstrip("0").rstrip(".")
            return text

        inr_km = _fmt_number(entry.get("inr_km"), 1)
        otr_km = _fmt_number(entry.get("otr_km"), 1)
        mtr_km = _fmt_number(entry.get("mtr_km"), 1)
        inr_deg = _fmt_number(entry.get("inr_deg"), 0)
        otr_deg = _fmt_number(entry.get("otr_deg"), 0)
        circle_turn = str(entry.get("circle_turn") or "").strip() or "Left"
        link = str(entry.get("link") or "")

        row = [
            name,
            class_name,
            _fmt_number(lat, 6),
            _fmt_number(lon, 6),
            inr_km,
            otr_km,
            mtr_km,
            inr_deg,
            otr_deg,
            circle_turn,
            link,
        ]

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(row)
        line = output.getvalue().rstrip("\r\n") + line_ending
        prefix = "" if not raw or raw.endswith(b"\n") else line_ending
        try:
            with open(file_path, "ab") as handle:
                handle.write(prefix.encode(encoding, errors="ignore"))
                handle.write(line.encode(encoding, errors="ignore"))
        except OSError:
            return {"ok": False, "message": "Failed to append data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _append_basestation_datafile(
        self, payload: dict[str, object]
    ) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        entry = payload.get("entry")
        if not isinstance(entry, dict):
            return {"ok": False, "message": "Missing entry payload."}

        name = str(entry.get("name") or "").strip()
        if not name:
            return {"ok": False, "message": "Missing base station name."}

        lat = _parse_float(entry.get("lat"))
        lon = _parse_float(entry.get("lon"))
        if lat is None or lon is None:
            return {"ok": False, "message": "Invalid coordinates."}

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text = text.rstrip("0").rstrip(".")
            return text

        row = [
            name,
            _fmt_number(lat, 6),
            _fmt_number(lon, 6),
        ]

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        header = rows[0]
        normalized = [
            cell.strip().lower().replace(" ", "").replace("_", "") for cell in header
        ]
        start_index = 1 if "lat" in normalized and "lon" in normalized else 0
        for existing in rows[start_index:]:
            if existing and existing[0].strip() == name:
                return {"ok": False, "message": "Base station name already exists."}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(row)
        line = output.getvalue().rstrip("\r\n") + line_ending
        prefix = "" if not raw or raw.endswith(b"\n") else line_ending
        try:
            with open(file_path, "ab") as handle:
                handle.write(prefix.encode(encoding, errors="ignore"))
                handle.write(line.encode(encoding, errors="ignore"))
        except OSError:
            return {"ok": False, "message": "Failed to append data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _normalize_corridor_rows(
        self, rows: list[list[str]]
    ) -> tuple[list[list[str]], bool]:
        if not rows:
            return rows, False
        updated = False
        header = rows[0]
        normalized = [
            cell.strip().lower().replace(" ", "").replace("_", "") for cell in header
        ]
        if "sparelink" not in normalized:
            header.append("spare_link")
            updated = True
        target_len = max(len(header), 6)
        if len(header) < target_len:
            header.extend([""] * (target_len - len(header)))
            updated = True
        for row in rows[1:]:
            if len(row) < target_len:
                row.extend([""] * (target_len - len(row)))
                updated = True
        return rows, updated

    def _normalize_vertiport_rows(
        self, rows: list[list[str]]
    ) -> tuple[list[list[str]], bool]:
        if not rows:
            return rows, False
        updated = False
        target_len = 11
        header = rows[0]
        if len(header) > target_len:
            header[:] = header[:target_len]
            updated = True
        if len(header) < target_len:
            header.extend([""] * (target_len - len(header)))
            updated = True
        for row in rows[1:]:
            if len(row) > target_len:
                link_parts = [part.strip() for part in row[target_len - 1 :] if part.strip()]
                row[:] = row[: target_len - 1] + [", ".join(link_parts)]
                updated = True
            elif len(row) < target_len:
                row.extend([""] * (target_len - len(row)))
                updated = True
        return rows, updated

    def _append_corridor_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        entry = payload.get("entry")
        if not isinstance(entry, dict):
            return {"ok": False, "message": "Missing entry payload."}

        name = str(entry.get("name") or "").strip()
        if not name:
            return {"ok": False, "message": "Missing corridor name."}

        lat = _parse_float(entry.get("lat"))
        lon = _parse_float(entry.get("lon"))
        if lat is None or lon is None:
            return {"ok": False, "message": "Invalid coordinates."}

        alt_ft = _parse_float(entry.get("alt_ft"))
        if alt_ft is None:
            alt_ft = 1000.0

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text = text.rstrip("0").rstrip(".")
            return text

        link = str(entry.get("link") or "")
        spare_link = str(entry.get("spare_link") or "")
        row = [
            name,
            _fmt_number(lat, 6),
            _fmt_number(lon, 6),
            _fmt_number(alt_ft, 0),
            link,
            spare_link,
        ]

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        rows, _ = self._normalize_corridor_rows(rows)
        for existing in rows[1:]:
            if existing and existing[0].strip() == name:
                return {"ok": False, "message": "Corridor name already exists."}

        rows.append(row)
        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for record in rows:
            writer.writerow(record)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to append data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _update_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "corridor":
            return self._update_corridor_datafile(payload)
        if kind == "basestation":
            return self._update_basestation_datafile(payload)
        if kind != "vertiport":
            return {"ok": False, "message": "Invalid data file type."}

        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing vertiport name."}

        updates = payload.get("updates")
        if not isinstance(updates, dict):
            updates = {}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        rows, _ = self._normalize_vertiport_rows(rows)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        next_name = None
        if "name" in updates:
            next_name = str(updates.get("name") or "").strip()
            if not next_name:
                return {"ok": False, "message": "Missing vertiport name."}

        if next_name and next_name != target:
            for row in rows:
                if row and row[0].strip() == next_name:
                    return {"ok": False, "message": "Vertiport name already exists."}

        class_name = None
        if "class" in updates:
            class_name = str(updates.get("class") or "").strip().lower()
            if class_name not in ("port", "hub"):
                return {"ok": False, "message": "Invalid vertiport class."}

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text_value = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text_value = text_value.rstrip("0").rstrip(".")
            return text_value

        def _parse_link_list(value: object) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                items = value
            else:
                items = str(value).split(",")
            cleaned: list[str] = []
            seen: set[str] = set()
            for item in items:
                text = str(item).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                cleaned.append(text)
            return cleaned

        lat_value = None
        if "lat" in updates:
            lat = _parse_float(updates.get("lat"))
            if lat is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lat_value = _fmt_number(lat, 6)

        lon_value = None
        if "lon" in updates:
            lon = _parse_float(updates.get("lon"))
            if lon is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lon_value = _fmt_number(lon, 6)

        fields = {
            "inr_km": 4,
            "otr_km": 5,
            "mtr_km": 6,
            "inr_deg": 7,
            "otr_deg": 8,
        }
        link_value = None
        if "link" in updates:
            link_value = updates.get("link")
        link_append_requested = "link_append" in updates
        link_remove_requested = "link_remove" in updates
        link_append = (
            _parse_link_list(updates.get("link_append")) if link_append_requested else []
        )
        link_remove = (
            _parse_link_list(updates.get("link_remove")) if link_remove_requested else []
        )

        updated = False
        for row in rows:
            if not row:
                continue
            row_name = row[0].strip() if row else ""
            if row_name != target:
                continue
            if len(row) < 11:
                row.extend([""] * (11 - len(row)))
            if next_name:
                row[0] = next_name
            if class_name:
                row[1] = class_name
            if lat_value is not None:
                row[2] = lat_value
            if lon_value is not None:
                row[3] = lon_value
            for key, idx in fields.items():
                if key not in updates:
                    continue
                value = _parse_float(updates.get(key))
                if value is None:
                    return {"ok": False, "message": f"Invalid {key} value."}
                row[idx] = _fmt_number(value, 1 if key.endswith("_km") else 0)
            if "circle_turn" in updates:
                row[9] = str(updates.get("circle_turn") or "").strip()
            if "link" in updates or link_append_requested or link_remove_requested:
                current_links = _parse_link_list(row[10])
                if link_value is not None:
                    current_links = _parse_link_list(link_value)
                if link_append:
                    for entry in link_append:
                        if entry not in current_links:
                            current_links.append(entry)
                if link_remove:
                    remove_set = set(link_remove)
                    current_links = [
                        entry for entry in current_links if entry not in remove_set
                    ]
                row[10] = ", ".join(current_links)
            updated = True
            break

        if not updated:
            return {"ok": False, "message": "Vertiport name not found."}

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in rows:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _update_corridor_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing corridor name."}

        updates = payload.get("updates")
        if not isinstance(updates, dict):
            updates = {}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        rows, _ = self._normalize_corridor_rows(rows)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        next_name = None
        if "name" in updates:
            next_name = str(updates.get("name") or "").strip()
            if not next_name:
                return {"ok": False, "message": "Missing corridor name."}

        if next_name and next_name != target:
            for row in rows:
                if row and row[0].strip() == next_name:
                    return {"ok": False, "message": "Corridor name already exists."}

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text_value = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text_value = text_value.rstrip("0").rstrip(".")
            return text_value

        lat_value = None
        if "lat" in updates:
            lat = _parse_float(updates.get("lat"))
            if lat is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lat_value = _fmt_number(lat, 6)

        lon_value = None
        if "lon" in updates:
            lon = _parse_float(updates.get("lon"))
            if lon is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lon_value = _fmt_number(lon, 6)

        alt_value = None
        if "alt_ft" in updates:
            alt = _parse_float(updates.get("alt_ft"))
            if alt is None:
                return {"ok": False, "message": "Invalid altitude."}
            alt_value = _fmt_number(alt, 0)

        link_value = None
        if "link" in updates:
            link_value = str(updates.get("link") or "")

        spare_link_value = None
        if "spare_link" in updates:
            spare_link_value = str(updates.get("spare_link") or "")

        updated = False
        for row in rows:
            if not row:
                continue
            row_name = row[0].strip() if row else ""
            if row_name != target:
                continue
            if len(row) < 6:
                row.extend([""] * (6 - len(row)))
            if next_name:
                row[0] = next_name
            if lat_value is not None:
                row[1] = lat_value
            if lon_value is not None:
                row[2] = lon_value
            if alt_value is not None:
                row[3] = alt_value
            if link_value is not None:
                row[4] = link_value
            if spare_link_value is not None:
                row[5] = spare_link_value
            updated = True
            break

        if not updated:
            return {"ok": False, "message": "Corridor name not found."}

        def _replace_link(cell: str, old: str, new: str) -> str:
            parts = [part.strip() for part in str(cell).split(",") if part.strip()]
            if not parts:
                return ""
            updated_parts = [new if part == old else part for part in parts]
            return ", ".join(updated_parts)

        if next_name and next_name != target:
            for row in rows:
                if not row or len(row) < 5:
                    continue
                if row[4]:
                    row[4] = _replace_link(row[4], target, next_name)
                if len(row) >= 6 and row[5]:
                    row[5] = _replace_link(row[5], target, next_name)

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in rows:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _update_basestation_datafile(
        self, payload: dict[str, object]
    ) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing base station name."}

        updates = payload.get("updates")
        if not isinstance(updates, dict):
            updates = {}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        header = rows[0]
        normalized = [
            cell.strip().lower().replace(" ", "").replace("_", "") for cell in header
        ]
        has_header = "lat" in normalized and "lon" in normalized
        start_index = 1 if has_header else 0

        next_name = None
        if "name" in updates:
            next_name = str(updates.get("name") or "").strip()
            if not next_name:
                return {"ok": False, "message": "Missing base station name."}

        if next_name and next_name != target:
            for row in rows[start_index:]:
                if row and row[0].strip() == next_name:
                    return {"ok": False, "message": "Base station name already exists."}

        def _fmt_number(value: object, decimals: int) -> str:
            parsed = _parse_float(value)
            if parsed is None:
                return ""
            if abs(parsed) < 1e-9:
                return "0"
            text_value = f"{parsed:.{decimals}f}"
            if decimals > 0:
                text_value = text_value.rstrip("0").rstrip(".")
            return text_value

        lat_value = None
        if "lat" in updates:
            lat = _parse_float(updates.get("lat"))
            if lat is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lat_value = _fmt_number(lat, 6)

        lon_value = None
        if "lon" in updates:
            lon = _parse_float(updates.get("lon"))
            if lon is None:
                return {"ok": False, "message": "Invalid coordinates."}
            lon_value = _fmt_number(lon, 6)

        updated = False
        for row in rows[start_index:]:
            if not row:
                continue
            row_name = row[0].strip() if row else ""
            if row_name != target:
                continue
            if len(row) < 3:
                row.extend([""] * (3 - len(row)))
            if next_name:
                row[0] = next_name
            if lat_value is not None:
                row[1] = lat_value
            if lon_value is not None:
                row[2] = lon_value
            updated = True
            break

        if not updated:
            return {"ok": False, "message": "Base station name not found."}

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in rows:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _delete_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "corridor":
            return self._delete_corridor_datafile(payload)
        if kind == "basestation":
            return self._delete_basestation_datafile(payload)
        if kind != "vertiport":
            return {"ok": False, "message": "Invalid data file type."}

        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing vertiport name."}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        remaining = [row for row in rows if not row or row[0].strip() != target]
        if len(remaining) == len(rows):
            return {"ok": False, "message": "Vertiport name not found."}

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in remaining:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _delete_basestation_datafile(
        self, payload: dict[str, object]
    ) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing base station name."}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        header = rows[0]
        normalized = [
            cell.strip().lower().replace(" ", "").replace("_", "") for cell in header
        ]
        has_header = "lat" in normalized and "lon" in normalized
        start_index = 1 if has_header else 0

        remaining: list[list[str]] = []
        if has_header:
            remaining.append(rows[0])
        removed = False
        for row in rows[start_index:]:
            if row and row[0].strip() == target:
                removed = True
                continue
            remaining.append(row)

        if not removed:
            return {"ok": False, "message": "Base station name not found."}

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in remaining:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }

    def _delete_corridor_datafile(self, payload: dict[str, object]) -> dict[str, object]:
        file_name = str(payload.get("file") or "").strip()
        if not file_name or "/" in file_name or "\\" in file_name:
            return {"ok": False, "message": "Invalid file name."}

        target = str(payload.get("target") or payload.get("name") or "").strip()
        if not target:
            return {"ok": False, "message": "Missing corridor name."}

        custom_dir = (self.data_dir / "customed").resolve()
        file_path = _safe_join(custom_dir, file_name)
        if file_path is None or not file_path.is_file():
            return {"ok": False, "message": "Target data file not found."}

        try:
            raw = file_path.read_bytes()
        except OSError:
            return {"ok": False, "message": "Failed to read data file."}

        if raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "cp949"

        line_ending = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode(encoding, errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {"ok": False, "message": "Data file is empty."}

        def _remove_link(cell: str, name: str) -> str:
            parts = [part.strip() for part in str(cell).split(",") if part.strip()]
            if not parts:
                return ""
            filtered = [part for part in parts if part != name]
            return ", ".join(filtered)

        remaining = []
        removed = False
        for row in rows:
            if row and row[0].strip() == target:
                removed = True
                continue
            if row and len(row) >= 5 and row[4]:
                row[4] = _remove_link(row[4], target)
            if row and len(row) >= 6 and row[5]:
                row[5] = _remove_link(row[5], target)
            remaining.append(row)

        if not removed:
            return {"ok": False, "message": "Corridor name not found."}

        output = io.StringIO()
        writer = csv.writer(output, lineterminator=line_ending)
        for row in remaining:
            writer.writerow(row)
        try:
            with open(file_path, "w", encoding=encoding, newline="") as handle:
                handle.write(output.getvalue())
        except OSError:
            return {"ok": False, "message": "Failed to update data file."}

        return {
            "ok": True,
            "name": file_path.name,
            "url": f"/data/customed/{file_path.name}",
        }


    def _apply_datafiles(self, payload: dict[str, object]) -> dict[str, object]:
        vertiport_path = self._resolve_datafile_path(payload.get("vertiport"))
        corridor_path = self._resolve_datafile_path(payload.get("corridor"))
        basestation_path = self._resolve_datafile_path(payload.get("basestation"))
        if not vertiport_path or not corridor_path:
            return {"ok": False, "message": "Invalid data file path."}
        return self.api.apply_datafiles(
            vertiport_path,
            corridor_path,
            basestation_path=basestation_path,
        )

    def _resolve_datafile_path(self, value: object) -> Optional[Path]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("/data/"):
            text = text[len("/data/") :]
        text = text.lstrip("/\\")
        file_path = _safe_join(self.data_dir, text)
        if file_path is None or not file_path.is_file():
            return None
        return file_path



