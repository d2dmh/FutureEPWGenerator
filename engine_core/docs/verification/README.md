# Verification evidence (2026-09-13)

Fresh verification performed in the ChatGPT container:

- All eight real TMYx 2009–2023 EPWs passed the offline baseline audit.
- Frozen catalog subset audit: 200 Amon assets + 5 sftlf assets, no duplicate main keys.
- Full case matrix: 288 future EPWs (240 model-specific + 48 ensemble mean).
- Real eight-EPW zero-signal morph/write/reread regression: 8/8 output EPWs passed structural/physical validation; 80 post-serialization factor audit groups were produced.
- Python test suite: 22 passed.
- `compileall`: PASS.

Not verified in this container:

- Live remote CMIP6 Zarr extraction. The container lacks `zarr`, `gcsfs`, and `cftime` and does not provide the same unrestricted network environment as the user's Windows machine. Stage 02 is therefore verified by synthetic/unit tests, cache/retry tests, offline status mode, and code compilation; its live remote run must be performed in the pinned environment from `requirements.txt`.

See `offline_stage_00_02.log`, `real_epw_zero_signal.log`, `tests_and_compile.log`, and `zero_signal_validation/` for evidence.
