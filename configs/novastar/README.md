# NovaStar Backup Set

This directory is the canonical tracked backup set for the working ARTIFACT 128x128 NovaStar setup.

Last verified:
- March 28, 2026

Known-good recovery note:
- On March 28, 2026, the screen was recovered without reloading mapping.
- The T50 front-panel switch had been pressed accidentally.
- The sender was showing internal stored media instead of live HDMI.
- Do not assume a stored photo on the panel means the receiver mapping is lost.

## Canonical Files

- `working_receiver.rcfgx`
  Receiver-card configuration for the DH418 and module timings.
- `screenmapping.oscfg`
  Screen topology mapping for the 128x128 2x2 layout.
- `screen.scr`
  Screen connection file used by NovaStar tools.
- `FINAL_4hub_128x128.rcfgx`
  Full working project snapshot for the 4-hub 128x128 setup.

## Restore Order

1. Connect to the T50 with NovaLCT or ViPlex.
2. Load `working_receiver.rcfgx` in the Receiving Card tab.
3. Go to Screen Connection and load `screenmapping.oscfg` or use `Open Mapping`.
4. If needed, load `screen.scr`.
5. Click `Send`.
6. Click `Save`.
7. Verify the T50 is using live HDMI, not internal media.
8. Verify the T50 switch is in synchronous / HDMI mode.

## Integrity

See `SHA256SUMS` for checksums of the files in this directory.
