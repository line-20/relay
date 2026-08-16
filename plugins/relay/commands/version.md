---
description: Print the Relay version and banner — a CLI-style --version. Confirms which plugin version is actually loaded.
argument-hint: "(no arguments)"
---

Print Relay's version. Your **entire reply is just the banner below, verbatim, inside a fenced code
block** (monospace keeps it aligned) — no preamble, no explanation, no tool calls, nothing else:

```
 ____      _
|  _ \ ___| | __ _ _   _
| |_) / _ \ |/ _` | | | |
|  _ <  __/ | (_| | |_| |
|_| \_\___|_|\__,_|\__, |
                   |___/
  continuity-first SSDLC workbench                         v1.12.0
  by Line20 · @eriklenaerts
  update: /plugin marketplace update line-20 · then reload the window
```

The version is **hardcoded in this banner on purpose** — it certifies which command file is loaded.
There's no runtime read (`${CLAUDE_PLUGIN_ROOT}` doesn't expand in command bash), so if this shows an
older number than you expect, the session is running a **cached** command and needs a reload.
**Maintainers: bump this version on every release** — mirror `plugin.json`; `/init`'s banner
carries the same string and must move with it.
