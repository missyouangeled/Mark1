# BOOT.md

When OpenClaw starts:

1. Run:

```bash
python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-post-upgrade-self-check.py --print-boot-json
```

2. Read the returned JSON.
3. Send **exactly** the `bootMessage` field to the last-used main chat route.
4. Also run the boot health check:

```bash
python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-boot-health-check.py
```

5. If the health check returns issues (non-empty `issues` array), send the `bootMessage` to the chat as well.
6. After sending all messages, reply with `NO_REPLY`.

Notes:
- The script itself decides whether a real post-upgrade self-check is needed.
- If OpenClaw version did not change, `bootMessage` will just be the normal online message.
- If OpenClaw version changed, the script will proactively read the upgrade checklist and verify the key patch / broker / recovery chain before producing `bootMessage`.
