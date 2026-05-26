# BOOT.md

When OpenClaw starts:

1. Run:

```bash
python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-post-upgrade-self-check.py --print-boot-json
```

2. Read the returned JSON.
3. If `"upgraded": true` (OpenClaw 版本确实变了，这是升级后的第一次启动):
   - **先读取** `docs/通用-OpenClaw-升级记录.md`，了解历史上每次升级出现过什么问题、怎么修的、有什么经验教训
   - 再继续后续步骤
4. Send **exactly** the `bootMessage` field to the last-used main chat route.
5. Also run the boot health check:

```bash
python3 /home/missyouangeled/.openclaw/workspace/scripts/openclaw-boot-health-check.py
```

6. If the health check returns issues (non-empty `issues` array), send the `bootMessage` to the chat as well.
7. After sending all messages, reply with `NO_REPLY`.

Notes:
- The script itself decides whether a real post-upgrade self-check is needed.
- If OpenClaw version did not change, `bootMessage` will just be the normal online message.
- If OpenClaw version changed, the script will proactively read the upgrade checklist and verify the key patch / broker / recovery chain before producing `bootMessage`.
