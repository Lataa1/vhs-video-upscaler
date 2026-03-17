# VHS Upscaler

A local Windows GUI for restoring and upscaling VHS captures with free tools.

The app wraps a practical restoration pipeline around VapourSynth, QTGMC, FFmpeg, and Real-ESRGAN NCNN Vulkan. It is designed for home-video workflows where the goal is a cleaner, easier-to-watch result rather than fake "true HD" detail.

## Features

- Desktop GUI for the full VHS pipeline
- `PAL` and `NTSC` workflow presets
- QTGMC-based deinterlacing and light cleanup
- Optional AI upscale with multiple model choices
- Single-frame preview rendering for quick model comparison
- Estimated final output resolution shown in the UI
- Auto-detection for local tool paths
- Optional cleanup of intermediate files after success
- Stop button and safe shutdown when the window is closed during a job

## Pipeline

1. Generate a VapourSynth restore script.
2. Render a lossless FFV1 restored master.
3. Split long videos into segments.
4. Run Real-ESRGAN on each segment.
5. Encode and combine the final output.

## Current output geometry

The app exports square-pixel 4:3 output by default.

Typical results:
- `PAL`, deinterlace only: `768x576`
- `PAL`, AI scale `2x`: `1536x1152`
- `NTSC`, deinterlace only: `640x480`
- `NTSC`, AI scale `2x`: `1280x960`

## Repository contents

Main application files:
- [vhs_upscaler_gui.py](./vhs_upscaler_gui.py)
- [launch_vhs_upscaler.bat](./launch_vhs_upscaler.bat)
- [launch_vhs_upscaler.ps1](./launch_vhs_upscaler.ps1)
- [build_exe.ps1](./build_exe.ps1)
- [VHS_UPSCALER_APP_README.md](./VHS_UPSCALER_APP_README.md)

Additional workflow reference:
- [PAL_VHS_HYBRID_WORKFLOW.md](./PAL_VHS_HYBRID_WORKFLOW.md)
- [pal_vhs_qtgmc_restore.vpy](./pal_vhs_qtgmc_restore.vpy)

## Requirements

The repository does not bundle third-party binaries in source control.

You need:
- `ffmpeg.exe`
- `ffprobe.exe`
- `VSPipe.exe`
- VapourSynth plugins required by the generated script
- `realesrgan-ncnn-vulkan.exe`

The app can auto-detect local tool folders if you keep them under a `tools/` folder next to the project, but `tools/` is intentionally ignored in git.

## Launching the app

Recommended:
- [launch_vhs_upscaler.bat](./launch_vhs_upscaler.bat)

Alternative:
- [launch_vhs_upscaler.ps1](./launch_vhs_upscaler.ps1)

The PowerShell launcher correctly handles project paths that contain spaces.

You can also run the GUI directly:

```powershell
py -3.12 .\vhs_upscaler_gui.py
```

## Building the `.exe`

Use:

```powershell
.\build_exe.ps1
```

Note: unsigned `.exe` builds may be blocked by Windows Smart App Control.

## Recommended defaults

For PAL VHS:
- `Video standard`: `PAL`
- `Field order`: `TFF`
- `QTGMC preset`: `Very Slow`
- `Crop`: `4 / 4 / 0 / 8`
- `Segment minutes`: `30`
- `Model`: `realesr-animevideov3`
- `Scale`: `2`
- `Final codec`: `libx264`
- `Final CRF`: `12`

For NTSC VHS:
- `Video standard`: `NTSC`
- `Field order`: start with `TFF`, test `BFF` if motion looks wrong
- `QTGMC preset`: `Very Slow`
- `Scale`: `2`
- `Final codec`: `libx264`
- `Final CRF`: `12`

## AI model notes

Safe default:
- `realesr-animevideov3`

Available test models:
- `remacri-4x`
- `ultramix-balanced-4x`
- `ultrasharp-4x`
- `upscayl-standard-4x`

Some models may look sharper but also more artificial. VHS material benefits from conservative settings.

## Known limitations

- VHS source quality is still the main limiting factor.
- Long tapes can take many hours, especially in the AI stage.
- Intermediate processing can use a large amount of disk space.
- VapourSynth plugin problems will block the restore stage.
- The unsigned `.exe` may be blocked on some Windows systems.

## License

This project is released under the [MIT License](./LICENSE).
