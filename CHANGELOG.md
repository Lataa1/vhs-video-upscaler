# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows semantic-style version tags where practical.

## [0.1.0] - 2026-03-17

### Added

- Initial public release of the VHS Upscaler desktop app
- Windows GUI for a VHS restore and upscale workflow
- PAL and NTSC workflow presets
- QTGMC-based deinterlacing and light cleanup
- Real-ESRGAN NCNN Vulkan integration with selectable models
- Single-frame preview rendering for model comparison
- Estimated final output resolution display in the UI
- Auto-detection for local tool paths
- Optional cleanup of intermediate files after successful runs
- Stop button and safe shutdown handling for active jobs
- Batch and PowerShell launchers
- GitHub-ready documentation, screenshot, and release notes

### Notes

- Third-party tools are not bundled in git.
- Unsigned `.exe` builds may be blocked by Windows Smart App Control.

