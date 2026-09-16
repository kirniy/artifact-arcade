# Sunset Palms idle-video slot

Production asset name: `sunset-palms-fans.mp4`

This slot accepts only the fan master approved by the Sunset Palms video QA workflow. Do not place a placeholder or substitute here. Adapt the accepted source with:

```bash
scripts/prepare-sunset-palms-idle-video.sh /absolute/path/to/accepted-fan-master.mp4
scripts/prepare-sunset-palms-idle-video.sh --check
```

Required playback contract:

- MP4 container, H.264 video, `yuv420p`
- exactly 128×128 square, square pixels
- constant 24 fps
- no audio stream
- center-safe crop with no letterboxing, UI, or black bars
- clean visual end-to-start loop and fast-start metadata
- final 0.6 seconds fade to black so the player reset joins cleanly to a black opening frame

`scripts/activate-sunset-palms-photobooth.sh` refuses to change the active theme until this exact production asset passes validation.
