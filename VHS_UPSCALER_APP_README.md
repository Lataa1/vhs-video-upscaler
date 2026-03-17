# VHS Upscaler App

This project contains a local desktop GUI for restoring and upscaling VHS captures with free tools.

Main files:
- [vhs_upscaler_gui.py](./vhs_upscaler_gui.py)
- [launch_vhs_upscaler.bat](./launch_vhs_upscaler.bat)
- [launch_vhs_upscaler.ps1](./launch_vhs_upscaler.ps1)
- [build_exe.ps1](./build_exe.ps1)
- `dist/VHSUpscaler.exe`

## What the app does

The app wraps the full VHS pipeline in one interface:

1. Generate a VapourSynth QTGMC restore script.
2. Render a lossless FFV1 restored master.
3. Split long videos into segments for safer AI processing.
4. Run Real-ESRGAN NCNN Vulkan on each segment.
5. Encode and combine the final output video.

The app also supports:
- `PAL` and `NTSC` project presets
- live estimated output resolution display
- preview rendering for model testing
- auto-detection of local tools
- optional cleanup of intermediate files after success
- `Stop Job` support
- automatic process shutdown when the window is closed during a job

## What the app does not include

The wrapper does not embed third-party tools inside the Python source itself. It expects these tools to exist on disk:

- `ffmpeg.exe`
- `ffprobe.exe`
- `VSPipe.exe`
- VapourSynth plugins required by the generated script
- `realesrgan-ncnn-vulkan.exe`

The app can auto-detect a local `tools/` folder next to the project, but `tools/` is usually best kept out of git.

## Getting the tools

The easiest Windows setup is:

1. Download a ready-to-use FFmpeg Windows build and place it under `tools/FFmpeg/`.
2. Install VapourSynth Portable for Windows and make sure `VSPipe.exe` is available.
3. Install the required VapourSynth plugins, either with `vsrepo` or by using a prepared portable setup.
4. Download `realesrgan-ncnn-vulkan` for Windows and place it under `tools/RealESRGAN/`.
5. Start the app and use `Auto-Detect Tools`.

Recommended official starting points:
- FFmpeg downloads page: [ffmpeg.org/download.html](https://www.ffmpeg.org/download.html)
- VapourSynth installation guide: [vapoursynth.com/doc/installation.html](https://www.vapoursynth.com/doc/installation.html)
- Real-ESRGAN NCNN Vulkan releases: [xinntao/Real-ESRGAN-ncnn-vulkan releases](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases)

## Recommended way to launch

Because Windows Smart App Control may block unsigned `.exe` builds, the safest launch method is:

- [launch_vhs_upscaler.bat](./launch_vhs_upscaler.bat)

Alternative launch methods:
- [launch_vhs_upscaler.ps1](./launch_vhs_upscaler.ps1)
- `dist/VHSUpscaler.exe`

The PowerShell launcher correctly handles project paths with spaces and should start the GUI normally.

Command line launch:

```powershell
py -3.12 .\vhs_upscaler_gui.py
```

## Basic workflow

1. Select `Source video`.
2. Select `Output folder`.
3. Check the tool paths on the `Tools` tab, or use `Auto-Detect Tools`.
4. Choose `Video standard`: `PAL` or `NTSC`.
5. Adjust restore and AI settings if needed.
6. Check the estimated final resolution shown in the UI.
7. Use `Render Model Preview` for a fast single-frame comparison.
8. Click `Start Job`.

## Current output geometry

The app converts final output to square pixels for correct 4:3 display.

Typical results:
- `PAL`, deinterlace only: `768x576`
- `PAL`, AI scale `2x`: `1536x1152`
- `NTSC`, deinterlace only: `640x480`
- `NTSC`, AI scale `2x`: `1280x960`

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

## Notes about AI models

Safe default:
- `realesr-animevideov3`

Available test models:
- `remacri-4x`
- `ultramix-balanced-4x`
- `ultrasharp-4x`
- `upscayl-standard-4x`

Not every model works equally well on VHS. Some models may look sharper but also more artificial.

## Preview output

Preview images are saved under:

- `preview/`

For each source, the app creates a subfolder named after the source file stem.

Typical preview files:
- `restored_000050.png`
- `ai_realesr-animevideov3_000050.png`
- `compare_realesr-animevideov3_000050.png`

## Intermediate files

Depending on settings, the app may create:
- restored FFV1 master
- `temp` folder
- `segments` folder
- extracted PNG frames
- upscaled PNG frames

If `Delete intermediates after success` is enabled, the app removes:
- the restored master
- the `temp` folder
- the `segments` folder

If `Keep extracted frames` is enabled but `Delete intermediates after success` is also enabled, cleanup wins and the extracted frames are removed at the end of a successful run.

## Rebuilding the app

Use:

- [build_exe.ps1](./build_exe.ps1)

## Limitations

- VHS source quality is still the main limiting factor.
- Long tapes can take many hours, especially in the AI stage.
- Disk usage can become very large during intermediate processing.
- VapourSynth plugin issues will prevent the restore stage from starting.
- The `.exe` is unsigned and may be blocked by Windows Smart App Control.
