"""视频码率计算器 - 纯标准库的计算与媒体时长读取。"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

CODECS = {
    "AV1": {
        "encoder": "AV1 (SVT-AV1，优先 10-bit)",
        "preset": "4；编码慢可改为 5 或 6",
        "container": "MP4（上传前确认网站兼容）；也可 MKV",
        "tip": "相同码率下通常更高效；耗时较长。10-bit 不会恢复原片中没有的细节。",
        "thresholds": (12500, 4200, 2000, 1650, 800),
    },
    "H.265 / HEVC": {
        "encoder": "H.265 (x265 10-bit，软件编码)",
        "preset": "Slow（压制时间不足可 Medium）",
        "container": "MP4 或 MKV",
        "tip": "压缩效率较好，兼容性通常不如 H.264。",
        "thresholds": (16000, 5400, 2900, 2250, 1150),
    },
    "H.264 / AVC": {
        "encoder": "H.264 (x264，软件编码)",
        "preset": "Slow（压制时间不足可 Medium）",
        "container": "MP4",
        "tip": "兼容性最好，但同样大小下更容易牺牲画质。",
        "thresholds": (22000, 8500, 4300, 3800, 1900),
    },
    "VP9": {
        "encoder": "VP9 (libvpx-vp9；按软件可用选 10-bit)",
        "preset": "偏慢 / 高质量（视 HandBrake 版本显示）",
        "container": "WebM 或 MKV（要先确认网站支持）",
        "tip": "编码慢；与 H.265 画质表现接近，但支持情况因平台而异。",
        "thresholds": (16000, 5900, 3100, 2400, 1250),
    },
}
PROFILES = {
    "综合（一般游戏）": 1.0,
    "高速战斗 / 大量粒子": 1.3,
    "风景 / 慢节奏": 0.85,
}

@dataclass(frozen=True)
class Budget:
    seconds: float
    limit_mb: float
    target_mb: float
    audio_kbps: int
    overhead_pct: float
    video_kbps: int
    total_kbps: int
    estimated_mb: float


def _positive_number(text: str, field: str) -> float:
    try:
        n = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}请输入数字。") from None
    if not n.is_finite() or n <= 0:
        raise ValueError(f"{field}必须大于 0。")
    if n > 100000000:
        raise ValueError(f"{field}数值过大。")
    return float(n)


def parse_duration(text: str) -> float:
    """支持 SS、MM:SS、HH:MM:SS；最后一部分可以有小数。"""
    raw = str(text).strip().replace("：", ":")
    parts = raw.split(":")
    if not 1 <= len(parts) <= 3 or any(not p for p in parts):
        raise ValueError("时长格式应为 分:秒（如 9:38）或 时:分:秒。")
    try:
        values = [Decimal(p) for p in parts]
    except InvalidOperation:
        raise ValueError("时长格式应为 分:秒（如 9:38）或 时:分:秒。") from None
    if any(not v.is_finite() or v < 0 for v in values):
        raise ValueError("时长不能为负数。")
    if len(parts) > 1 and values[-1] >= 60:
        raise ValueError("秒数须小于 60。")
    if len(parts) == 3 and values[1] >= 60:
        raise ValueError("分钟数须小于 60。")
    if len(parts) > 1 and (values[0] != int(values[0]) or (len(parts) == 3 and values[1] != int(values[1]))):
        raise ValueError("小时和分钟须是整数。")
    if len(parts) == 3:
        seconds = values[0] * 3600 + values[1] * 60 + values[2]
    elif len(parts) == 2:
        seconds = values[0] * 60 + values[1]
    else:
        seconds = values[0]
    if not seconds or seconds > 86400 * 10:
        raise ValueError("视频时长须大于 0，且不超过 10 天。")
    return float(seconds)


def format_duration(seconds: float) -> str:
    s = int(round(seconds))
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    return f"{h}:{m:02}:{sec:02}" if h else f"{m}:{sec:02}"


def calculate(duration: str, limit_mb: str, target_mb: str,
              audio_kbps: str, overhead_pct: str) -> Budget:
    seconds = parse_duration(duration)
    limit = _positive_number(limit_mb, "上传上限")
    target = _positive_number(target_mb, "安全目标")
    if target >= limit:
        raise ValueError("安全目标需小于上传上限，以预留余量。")
    try:
        audio_val = Decimal(str(audio_kbps).strip())
        overhead_val = Decimal(str(overhead_pct).strip())
    except InvalidOperation:
        raise ValueError("音频码率和封装余量须输入数字。") from None
    if not audio_val.is_finite() or audio_val < 0 or audio_val > 2048:
        raise ValueError("音频码率须在 0～2048 Kbps 内；多音轨请填总和。")
    if not overhead_val.is_finite() or not (0 <= overhead_val <= 15):
        raise ValueError("封装余量须在 0～15% 内。")
    # 十进制 1 MB = 1,000,000 bytes；1 MB 对应 8,000 千比特。
    # 从目标容积里扣掉封装比例和所有音轨，向下取整作为视频平均码率。
    video = math.floor((target * 8000 / seconds) * (1 - float(overhead_val) / 100) - float(audio_val))
    if video < 100:
        raise ValueError("留给视频的码率不足 100 Kbps，请缩短视频、放宽体积或降低音频码率。")
    if audio_val != int(audio_val):
        raise ValueError("音频码率请填写整数 Kbps（例如 128）。")
    audio = int(audio_val)
    total = video + audio
    estimated = (total * seconds / 8000) / (1 - float(overhead_val) / 100)
    return Budget(seconds, limit, target, audio, float(overhead_val), video, total, estimated)


def recommend(codec: str, video_kbps: int, profile: str = "综合（一般游戏）") -> tuple[str, str]:
    """粗略建议，不是客观的画质保证。"""
    factor = PROFILES.get(profile, 1.0)
    limits = [int(t * factor) for t in CODECS[codec]["thresholds"]]
    options = ["2560×1440 @ 60 FPS", "1920×1080 @ 60 FPS", "1920×1080 @ 30 FPS", "1280×720 @ 60 FPS", "1280×720 @ 30 FPS"]
    # 高速运动优先 720p60，而不是相近预算的 1080p30。
    if profile == "高速战斗 / 大量粒子":
        order = [0, 1, 3, 2, 4]
    else:
        order = [0, 1, 2, 3, 4]
    for i in order:
        if video_kbps >= limits[i]:
            return options[i], "仅经验估计；动作、纹理、编码器和源素材都会影响清晰度。"
    return "建议剪短或降低到 720p30 以下", "码率预算过低，无法保证画质。"


def make_preset(codec: str, b: Budget, profile: str) -> str:
    c = CODECS[codec]
    rec, warning = recommend(codec, b.video_kbps, profile)
    return (
        "视频上传压缩推荐参数（HandBrake）\n"
        "────────────────────────\n"
        f"原片时长：{format_duration(b.seconds)}（{b.seconds:g} 秒）\n"
        f"上传上限：{b.limit_mb:g} MB；安全目标：{b.target_mb:g} MB（十进制）\n"
        f"编码格式：{codec}\n"
        f"视频编码器：{c['encoder']}\n"
        f"视频码率控制：Average Bitrate（平均码率），不要选 RF/CQ\n"
        f"【视频平均码率】：{b.video_kbps} Kbps\n"
        f"多遍编码：启用 2-Pass / Multi-pass（编码器支持时）\n"
        f"编码器预设：{c['preset']}\n"
        f"画面模式：{profile}\n"
        f"建议分辨率/帧率：{rec}\n"
        f"帧率方式：Constant Framerate；不要超过原片帧率\n"
        f"输出尺寸：不得超过原片实际分辨率；画质预算不足时适当降低\n"
        f"音频：{f'AAC，{b.audio_kbps} Kbps（多音轨按总预算）' if b.audio_kbps else '不保留音轨'}\n"
        f"容器：{c['container']}\n"
        f"字幕 / 多音轨：会占用容量，需增加余量或计入所有音轨\n"
        f"画面处理：不额外锐化、不降噪；缩放时使用高质量滤镜\n"
        f"封装和浮动余量：{b.overhead_pct:g}%\n"
        f"理论文件大小估计：{b.estimated_mb:.1f} MB\n"
        f"编码特点：{c['tip']}\n"
        f"画质提示：{warning}\n"
        "注意：预算只约束平均码率，最终文件大小和清晰度不是硬保证；上传前核对文件。\n"
        "────────────────────────\n"
        "原片建议：1080p60 可用 HEVC 30～40 Mbps 或录制软件恒定质量高画质模式；\n"
        "先保留清晰原片，再制作小体积上传版，避免反复有损转码。"
    )


def find_ffprobe() -> str | None:
    # 打包在 exe 内的 ffprobe.exe、与 exe 同目录的 ffprobe.exe，以及系统 PATH。
    names = ("ffprobe.exe", "ffprobe") if os.name == "nt" else ("ffprobe", "ffprobe.exe")
    locations = [Path(sys.executable).resolve().parent, Path(__file__).resolve().parent]
    if hasattr(sys, "_MEIPASS"):
        locations.insert(0, Path(sys._MEIPASS))
    for folder in locations:
        for name in names:
            p = folder / name
            if p.is_file():
                return str(p)
    return shutil.which("ffprobe")


def _probe_with_ffprobe(path: str, probe: str) -> float | None:
    try:
        cp = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=18, check=False,
            **({"creationflags": 0x08000000} if os.name == "nt" else {}),
        )
        duration = float(cp.stdout.strip())
        if cp.returncode == 0 and math.isfinite(duration) and 0 < duration <= 864000:
            return duration
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _boxes(file, start: int, end: int):
    """遍历 MP4 ISO BMFF box，不读大型 mdat 全量数据。"""
    pos = start
    while pos + 8 <= end:
        file.seek(pos)
        raw = file.read(8)
        if len(raw) != 8:
            break
        size, kind = struct.unpack(">I4s", raw)
        header = 8
        if size == 1:
            extended = file.read(8)
            if len(extended) != 8:
                break
            size = struct.unpack(">Q", extended)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            break
        yield kind, pos + header, pos + size
        pos += size


def _mp4_duration(path: str) -> float | None:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            for kind, begin, end in _boxes(f, 0, filesize):
                if kind != b"moov":
                    continue
                for child, child_begin, child_end in _boxes(f, begin, end):
                    if child != b"mvhd":
                        continue
                    f.seek(child_begin)
                    version = f.read(1)
                    if version == b"\x00":
                        f.seek(child_begin + 12)
                        raw = f.read(8)
                        if len(raw) != 8:
                            continue
                        scale, ticks = struct.unpack(">II", raw)
                    elif version == b"\x01":
                        f.seek(child_begin + 20)
                        raw = f.read(12)
                        if len(raw) != 12:
                            continue
                        scale, ticks = struct.unpack(">IQ", raw)
                    else:
                        continue
                    if scale > 0 and 0 < ticks / scale <= 864000:
                        return ticks / scale
    except (OSError, ValueError, OverflowError, struct.error):
        pass
    return None


def _read_vint(f, *, for_id: bool) -> tuple[int, int] | None:
    start = f.read(1)
    if not start:
        return None
    first = start[0]
    if not first:
        return None
    width = 1
    mask = 0x80
    while not first & mask:
        width += 1
        mask >>= 1
        if width > 8:
            return None
    rest = f.read(width - 1)
    if len(rest) != width - 1:
        return None
    value = int.from_bytes(start + rest, "big")
    if not for_id:
        value &= (1 << (7 * width)) - 1
    return value, width


def _mkv_duration(path: str) -> float | None:
    """读取 Matroska Segment.Info.Duration；Info 未写 Duration 时须依赖 ffprobe。"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            eof = f.tell()
            f.seek(0)
            while f.tell() < eof:
                eid = _read_vint(f, for_id=True)
                sz = _read_vint(f, for_id=False)
                if not eid or not sz:
                    break
                size = sz[0]
                end = min(eof, f.tell() + size)
                if eid[0] == 0x18538067:  # Segment
                    break
                f.seek(end)
            else:
                return None
            if not eid or eid[0] != 0x18538067:
                return None
            segment_end = end if size < (1 << (7 * sz[1])) - 1 else eof
            while f.tell() < segment_end:
                eid = _read_vint(f, for_id=True)
                sz = _read_vint(f, for_id=False)
                if not eid or not sz:
                    break
                end = min(segment_end, f.tell() + sz[0])
                if eid[0] == 0x1549A966:  # Info
                    scale = 1000000
                    ticks = None
                    while f.tell() < end:
                        child_id = _read_vint(f, for_id=True)
                        child_sz = _read_vint(f, for_id=False)
                        if not child_id or not child_sz:
                            break
                        child_end = f.tell() + child_sz[0]
                        if child_end > end:
                            break
                        if child_id[0] == 0x2AD7B1 and 1 <= child_sz[0] <= 8:
                            scale = int.from_bytes(f.read(child_sz[0]), "big")
                        elif child_id[0] == 0x4489 and child_sz[0] in (4, 8):
                            raw = f.read(child_sz[0])
                            ticks = struct.unpack(">f" if child_sz[0] == 4 else ">d", raw)[0]
                        f.seek(child_end)
                    if ticks is not None and scale > 0:
                        duration = ticks * scale / 1e9
                        if math.isfinite(duration) and 0 < duration <= 864000:
                            return duration
                f.seek(end)
    except (OSError, ValueError, OverflowError, struct.error):
        pass
    return None


def detect_duration(path: str) -> tuple[float | None, str]:
    if not os.path.isfile(path):
        return None, "找不到文件"
    probe = find_ffprobe()
    if probe:
        duration = _probe_with_ffprobe(path, probe)
        if duration:
            return duration, "ffprobe"
    ext = Path(path).suffix.lower()
    if ext in (".mp4", ".m4v", ".mov", ".3gp"):
        duration = _mp4_duration(path)
        if duration:
            return duration, "内置 MP4/MOV 解析"
    if ext in (".mkv", ".webm"):
        duration = _mkv_duration(path)
        if duration:
            return duration, "内置 MKV/WebM 解析"
    return None, "无法识别时长；请手动输入或提供 ffprobe.exe"
