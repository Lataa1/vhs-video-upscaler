import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk


def app_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_runtime_dir()
SCRIPT_DIR = Path(__file__).resolve().parent


def candidate_roots() -> list[Path]:
    roots = [APP_DIR]
    if APP_DIR.parent != APP_DIR:
        roots.append(APP_DIR.parent)
    if SCRIPT_DIR not in roots:
        roots.append(SCRIPT_DIR)
    return roots


def project_root() -> Path:
    for root in candidate_roots():
        if (root / "tools").exists() or (root / "vhs_upscaler_config.json").exists():
            return root
    return APP_DIR


PROJECT_ROOT = project_root()
CONFIG_PATH = PROJECT_ROOT / "vhs_upscaler_config.json"
DEFAULT_UPSCALE_MODEL = "realesr-animevideov3"
SUPPORTED_UPSCALE_MODELS = [
    "realesr-animevideov3",
    "remacri-4x",
    "ultramix-balanced-4x",
    "ultrasharp-4x",
    "upscayl-standard-4x",
]
HELP_TEXTS = {
    "source_path": "Input video file. MKV, MP4, AVI, MOV, MTS, M2TS, TS, MPG, and MPEG are supported.",
    "output_dir": "Destination folder for the final video, restored master, previews, and temporary work files.",
    "video_standard": "Choose the source TV standard. PAL maps to 768x576 at 4:3 square pixels, NTSC maps to 640x480.",
    "ffmpeg_path": "Path to ffmpeg.exe. Used for encoding, segmentation, frame extraction, and image generation.",
    "vspipe_path": "Path to VSPipe.exe. Used to render the VapourSynth restoration script.",
    "realesrgan_path": "Path to realesrgan-ncnn-vulkan.exe. Used for AI frame upscaling.",
    "crop_left": "Masks noise or edge damage on the left side before restoration.",
    "crop_right": "Masks noise or edge damage on the right side before restoration.",
    "crop_top": "Masks noise at the top edge before restoration.",
    "crop_bottom": "Masks bottom-edge VHS noise before restoration, then restores the original frame geometry.",
    "field_order": "Interlaced field order. Most VHS captures are TFF, but some hardware outputs BFF.",
    "qtgmc_preset": "QTGMC quality preset. Slower settings are usually cleaner but take longer.",
    "qtgmc_sharpness": "Extra QTGMC sharpening. Keep this low for VHS to avoid halos and fake edges.",
    "qtgmc_tr2": "Temporal cleanup strength in QTGMC. Higher values can reduce noise in motion but may soften detail.",
    "qtgmc_sourcematch": "How strongly QTGMC tries to recover source detail after deinterlacing.",
    "qtgmc_lossless": "QTGMC lossless reconstruction mode. Usually leave this at 0 for VHS material.",
    "denoise_enabled": "Applies a light denoise pass after deinterlacing. Usually helpful for noisy tapes.",
    "ai_upscale_enabled": "Runs the AI upscale stage after the restored master has been created.",
    "segment_minutes": "Splits long videos into smaller segments before AI processing. Smaller segments are safer for long runs.",
    "upscale_model": "Real-ESRGAN model used for AI upscale. Different models trade off sharpness, stability, and realism.",
    "upscale_scale": "AI upscale factor. For VHS, 2x is usually the safest and most natural choice.",
    "tile_size": "Real-ESRGAN tile size. Lower values use less VRAM and may improve stability on difficult GPUs.",
    "gpu_id": "Vulkan GPU selection. Use auto for the default device, or 0, 1, and so on to force a specific GPU.",
    "jobs": "Real-ESRGAN worker layout in load:process:save format. Lower values are slower but often more stable.",
    "preview_timestamp": "Frame timestamp used by the preview feature, for example 00:01:00.",
    "output_fps": "Legacy UI field. Final AI output follows the detected segment frame rate instead of this value.",
    "final_codec": "Final video codec. libx264 is the safest choice for compatibility. libx265 is smaller but slower.",
    "final_crf": "Final encode quality. Lower values mean higher quality and larger files.",
    "keep_frames": "Keeps extracted and AI-upscaled PNG frames after processing. Useful for debugging, but uses a lot of disk space.",
    "delete_intermediates": "Deletes the restored master, temp folder, and segment data after a successful run, keeping only the final output.",
}

RETRO_BG = "#08110a"
RETRO_PANEL = "#0e1b10"
RETRO_PANEL_ALT = "#132617"
RETRO_FIELD = "#061008"
RETRO_TEXT = "#b7ff9f"
RETRO_TEXT_DIM = "#79cc7d"
RETRO_ACCENT = "#3dff8b"
RETRO_ACCENT_SOFT = "#1d7d44"
RETRO_WARNING = "#ffe66d"
RETRO_FONT_FAMILY = "Cascadia Mono"
RETRO_FONT_FALLBACK = "Consolas"


def first_existing_path(*candidates: Path) -> str:
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def bundled_ffmpeg_path() -> str:
    for root in candidate_roots():
        matches = sorted((root / "tools" / "FFmpeg").glob("*/bin/ffmpeg.exe"))
        if matches:
            return str(matches[0])
    return ""


def bundled_vspipe_path() -> str:
    for root in candidate_roots():
        found = first_existing_path(
            root / "tools" / "VapourSynthPortable" / "VSPipe.exe",
            root / "tools" / "VapourSynth" / "VSPipe.exe",
        )
        if found:
            return found
    return ""


def bundled_realesrgan_path() -> str:
    for root in candidate_roots():
        found = first_existing_path(
            root / "tools" / "RealESRGAN" / "realesrgan-ncnn-vulkan-v0.2.0-windows" / "realesrgan-ncnn-vulkan.exe",
        )
        if found:
            return found
    return ""


@dataclass
class AppConfig:
    source_path: str = ""
    output_dir: str = ""
    ffmpeg_path: str = bundled_ffmpeg_path()
    vspipe_path: str = bundled_vspipe_path()
    realesrgan_path: str = bundled_realesrgan_path()
    video_standard: str = "PAL"
    crop_left: int = 4
    crop_right: int = 4
    crop_top: int = 0
    crop_bottom: int = 8
    field_order: str = "TFF"
    qtgmc_preset: str = "Very Slow"
    qtgmc_sharpness: float = 0.1
    qtgmc_tr2: int = 1
    qtgmc_sourcematch: int = 3
    qtgmc_lossless: int = 0
    denoise_enabled: bool = True
    ai_upscale_enabled: bool = True
    segment_minutes: int = 30
    upscale_model: str = DEFAULT_UPSCALE_MODEL
    upscale_scale: int = 2
    tile_size: int = 0
    gpu_id: str = "auto"
    jobs: str = "2:2:2"
    output_fps: int = 50
    final_codec: str = "libx264"
    final_crf: int = 12
    keep_frames: bool = False
    delete_intermediates: bool = False
    preview_timestamp: str = "00:01:00"


VPY_TEMPLATE = """import vapoursynth as vs
import havsfunc as haf

core = vs.core

clip = core.ffms2.Source(source={source_path!r})
clip = core.std.Crop(
    clip,
    left={crop_left},
    right={crop_right},
    top={crop_top},
    bottom={crop_bottom},
)
clip = core.std.AddBorders(
    clip,
    left={crop_left},
    right={crop_right},
    top={crop_top},
    bottom={crop_bottom},
)
clip = haf.QTGMC(
    clip,
    Preset={qtgmc_preset!r},
    TFF={tff},
    FPSDivisor=1,
    Sharpness={qtgmc_sharpness},
    TR2={qtgmc_tr2},
    SourceMatch={qtgmc_sourcematch},
    Lossless={qtgmc_lossless},
)
{denoise_block}
clip.set_output()
"""


class PipelineCancelled(Exception):
    pass


class PipelineRunner:
    def __init__(self, config: AppConfig, logger, progress, stop_event: threading.Event | None = None):
        self.config = config
        self.log = logger
        self.progress = progress
        self.stop_event = stop_event or threading.Event()
        self._active_processes: set[subprocess.Popen] = set()
        self._process_lock = threading.Lock()

    def stop(self):
        self.stop_event.set()
        with self._process_lock:
            processes = list(self._active_processes)
        for proc in processes:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
        for proc in processes:
            try:
                if proc.poll() is None:
                    proc.wait(timeout=2)
            except Exception:
                try:
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass

    def run(self):
        self._check_cancel()
        ffmpeg = self._resolve_tool(self.config.ffmpeg_path, "ffmpeg.exe")
        ffprobe = self._resolve_ffprobe(ffmpeg)
        vspipe = self._resolve_tool(self.config.vspipe_path, "vspipe.exe")
        realesrgan = None
        if self.config.ai_upscale_enabled:
            realesrgan = self._resolve_tool(
                self.config.realesrgan_path,
                "realesrgan-ncnn-vulkan.exe",
            )

        source_path = Path(self.config.source_path).expanduser().resolve()
        output_dir = Path(self.config.output_dir).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")
        output_dir.mkdir(parents=True, exist_ok=True)

        job_dir = output_dir / source_path.stem
        temp_dir = job_dir / "temp"
        segments_dir = job_dir / "segments"
        temp_dir.mkdir(parents=True, exist_ok=True)
        segments_dir.mkdir(parents=True, exist_ok=True)

        self.progress("Preparing job", 5)
        self.log(f"Source: {source_path}")
        self.log(f"Job dir: {job_dir}")

        script_path = temp_dir / "restore.vpy"
        script_path.write_text(self._build_vpy(str(source_path)), encoding="utf-8")
        self.log(f"Generated VapourSynth script: {script_path}")

        master_height = self._base_output_height()
        master_path = job_dir / f"restored_{master_height}p_master_ffv1.mkv"
        self.progress(f"Rendering {master_height}p master", 15)
        self._render_master(vspipe, ffmpeg, script_path, source_path, master_path)

        if not self.config.ai_upscale_enabled:
            self.progress("Encoding deinterlace-only output", 75)
            width, height = self._estimated_output_resolution(ai_enabled=False)
            final_output = job_dir / f"{source_path.stem}_deinterlace_only_{width}x{height}.mkv"
            self._encode_deinterlace_only(ffmpeg, master_path, final_output)
            self._cleanup_intermediates(job_dir, temp_dir, segments_dir, master_path, final_output)
            self.log("")
            self.log("Pipeline completed.")
            self.log(f"Final output: {final_output}")
            self.progress("Completed", 100)
            return

        self.progress("Splitting into segments", 35)
        segment_paths = self._segment_master(ffmpeg, master_path, segments_dir)
        final_segment_paths = []
        for index, segment_path in enumerate(segment_paths, start=1):
            segment_start = 40 + int(((index - 1) / len(segment_paths)) * 45)
            self.progress(f"Processing segment {index}/{len(segment_paths)}", segment_start)
            self.log(f"Processing segment {index}/{len(segment_paths)}: {segment_path.name}")
            final_segment_paths.append(
                self._process_segment(ffmpeg, ffprobe, realesrgan, segment_path, segments_dir, index, len(segment_paths))
            )

        width, height = self._estimated_output_resolution(ai_enabled=True)
        final_output = job_dir / f"{source_path.stem}_final_{width}x{height}.mkv"
        self.progress("Combining output", 90)
        if len(final_segment_paths) == 1:
            shutil.copy2(final_segment_paths[0], final_output)
            self.log(f"Copied single segment to final output: {final_output}")
        else:
            self._concat_segments(ffmpeg, final_segment_paths, temp_dir / "concat.txt", final_output)

        self._cleanup_intermediates(job_dir, temp_dir, segments_dir, master_path, final_output)
        self.log("")
        self.log("Pipeline completed.")
        self.log(f"Final output: {final_output}")
        self.progress("Completed", 100)

    def run_preview(self):
        self._check_cancel()
        ffmpeg = self._resolve_tool(self.config.ffmpeg_path, "ffmpeg.exe")
        ffprobe = self._resolve_ffprobe(ffmpeg)
        vspipe = self._resolve_tool(self.config.vspipe_path, "vspipe.exe")
        realesrgan = None
        if self.config.ai_upscale_enabled:
            realesrgan = self._resolve_tool(
                self.config.realesrgan_path,
                "realesrgan-ncnn-vulkan.exe",
            )

        source_path = Path(self.config.source_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        preview_dir = PROJECT_ROOT / "preview" / source_path.stem
        temp_dir = preview_dir / "temp"
        preview_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        self.progress("Preparing preview", 5)
        self.log(f"Preview source: {source_path}")
        self.log(f"Preview dir: {preview_dir}")

        script_path = temp_dir / "preview_restore.vpy"
        script_path.write_text(self._build_vpy(str(source_path)), encoding="utf-8")

        script_info = self._probe_script_info(vspipe, script_path)
        target_frame = self._timestamp_to_frame(
            self.config.preview_timestamp,
            script_info["fps"],
            script_info["frames"],
        )
        safe_model_name = self.config.upscale_model.replace(" ", "_")
        restored_png = preview_dir / f"restored_{target_frame:06d}.png"
        ai_png = preview_dir / f"ai_{safe_model_name}_{target_frame:06d}.png"
        compare_png = preview_dir / f"compare_{safe_model_name}_{target_frame:06d}.png"

        self.progress("Rendering preview frame", 25)
        self._render_preview_frame(vspipe, ffmpeg, script_path, target_frame, restored_png)

        if self.config.ai_upscale_enabled:
            self.progress("Upscaling preview frame", 60)
            self._run_preview_upscale(realesrgan, restored_png, ai_png)
            self.progress("Building comparison image", 85)
            self._build_preview_compare(ffmpeg, restored_png, ai_png, compare_png)
            self.log(f"Preview restored: {restored_png}")
            self.log(f"Preview AI: {ai_png}")
            self.log(f"Preview compare: {compare_png}")
        else:
            self.log(f"Preview restored: {restored_png}")

        self.progress("Completed", 100)

    def _resolve_tool(self, configured_path: str, fallback_name: str) -> str:
        self._check_cancel()
        if configured_path:
            tool_path = Path(configured_path).expanduser()
            if tool_path.exists():
                return str(tool_path)
            raise FileNotFoundError(f"Configured tool not found: {tool_path}")

        found = shutil.which(fallback_name)
        if found:
            return found
        raise FileNotFoundError(
            f"Could not find {fallback_name}. Set the executable path in the app."
        )

    def _resolve_ffprobe(self, ffmpeg_path: str) -> str:
        ffmpeg_dir = Path(ffmpeg_path).resolve().parent
        sibling = ffmpeg_dir / "ffprobe.exe"
        if sibling.exists():
            return str(sibling)
        found = shutil.which("ffprobe.exe")
        if found:
            return found
        raise FileNotFoundError("Could not find ffprobe.exe next to ffmpeg.exe or in PATH.")

    def _build_vpy(self, source_path: str) -> str:
        denoise_block = (
            "clip = core.hqdn3d.Hqdn3d(clip, lum_spac=2.0, chrom_spac=2.0, "
            "lum_tmp=3.0, chrom_tmp=3.0)"
            if self.config.denoise_enabled
            else "# Denoise disabled"
        )
        return VPY_TEMPLATE.format(
            source_path=source_path,
            crop_left=self.config.crop_left,
            crop_right=self.config.crop_right,
            crop_top=self.config.crop_top,
            crop_bottom=self.config.crop_bottom,
            qtgmc_preset=self.config.qtgmc_preset,
            tff=self.config.field_order == "TFF",
            qtgmc_sharpness=self.config.qtgmc_sharpness,
            qtgmc_tr2=self.config.qtgmc_tr2,
            qtgmc_sourcematch=self.config.qtgmc_sourcematch,
            qtgmc_lossless=self.config.qtgmc_lossless,
            denoise_block=denoise_block,
        )

    def _render_master(self, vspipe: str, ffmpeg: str, script_path: Path, source_path: Path, master_path: Path):
        self._check_cancel()
        self.log("Rendering FFV1 master with vspipe + ffmpeg...")
        vspipe_cmd = [vspipe, str(script_path), "-", "-c", "y4m"]
        ffmpeg_cmd = [
            ffmpeg,
            "-y",
            "-i",
            "-",
            "-i",
            str(source_path),
            "-map",
            "0:v",
            "-map",
            "1:a?",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-g",
            "1",
            "-c:a",
            "copy",
            str(master_path),
        ]

        vspipe_proc = None
        ffmpeg_proc = None
        ffmpeg_return = None
        vspipe_return = None
        vspipe_stderr = ""
        try:
            vspipe_proc = subprocess.Popen(
                vspipe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **self._popen_kwargs(binary_output=True),
            )
            self._register_process(vspipe_proc)
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=vspipe_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._popen_kwargs(),
            )
            self._register_process(ffmpeg_proc)
            if vspipe_proc.stdout:
                vspipe_proc.stdout.close()

            self._stream_process_output(ffmpeg_proc)
            ffmpeg_return = ffmpeg_proc.wait()
            if vspipe_proc.stderr:
                vspipe_stderr = vspipe_proc.stderr.read().decode("utf-8", errors="replace")
            vspipe_return = vspipe_proc.wait()
        finally:
            if ffmpeg_proc is not None:
                self._unregister_process(ffmpeg_proc)
            if vspipe_proc is not None:
                self._unregister_process(vspipe_proc)

        if vspipe_stderr.strip():
            self.log(vspipe_stderr.strip())
        if self.stop_event.is_set():
            raise PipelineCancelled("Processing stopped by user.")
        if vspipe_return != 0:
            raise RuntimeError(f"vspipe failed with exit code {vspipe_return}")
        if ffmpeg_return != 0:
            raise RuntimeError(f"ffmpeg master render failed with exit code {ffmpeg_return}")

    def _encode_deinterlace_only(self, ffmpeg: str, master_path: Path, final_output: Path):
        self._check_cancel()
        self.log("Encoding deinterlace-only final output...")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(master_path),
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-vf",
            self._square_pixel_filter(),
            "-c:v",
            self.config.final_codec,
            "-preset",
            "slow",
            "-crf",
            str(self.config.final_crf),
            "-pix_fmt",
            "yuv420p10le",
            "-c:a",
            "copy",
            str(final_output),
        ]
        self._run_command(cmd, "ffmpeg encode deinterlace-only")

    def _segment_master(self, ffmpeg: str, master_path: Path, segments_dir: Path):
        self._check_cancel()
        segment_seconds = self.config.segment_minutes * 60
        if segment_seconds <= 0:
            return [master_path]

        self.log(f"Splitting master into {self.config.segment_minutes}-minute segments...")
        for old_segment in segments_dir.glob("part_*.mkv"):
            old_segment.unlink()

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(master_path),
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            str(segment_seconds),
            "-reset_timestamps",
            "1",
            str(segments_dir / "part_%03d.mkv"),
        ]
        self._run_command(cmd, "ffmpeg segment")
        segment_paths = sorted(segments_dir.glob("part_*.mkv"))
        if not segment_paths:
            raise RuntimeError("No segments were created.")
        return segment_paths

    def _process_segment(self, ffmpeg: str, ffprobe: str, realesrgan: str, segment_path: Path, segments_dir: Path, index: int, total_segments: int):
        self._check_cancel()
        segment_root = segments_dir / f"part_{index:03d}"
        frames_dir = segment_root / "frames"
        upscaled_dir = segment_root / "upscaled"
        segment_root.mkdir(parents=True, exist_ok=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
        upscaled_dir.mkdir(parents=True, exist_ok=True)

        self._clear_directory(frames_dir)
        self._clear_directory(upscaled_dir)

        base = 40 + int(((index - 1) / total_segments) * 45)
        self.progress(f"Extracting frames {index}/{total_segments}", min(base + 5, 84))
        self.log(f"Extracting frames for {segment_path.name}...")
        extract_cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(segment_path),
            "-vsync",
            "0",
            str(frames_dir / "frame_%08d.png"),
        ]
        self._run_command(extract_cmd, f"ffmpeg extract {segment_path.name}")

        self.progress(f"Upscaling segment {index}/{total_segments}", min(base + 20, 88))
        self.log(f"Upscaling {segment_path.name} with Real-ESRGAN...")
        upscale_cmd = [
            realesrgan,
            "-i",
            str(frames_dir),
            "-o",
            str(upscaled_dir),
            "-n",
            self.config.upscale_model,
            "-s",
            str(self.config.upscale_scale),
            "-t",
            str(self.config.tile_size),
        ]
        if self.config.gpu_id and self.config.gpu_id.lower() != "auto":
            upscale_cmd.extend(["-g", self.config.gpu_id])
        upscale_cmd.extend([
            "-j",
            self.config.jobs,
            "-v",
        ])
        self._run_command(
            upscale_cmd,
            f"realesrgan {segment_path.name}",
            cwd=str(Path(realesrgan).resolve().parent),
        )

        final_segment_path = segment_root / f"{segment_path.stem}_final.mkv"
        segment_fps = self._probe_fps(ffprobe, segment_path)
        self.progress(f"Encoding segment {index}/{total_segments}", min(base + 35, 89))
        self.log(f"Encoding final segment {segment_path.name}...")
        encode_cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            segment_fps,
            "-i",
            str(upscaled_dir / "frame_%08d.png"),
            "-i",
            str(segment_path),
            "-map",
            "0:v",
            "-map",
            "1:a?",
            "-vf",
            self._square_pixel_filter(),
            "-c:v",
            self.config.final_codec,
            "-preset",
            "slow",
            "-crf",
            str(self.config.final_crf),
            "-pix_fmt",
            "yuv420p10le",
            "-c:a",
            "copy",
            str(final_segment_path),
        ]
        self._run_command(encode_cmd, f"ffmpeg encode {segment_path.name}")

        if not self.config.keep_frames:
            self._clear_directory(frames_dir)
            self._clear_directory(upscaled_dir)

        return final_segment_path

    def _probe_fps(self, ffprobe: str, input_path: Path) -> str:
        self._check_cancel()
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self._popen_kwargs(),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {input_path.name}: {proc.stderr.strip()}")
        rate = proc.stdout.strip()
        if not rate or rate == "0/0":
            raise RuntimeError(f"ffprobe returned invalid frame rate for {input_path.name}")
        if "/" in rate:
            num, den = rate.split("/", 1)
            return f"{float(num) / float(den):.6f}".rstrip("0").rstrip(".")
        return rate

    def _probe_script_info(self, vspipe: str, script_path: Path) -> dict[str, float | int]:
        self._check_cancel()
        proc = subprocess.run(
            [vspipe, "--info", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self._popen_kwargs(),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"vspipe --info failed: {proc.stderr.strip()}")

        info = {}
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip()

        frames = int(info["Frames"])
        fps_text = info["FPS"].split(" ", 1)[0]
        if "/" in fps_text:
            num, den = fps_text.split("/", 1)
            fps = float(num) / float(den)
        else:
            fps = float(fps_text)
        return {"frames": frames, "fps": fps}

    def _timestamp_to_frame(self, timestamp: str, fps: float, frame_count: int) -> int:
        text = timestamp.strip()
        if not text:
            text = "00:01:00"
        parts = text.split(":")
        try:
            if len(parts) == 1:
                total_seconds = float(parts[0])
            elif len(parts) == 2:
                total_seconds = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            else:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"Invalid preview timestamp: {timestamp}") from exc

        frame_index = int(round(total_seconds * fps))
        return max(0, min(frame_index, frame_count - 1))

    def _square_pixel_filter(self) -> str:
        return "scale=trunc((ih*4/3)/2)*2:ih:flags=lanczos,setsar=1"

    def _base_output_height(self) -> int:
        return 576 if self.config.video_standard == "PAL" else 480

    def _estimated_output_resolution(self, ai_enabled: bool | None = None) -> tuple[int, int]:
        if ai_enabled is None:
            ai_enabled = self.config.ai_upscale_enabled
        height = self._base_output_height()
        if ai_enabled:
            height *= max(1, int(self.config.upscale_scale))
        width = int(((height * 4 / 3) // 2) * 2)
        return width, height

    def _render_preview_frame(self, vspipe: str, ffmpeg: str, script_path: Path, frame_index: int, output_png: Path):
        self._check_cancel()
        self.log(f"Rendering preview frame {frame_index}...")
        vspipe_cmd = [
            vspipe,
            "--start",
            str(frame_index),
            "--end",
            str(frame_index),
            str(script_path),
            "-",
            "-c",
            "y4m",
        ]
        ffmpeg_cmd = [
            ffmpeg,
            "-y",
            "-i",
            "-",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(output_png),
        ]

        vspipe_proc = None
        ffmpeg_proc = None
        ffmpeg_return = None
        vspipe_return = None
        vspipe_stderr = ""
        try:
            vspipe_proc = subprocess.Popen(
                vspipe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **self._popen_kwargs(binary_output=True),
            )
            self._register_process(vspipe_proc)
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=vspipe_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._popen_kwargs(),
            )
            self._register_process(ffmpeg_proc)
            if vspipe_proc.stdout:
                vspipe_proc.stdout.close()

            self._stream_process_output(ffmpeg_proc)
            ffmpeg_return = ffmpeg_proc.wait()
            if vspipe_proc.stderr:
                vspipe_stderr = vspipe_proc.stderr.read().decode("utf-8", errors="replace")
            vspipe_return = vspipe_proc.wait()
        finally:
            if ffmpeg_proc is not None:
                self._unregister_process(ffmpeg_proc)
            if vspipe_proc is not None:
                self._unregister_process(vspipe_proc)

        if vspipe_stderr.strip():
            self.log(vspipe_stderr.strip())
        if self.stop_event.is_set():
            raise PipelineCancelled("Processing stopped by user.")
        if vspipe_return != 0:
            raise RuntimeError(f"vspipe preview failed with exit code {vspipe_return}")
        if ffmpeg_return != 0:
            raise RuntimeError(f"ffmpeg preview frame failed with exit code {ffmpeg_return}")

    def _run_preview_upscale(self, realesrgan: str, restored_png: Path, ai_png: Path):
        self._check_cancel()
        cmd = [
            realesrgan,
            "-i",
            str(restored_png),
            "-o",
            str(ai_png),
            "-n",
            self.config.upscale_model,
            "-s",
            str(self.config.upscale_scale),
            "-t",
            str(self.config.tile_size),
        ]
        if self.config.gpu_id and self.config.gpu_id.lower() != "auto":
            cmd.extend(["-g", self.config.gpu_id])
        cmd.extend(["-j", self.config.jobs, "-v"])
        self._run_command(
            cmd,
            f"preview realesrgan {self.config.upscale_model}",
            cwd=str(Path(realesrgan).resolve().parent),
        )

    def _build_preview_compare(self, ffmpeg: str, restored_png: Path, ai_png: Path, compare_png: Path):
        self._check_cancel()
        scale = max(1, int(self.config.upscale_scale))
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(restored_png),
            "-i",
            str(ai_png),
            "-filter_complex",
            f"[0:v]scale=iw*{scale}:ih*{scale}:flags=neighbor[left];[left][1:v]hstack=inputs=2",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(compare_png),
        ]
        self._run_command(cmd, "ffmpeg preview compare")

    def _concat_segments(self, ffmpeg: str, final_segment_paths, concat_path: Path, final_output: Path):
        self._check_cancel()
        self.log("Concatenating final segments...")
        lines = []
        for segment_path in final_segment_paths:
            normalized = segment_path.as_posix().replace("'", "'\\''")
            lines.append(f"file '{normalized}'")
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(final_output),
        ]
        self._run_command(cmd, "ffmpeg concat")

    def _run_command(self, cmd, label: str, cwd: str | None = None):
        self._check_cancel()
        self.log("")
        self.log(f"[run] {label}")
        self.log(" ".join(self._quote(part) for part in cmd))
        env = os.environ.copy()
        for tool_path in (self.config.ffmpeg_path, self.config.vspipe_path, self.config.realesrgan_path):
            if tool_path:
                tool_dir = str(Path(tool_path).resolve().parent)
                env["PATH"] = tool_dir + os.pathsep + env.get("PATH", "")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=cwd,
            **self._popen_kwargs(),
        )
        self._register_process(proc)
        try:
            self._stream_process_output(proc)
            returncode = proc.wait()
        finally:
            self._unregister_process(proc)
        if self.stop_event.is_set():
            raise PipelineCancelled("Processing stopped by user.")
        if returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {returncode}")

    def _stream_process_output(self, proc: subprocess.Popen):
        if not proc.stdout:
            return
        for line in proc.stdout:
            if self.stop_event.is_set():
                break
            line = line.rstrip()
            if line:
                self.log(line)

    def _register_process(self, proc: subprocess.Popen):
        with self._process_lock:
            self._active_processes.add(proc)
        if self.stop_event.is_set():
            self.stop()

    def _unregister_process(self, proc: subprocess.Popen):
        with self._process_lock:
            self._active_processes.discard(proc)

    def _check_cancel(self):
        if self.stop_event.is_set():
            raise PipelineCancelled("Processing stopped by user.")

    def _clear_directory(self, path: Path):
        for child in path.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)

    def _cleanup_intermediates(
        self,
        job_dir: Path,
        temp_dir: Path,
        segments_dir: Path,
        master_path: Path,
        final_output: Path,
    ):
        if not self.config.delete_intermediates:
            return

        self.log("Cleaning up intermediate files...")
        cleanup_targets = [temp_dir, segments_dir]

        try:
            if master_path.exists() and master_path != final_output:
                master_path.unlink()
                self.log(f"Deleted intermediate master: {master_path.name}")

            for target in cleanup_targets:
                if target.exists():
                    shutil.rmtree(target)
                    self.log(f"Deleted folder: {target.name}")

            # Remove known leftover segment files if any were created outside the segments folder.
            for leftover in job_dir.glob("part_*.mkv"):
                if leftover != final_output:
                    leftover.unlink()
                    self.log(f"Deleted leftover segment: {leftover.name}")
        except Exception as exc:
            self.log(f"WARNING: cleanup failed: {exc}")

    @staticmethod
    def _popen_kwargs(binary_output: bool = False):
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
        if binary_output:
            return kwargs
        return kwargs

    @staticmethod
    def _quote(part: str) -> str:
        if " " in part:
            return f'"{part}"'
        return part


class HoverTooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)
        self.widget.bind("<ButtonPress>", self._hide)

    def _show(self, _event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 28
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        self.tip_window.attributes("-topmost", True)

        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            wraplength=320,
            background=RETRO_PANEL,
            foreground=RETRO_TEXT,
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=RETRO_ACCENT,
            highlightcolor=RETRO_ACCENT,
            font=("TkFixedFont", 9),
            padx=10,
            pady=8,
        )
        label.pack()

    def _hide(self, _event=None):
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VHS Upscaler")
        self.root.geometry("1280x920")
        self.root.minsize(1100, 760)
        self.font_family = self._pick_font_family()
        self._configure_theme()

        self.log_queue = queue.Queue()
        self.worker_thread = None
        self.runner_stop_event: threading.Event | None = None
        self.active_runner: PipelineRunner | None = None
        self._close_requested = False
        self.stop_buttons: list[ttk.Button] = []
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.resolution_var = tk.StringVar(value="")

        self.config = self._load_config()
        self.vars = {}
        self._build_ui()
        self._bind_dynamic_updates()
        self._refresh_estimated_output()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._pump_logs()

    def _pick_font_family(self) -> str:
        families = {name.lower() for name in tkfont.families()}
        for candidate in (RETRO_FONT_FAMILY, RETRO_FONT_FALLBACK, "Courier New"):
            if candidate.lower() in families:
                return candidate
        return "TkFixedFont"

    def _configure_theme(self):
        self.root.configure(bg=RETRO_BG)
        self.root.option_add("*Font", (self.font_family, 10))

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=RETRO_BG, foreground=RETRO_TEXT)
        style.configure(
            "TFrame",
            background=RETRO_BG,
        )
        style.configure(
            "TLabel",
            background=RETRO_BG,
            foreground=RETRO_TEXT,
            font=(self.font_family, 10),
        )
        style.configure(
            "TButton",
            background=RETRO_PANEL_ALT,
            foreground=RETRO_TEXT,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            focuscolor=RETRO_ACCENT,
            relief="flat",
            padding=(10, 6),
            font=(self.font_family, 10, "bold"),
        )
        style.map(
            "TButton",
            background=[("active", RETRO_PANEL), ("pressed", RETRO_FIELD)],
            foreground=[("disabled", RETRO_TEXT_DIM), ("active", RETRO_ACCENT)],
            bordercolor=[("active", RETRO_ACCENT)],
        )
        style.configure(
            "Help.TButton",
            background=RETRO_FIELD,
            foreground=RETRO_WARNING,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            focuscolor=RETRO_ACCENT,
            relief="flat",
            padding=(3, 1),
            font=(self.font_family, 9, "bold"),
        )
        style.map(
            "Help.TButton",
            background=[("active", RETRO_PANEL), ("pressed", RETRO_FIELD)],
            foreground=[("active", RETRO_ACCENT)],
            bordercolor=[("active", RETRO_ACCENT)],
        )
        style.configure(
            "TEntry",
            fieldbackground=RETRO_FIELD,
            foreground=RETRO_TEXT,
            insertcolor=RETRO_ACCENT,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            padding=4,
        )
        style.configure(
            "TCombobox",
            fieldbackground=RETRO_FIELD,
            background=RETRO_PANEL_ALT,
            foreground=RETRO_TEXT,
            arrowcolor=RETRO_ACCENT,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", RETRO_FIELD)],
            foreground=[("readonly", RETRO_TEXT)],
            selectbackground=[("readonly", RETRO_PANEL)],
            selectforeground=[("readonly", RETRO_TEXT)],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=RETRO_FIELD,
            foreground=RETRO_TEXT,
            arrowsize=14,
            arrowcolor=RETRO_ACCENT,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            padding=4,
        )
        style.configure(
            "TCheckbutton",
            background=RETRO_BG,
            foreground=RETRO_TEXT,
            font=(self.font_family, 10),
            indicatorbackground=RETRO_FIELD,
            indicatormargin=6,
        )
        style.map(
            "TCheckbutton",
            foreground=[("active", RETRO_ACCENT)],
            indicatorbackground=[("selected", RETRO_ACCENT), ("!selected", RETRO_FIELD)],
        )
        style.configure(
            "TNotebook",
            background=RETRO_BG,
            borderwidth=0,
            tabmargins=(4, 4, 4, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=RETRO_PANEL_ALT,
            foreground=RETRO_TEXT_DIM,
            borderwidth=1,
            padding=(14, 8),
            font=(self.font_family, 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", RETRO_PANEL), ("active", RETRO_PANEL_ALT)],
            foreground=[("selected", RETRO_ACCENT), ("active", RETRO_TEXT)],
        )
        style.configure(
            "TLabelframe",
            background=RETRO_BG,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT_SOFT,
            darkcolor=RETRO_BG,
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=RETRO_BG,
            foreground=RETRO_WARNING,
            font=(self.font_family, 10, "bold"),
        )
        style.configure(
            "Vertical.TScrollbar",
            background=RETRO_PANEL_ALT,
            troughcolor=RETRO_FIELD,
            bordercolor=RETRO_BG,
            arrowcolor=RETRO_ACCENT,
            darkcolor=RETRO_BG,
            lightcolor=RETRO_ACCENT_SOFT,
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=RETRO_FIELD,
            background=RETRO_ACCENT,
            bordercolor=RETRO_ACCENT_SOFT,
            lightcolor=RETRO_ACCENT,
            darkcolor=RETRO_PANEL,
        )

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        pipeline_tab = ttk.Frame(notebook)
        tools_tab = ttk.Frame(notebook)
        log_tab = ttk.Frame(notebook)

        notebook.add(pipeline_tab, text="Pipeline")
        notebook.add(tools_tab, text="Tools")
        notebook.add(log_tab, text="Log")

        self._build_pipeline_tab(self._make_scrollable_tab(pipeline_tab))
        self._build_tools_tab(self._make_scrollable_tab(tools_tab))
        self._build_log_tab(log_tab)

    def _make_scrollable_tab(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            highlightthickness=0,
            background=RETRO_BG,
            bd=0,
        )
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def on_content_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")

        def bind_mousewheel(_event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def unbind_mousewheel(_event):
            canvas.unbind_all("<MouseWheel>")

        content.bind("<Configure>", on_content_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        return content

    def _build_pipeline_tab(self, parent):
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill="both", expand=True)

        self._add_path_row(
            outer,
            "Source video",
            "source_path",
            file_dialog=True,
            row=0,
        )
        self._add_path_row(
            outer,
            "Output folder",
            "output_dir",
            folder_dialog=True,
            row=1,
        )

        actions_top = ttk.Frame(outer)
        actions_top.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions_top, text="Save Settings", command=self.save_config).pack(side="left")
        ttk.Button(actions_top, text="Start Job", command=self.run_pipeline).pack(side="left", padx=(8, 0))
        stop_top = ttk.Button(actions_top, text="Stop Job", command=self.stop_processing, state="disabled")
        stop_top.pack(side="left", padx=(8, 0))
        self.stop_buttons.append(stop_top)
        ttk.Label(
            actions_top,
            text="Input supports .mkv, .mp4, .avi, .mov, .mts, .m2ts, .ts, .mpg, .mpeg",
        ).pack(side="left", padx=(16, 0))

        progress_frame = ttk.Frame(outer)
        progress_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)
        ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(4, 0))

        form = ttk.LabelFrame(outer, text="Video settings", padding=12)
        form.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        outer.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self._add_combobox(form, "Video standard", "video_standard", ["PAL", "NTSC"], 0)
        self._add_spinbox(form, "Crop left", "crop_left", 0, 64, 1)
        self._add_spinbox(form, "Crop right", "crop_right", 0, 64, 2)
        self._add_spinbox(form, "Crop top", "crop_top", 0, 64, 3)
        self._add_spinbox(form, "Crop bottom", "crop_bottom", 0, 64, 4)

        self._add_combobox(form, "Field order", "field_order", ["TFF", "BFF"], 5)
        self._add_combobox(
            form,
            "QTGMC preset",
            "qtgmc_preset",
            ["Slow", "Very Slow", "Slower", "Placebo"],
            6,
        )
        self._add_entry(form, "QTGMC sharpness", "qtgmc_sharpness", 7)
        self._add_spinbox(form, "QTGMC TR2", "qtgmc_tr2", 0, 3, 8)
        self._add_spinbox(form, "SourceMatch", "qtgmc_sourcematch", 0, 3, 9)
        self._add_spinbox(form, "Lossless", "qtgmc_lossless", 0, 2, 10)
        self._add_checkbox(form, "Light denoise", "denoise_enabled", 11)
        self._add_checkbox(form, "Enable AI upscale", "ai_upscale_enabled", 12)
        self._add_spinbox(form, "Segment minutes", "segment_minutes", 0, 180, 13)

        ai_frame = ttk.LabelFrame(outer, text="AI upscale", padding=12)
        ai_frame.grid(row=5, column=0, sticky="nsew", pady=(12, 0))
        ai_frame.columnconfigure(1, weight=1)
        ai_frame.columnconfigure(3, weight=1)

        self._add_combobox(
            ai_frame,
            "Model",
            "upscale_model",
            SUPPORTED_UPSCALE_MODELS,
            0,
        )
        self._add_spinbox(ai_frame, "Scale", "upscale_scale", 2, 4, 1)
        self._add_spinbox(ai_frame, "Tile size", "tile_size", 0, 512, 2)
        self._add_entry(ai_frame, "GPU ID", "gpu_id", 3)
        self._add_entry(ai_frame, "Jobs", "jobs", 4)
        self._add_entry(ai_frame, "Preview time", "preview_timestamp", 5)
        self._add_spinbox(ai_frame, "Output FPS", "output_fps", 25, 60, 6)
        self._add_combobox(ai_frame, "Final codec", "final_codec", ["libx264", "libx265"], 7)
        self._add_spinbox(ai_frame, "Final CRF", "final_crf", 0, 30, 8)
        self._add_checkbox(ai_frame, "Keep extracted frames", "keep_frames", 9)
        self._add_checkbox(ai_frame, "Delete intermediates after success", "delete_intermediates", 10)
        preview_buttons = ttk.Frame(ai_frame)
        preview_buttons.grid(row=11, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(preview_buttons, text="Render Model Preview", command=self.run_preview).pack(side="left")
        ttk.Button(preview_buttons, text="Open Preview Folder", command=self.open_preview_folder).pack(side="left", padx=(8, 0))
        ttk.Label(
            ai_frame,
            textvariable=self.resolution_var,
            justify="left",
        ).grid(row=12, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(
            ai_frame,
            text=(
                "GPU ID: auto uses the default Vulkan device. "
                "On NVIDIA systems you can set 0/1/... to pick a specific GPU.\n"
                "Model advice: realesr-animevideov3 is the safe default. "
                "remacri-4x, ultramix-balanced-4x and ultrasharp-4x are for testing."
            ),
            justify="left",
        ).grid(row=13, column=0, columnspan=4, sticky="w", pady=(8, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Save Settings", command=self.save_config).pack(side="left")
        ttk.Button(actions, text="Start Job", command=self.run_pipeline).pack(side="left", padx=(8, 0))
        stop_bottom = ttk.Button(actions, text="Stop Job", command=self.stop_processing, state="disabled")
        stop_bottom.pack(side="left", padx=(8, 0))
        self.stop_buttons.append(stop_bottom)

    def _build_tools_tab(self, parent):
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill="both", expand=True)

        self._add_path_row(
            outer,
            "ffmpeg.exe",
            "ffmpeg_path",
            file_dialog=True,
            row=0,
        )
        self._add_path_row(
            outer,
            "vspipe.exe",
            "vspipe_path",
            file_dialog=True,
            row=1,
        )
        self._add_path_row(
            outer,
            "realesrgan-ncnn-vulkan.exe",
            "realesrgan_path",
            file_dialog=True,
            row=2,
        )

        buttons = ttk.Frame(outer)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(buttons, text="Auto-Detect Tools", command=self.autodetect_tools).pack(side="left")
        ttk.Button(buttons, text="Save Settings", command=self.save_config).pack(side="left", padx=(8, 0))

        info = (
            "This app does not bundle third-party binaries.\n"
            "Install ffmpeg, VapourSynth with vspipe/havsfunc/ffms2, and Real-ESRGAN NCNN Vulkan,\n"
            "then point the fields below to the correct executables."
        )
        ttk.Label(outer, text=info, justify="left").grid(row=4, column=0, sticky="w", pady=(12, 0))

    def _build_log_tab(self, parent):
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            outer,
            wrap="word",
            bg=RETRO_FIELD,
            fg=RETRO_ACCENT,
            insertbackground=RETRO_ACCENT,
            selectbackground=RETRO_ACCENT_SOFT,
            selectforeground=RETRO_TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            font=(self.font_family, 10),
        )
        self.log_text.pack(fill="both", expand=True)

    def _bind_dynamic_updates(self):
        for key in ("video_standard", "ai_upscale_enabled", "upscale_scale"):
            var = self.vars.get(key)
            if var is not None:
                var.trace_add("write", lambda *_args: self._refresh_estimated_output())

    def _refresh_estimated_output(self):
        standard = str(self.vars.get("video_standard").get() if self.vars.get("video_standard") else self.config.video_standard).upper()
        ai_enabled = bool(self.vars.get("ai_upscale_enabled").get()) if self.vars.get("ai_upscale_enabled") else self.config.ai_upscale_enabled
        scale_var = self.vars.get("upscale_scale")
        try:
            scale = int(scale_var.get()) if scale_var else self.config.upscale_scale
        except (TypeError, ValueError):
            scale = self.config.upscale_scale

        base_height = 576 if standard == "PAL" else 480
        final_height = base_height * max(1, scale) if ai_enabled else base_height
        final_width = int(((final_height * 4 / 3) // 2) * 2)
        mode = "AI upscale" if ai_enabled else "deinterlace only"
        self.resolution_var.set(
            f"Estimated final output: {final_width}x{final_height} ({standard} 4:3, {mode})"
        )

    def _add_help_button(self, parent, label: str, key: str, row: int, column: int):
        button = ttk.Button(
            parent,
            text="?",
            width=3,
            style="Help.TButton",
        )
        button.grid(row=row, column=column, sticky="w", padx=(6, 0), pady=4)
        HoverTooltip(button, HELP_TEXTS.get(key, f"No help text available for {label}."))

    def _add_path_row(self, parent, label, key, row, file_dialog=False, folder_dialog=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        var = tk.StringVar(value=getattr(self.config, key))
        self.vars[key] = var
        entry = ttk.Entry(parent, textvariable=var, width=90)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=4)
        parent.columnconfigure(1, weight=1)
        if file_dialog:
            command = lambda v=var: self._browse_file(v)
        elif folder_dialog:
            command = lambda v=var: self._browse_folder(v)
        else:
            command = None
        if command:
            ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, sticky="e", pady=4)
        self._add_help_button(parent, label, key, row, 3)

    def _add_entry(self, parent, label, key, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        var = tk.StringVar(value=str(getattr(self.config, key)))
        self.vars[key] = var
        ttk.Entry(parent, textvariable=var, width=18).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        self._add_help_button(parent, label, key, row, 2)

    def _add_spinbox(self, parent, label, key, minimum, maximum, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        var = tk.StringVar(value=str(getattr(self.config, key)))
        self.vars[key] = var
        ttk.Spinbox(
            parent,
            from_=minimum,
            to=maximum,
            textvariable=var,
            width=10,
        ).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        self._add_help_button(parent, label, key, row, 2)

    def _add_combobox(self, parent, label, key, values, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        var = tk.StringVar(value=str(getattr(self.config, key)))
        self.vars[key] = var
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=24)
        combo.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=4)
        self._add_help_button(parent, label, key, row, 2)

    def _add_checkbox(self, parent, label, key, row):
        var = tk.BooleanVar(value=bool(getattr(self.config, key)))
        self.vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).grid(row=row, column=0, sticky="w", pady=4)
        self._add_help_button(parent, label, key, row, 1)

    def _browse_file(self, var):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Video files", "*.mkv *.mp4 *.avi *.mov *.mts *.m2ts *.ts *.mpg *.mpeg"),
                ("All files", "*.*"),
            ]
        )
        if path:
            var.set(path)

    def _browse_folder(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _preview_dir_for_current_source(self) -> Path:
        source_text = self.vars.get("source_path")
        if source_text:
            source_value = source_text.get().strip()
            if source_value:
                return PROJECT_ROOT / "preview" / Path(source_value).stem
        return PROJECT_ROOT / "preview"

    def _load_config(self) -> AppConfig:
        defaults = AppConfig()
        if not CONFIG_PATH.exists():
            return defaults
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = asdict(defaults)
            merged.update(raw)
            if not merged.get("ffmpeg_path"):
                merged["ffmpeg_path"] = defaults.ffmpeg_path
            if not merged.get("vspipe_path"):
                merged["vspipe_path"] = defaults.vspipe_path
            if not merged.get("realesrgan_path"):
                merged["realesrgan_path"] = defaults.realesrgan_path
            if not merged.get("output_dir"):
                merged["output_dir"] = str(PROJECT_ROOT / "output")
            if not merged.get("gpu_id"):
                merged["gpu_id"] = "auto"
            if merged.get("upscale_model") in {"realesrgan-x4plus", "realesrgan-x4plus-anime"}:
                merged["upscale_model"] = DEFAULT_UPSCALE_MODEL
            if merged.get("upscale_model") not in SUPPORTED_UPSCALE_MODELS:
                merged["upscale_model"] = DEFAULT_UPSCALE_MODEL
            if not merged.get("preview_timestamp"):
                merged["preview_timestamp"] = "00:01:00"
            return AppConfig(**merged)
        except Exception:
            return defaults

    def _collect_config(self) -> AppConfig:
        try:
            return AppConfig(
                source_path=self.vars["source_path"].get().strip(),
                output_dir=self.vars["output_dir"].get().strip(),
                ffmpeg_path=self.vars["ffmpeg_path"].get().strip(),
                vspipe_path=self.vars["vspipe_path"].get().strip(),
                realesrgan_path=self.vars["realesrgan_path"].get().strip(),
                video_standard=self.vars["video_standard"].get().strip() or "PAL",
                crop_left=int(self.vars["crop_left"].get()),
                crop_right=int(self.vars["crop_right"].get()),
                crop_top=int(self.vars["crop_top"].get()),
                crop_bottom=int(self.vars["crop_bottom"].get()),
                field_order=self.vars["field_order"].get(),
                qtgmc_preset=self.vars["qtgmc_preset"].get(),
                qtgmc_sharpness=float(self.vars["qtgmc_sharpness"].get()),
                qtgmc_tr2=int(self.vars["qtgmc_tr2"].get()),
                qtgmc_sourcematch=int(self.vars["qtgmc_sourcematch"].get()),
                qtgmc_lossless=int(self.vars["qtgmc_lossless"].get()),
                denoise_enabled=bool(self.vars["denoise_enabled"].get()),
                ai_upscale_enabled=bool(self.vars["ai_upscale_enabled"].get()),
                segment_minutes=int(self.vars["segment_minutes"].get()),
                upscale_model=self.vars["upscale_model"].get(),
                upscale_scale=int(self.vars["upscale_scale"].get()),
                tile_size=int(self.vars["tile_size"].get()),
                gpu_id=self.vars["gpu_id"].get().strip() or "auto",
                jobs=self.vars["jobs"].get().strip(),
                preview_timestamp=self.vars["preview_timestamp"].get().strip() or "00:01:00",
                output_fps=int(self.vars["output_fps"].get()),
                final_codec=self.vars["final_codec"].get(),
                final_crf=int(self.vars["final_crf"].get()),
                keep_frames=bool(self.vars["keep_frames"].get()),
                delete_intermediates=bool(self.vars["delete_intermediates"].get()),
            )
        except ValueError as exc:
            raise ValueError(f"Invalid numeric input: {exc}") from exc

    def save_config(self):
        try:
            config = self._collect_config()
            CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
            messagebox.showinfo("Settings Saved", f"Settings saved to {CONFIG_PATH}")
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def autodetect_tools(self):
        detected = {
            "ffmpeg_path": bundled_ffmpeg_path(),
            "vspipe_path": bundled_vspipe_path(),
            "realesrgan_path": bundled_realesrgan_path(),
        }
        for key, value in detected.items():
            if value:
                self.vars[key].set(value)
        found_count = sum(1 for value in detected.values() if value)
        self.status_var.set(f"Detected {found_count}/3 tools")
        self.progress_var.set(0)
        lines = ["Tool auto-detect results:"]
        for key, value in detected.items():
            lines.append(f"{key}: {value or 'NOT FOUND'}")
        for line in lines:
            self._enqueue_log(line)

    def open_preview_folder(self):
        preview_dir = self._preview_dir_for_current_source()
        preview_dir.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(preview_dir))
            else:
                raise RuntimeError("Open folder is only implemented for Windows.")
        except Exception as exc:
            messagebox.showerror("Open Preview Folder Failed", str(exc))

    def _set_running_state(self, running: bool):
        state = "normal" if running else "disabled"
        for button in self.stop_buttons:
            button.configure(state=state)

    def stop_processing(self):
        if not (self.worker_thread and self.worker_thread.is_alive()):
            self.status_var.set("Ready")
            self.progress_var.set(0)
            return

        self.status_var.set("Stopping job")
        self._enqueue_log("")
        self._enqueue_log("Stop requested. Waiting for the active subprocess to exit...")
        if self.runner_stop_event:
            self.runner_stop_event.set()
        if self.active_runner:
            self.active_runner.stop()
        self._set_running_state(False)

    def _on_close(self):
        self._close_requested = True
        if self.worker_thread and self.worker_thread.is_alive():
            self.status_var.set("Stopping before exit")
            self._enqueue_log("")
            self._enqueue_log("Window closed. Stopping the active job before exit...")
            if self.runner_stop_event:
                self.runner_stop_event.set()
            if self.active_runner:
                self.active_runner.stop()
            self._set_running_state(False)
            self.root.after(150, self._finish_close)
            return
        self.root.destroy()

    def _finish_close(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(150, self._finish_close)
            return
        self.root.destroy()

    def run_pipeline(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Job Running", "A job is already running.")
            return

        try:
            config = self._collect_config()
        except Exception as exc:
            messagebox.showerror("Invalid Settings", str(exc))
            return

        if not config.source_path or not config.output_dir:
            messagebox.showerror("Missing Paths", "Set both the source video and the output folder.")
            return

        self.log_text.delete("1.0", "end")
        self.progress_var.set(0)
        self.status_var.set("Starting job")
        self.runner_stop_event = threading.Event()
        self._set_running_state(True)
        self.worker_thread = threading.Thread(
            target=self._run_pipeline_worker,
            args=(config,),
            daemon=True,
        )
        self.worker_thread.start()

    def run_preview(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Job Running", "A job is already running.")
            return

        try:
            config = self._collect_config()
        except Exception as exc:
            messagebox.showerror("Invalid Settings", str(exc))
            return

        if not config.source_path:
            messagebox.showerror("Missing Source", "Set a source video before rendering a preview.")
            return

        self.log_text.delete("1.0", "end")
        self.progress_var.set(0)
        self.status_var.set("Starting preview")
        self.runner_stop_event = threading.Event()
        self._set_running_state(True)
        self.worker_thread = threading.Thread(
            target=self._run_preview_worker,
            args=(config,),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_pipeline_worker(self, config: AppConfig):
        try:
            runner = PipelineRunner(config, self._enqueue_log, self._enqueue_progress, self.runner_stop_event)
            self.active_runner = runner
            runner.run()
        except PipelineCancelled as exc:
            self._enqueue_log("")
            self._enqueue_log(str(exc))
            self._enqueue_progress("Stopped", 0)
        except Exception as exc:
            self._enqueue_log("")
            self._enqueue_log(f"ERROR: {exc}")
            self._enqueue_progress("Error", 0)
        finally:
            self.active_runner = None
            self.runner_stop_event = None
            self.worker_thread = None
            self.log_queue.put(("ui_state", False))

    def _run_preview_worker(self, config: AppConfig):
        try:
            runner = PipelineRunner(config, self._enqueue_log, self._enqueue_progress, self.runner_stop_event)
            self.active_runner = runner
            runner.run_preview()
        except PipelineCancelled as exc:
            self._enqueue_log("")
            self._enqueue_log(str(exc))
            self._enqueue_progress("Stopped", 0)
        except Exception as exc:
            self._enqueue_log("")
            self._enqueue_log(f"ERROR: {exc}")
            self._enqueue_progress("Error", 0)
        finally:
            self.active_runner = None
            self.runner_stop_event = None
            self.worker_thread = None
            self.log_queue.put(("ui_state", False))

    def _enqueue_log(self, message: str):
        self.log_queue.put(message)

    def _enqueue_progress(self, status: str, value: float):
        self.log_queue.put(("progress", status, value))

    def _pump_logs(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple) and len(message) == 3 and message[0] == "progress":
                    _, status, value = message
                    self.status_var.set(status)
                    self.progress_var.set(value)
                elif isinstance(message, tuple) and len(message) == 2 and message[0] == "ui_state":
                    _, running = message
                    self._set_running_state(bool(running))
                    if self._close_requested and not running:
                        self._finish_close()
                else:
                    self.log_text.insert("end", message + "\n")
                    self.log_text.see("end")
        except queue.Empty:
            pass
        self.root.after(100, self._pump_logs)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
