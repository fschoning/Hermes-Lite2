# rawstream: PC tools for the HL2 raw front end

| File | What |
|---|---|
| `rawcap/` | Rust program (Windows): raw stream receiver and checker, duplex and echo sender, aux channel test, and a software radio (`--emulate`) for testing without hardware |
| `noisetest.py` | one-command receiver noise test: quiet capture versus full-rate stream, band by band, with plots |
| `analyse.py` | spectra of captures saved by `rawcap --save` |
| `nic_setup.ps1` | show and set the Windows network card settings for the stream |

Build rawcap:

```
cd rawcap
cargo build --release      # target/release/rawcap.exe
cargo test --release
```

Usage, examples and screenshots: `docs/rawfront/TOOLS.md`. Wire formats: `docs/rawfront/PROTOCOL.md`.
Network card settings: `docs/rawfront/TOOLCHAIN.md`.

All wire-format details of rawcap live in `rawcap/src/protocol.rs`.
