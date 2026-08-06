#!/usr/bin/env bash
# 正式位置：scripts/unity-record-ui-effect.sh（原在 tmp/，2026-08-06 转正）
# 录制 Unity UI 火焰动态：连续截帧 -> 回传 -> ffmpeg 合成
#
# 关键约束（2026-08-06 实测）：
# 1. ScreenCapture.CaptureScreenshot 抓不到 ScreenSpaceOverlay 的 UI（只有 3D 场景）
#    -> 必须用 Bridge 的 debug.screenshot（mode=screencapture，走主动渲染）
# 2. hover 状态会被 UI 自身逻辑重置 -> 每帧截图前重新调一次 OnPointerEnter()
# 3. 截图落在 Windows，需 code execute + WebClient 回传到 VM
set -uo pipefail

M="/home/missyouangeled/.openclaw/workspace/tools/unity-mcp-coplay/Server/.venv/bin/unity-mcp --host 127.0.0.1 --port 8080"
BRIDGE="http://localhost:27182/unity/tool"
OUT="/home/missyouangeled/.openclaw/workspace/media/unity"
FRAMES="${1:-24}"

rm -f "$OUT"/seqframe_*.png; mkdir -p "$OUT"

# 每帧：锁 hover -> Bridge 截图 -> 取文件名 -> 回传
for i in $(seq -f "%03g" 1 "$FRAMES"); do
  # 锁住 hover 展开状态
  cat > /tmp/lock_hover.cs <<'CS'
var btn=GameObject.Find("Canvas/Main_Panels/HOME/Content/Button List/CAMPAIGN");
var cu=btn!=null?btn.GetComponent<ChangeUIbim>():null;
if(cu!=null) cu.OnPointerEnter();
var ov=GameObject.Find("Canvas/Main_Panels/HOME/Content/SliderInfo/FX_Fire_Overlay");
var raw=ov!=null?ov.GetComponent<UnityEngine.UI.RawImage>():null;
return "h="+(cu!=null?cu.element.element.sizeDelta.y:-1f)+" uv="+(raw!=null?raw.uvRect.ToString():"null");
CS
  HOV=$(timeout 40 $M code execute --no-safety-checks -f /tmp/lock_hover.cs 2>&1 | grep -oE 'h=[0-9.]+ uv=\([^)]*\)' | head -1)

  SHOT=$(curl -s --max-time 60 -X POST "$BRIDGE" -H "Content-Type: application/json" \
    -d '{"tool":"debug.screenshot","arguments":{}}')
  NAME=$(echo "$SHOT" | python3 -c "import sys,json,os;print(os.path.basename(json.load(sys.stdin)['result']['path'].replace('\\\\','/')))" 2>/dev/null)
  [ -z "$NAME" ] && { echo "  [$i] 截图失败"; continue; }

  cat > /tmp/up_seq.cs <<CS
var p=System.IO.Path.Combine(Application.persistentDataPath,"$NAME");
if(!System.IO.File.Exists(p)) return "NOT FOUND";
var b=System.IO.File.ReadAllBytes(p);
var wc=new System.Net.WebClient(); wc.Headers.Add("X-Name","seqframe_$i.png");
wc.UploadData("http://192.168.79.128:28080/",b);
return "UP "+b.Length;
CS
  RES=$(timeout 60 $M code execute --no-safety-checks -f /tmp/up_seq.cs 2>&1 | grep -oE 'UP [0-9]+' | head -1)
  echo "  [$i] $HOV | $RES"
done

echo "=== 收到的帧 ==="
ls -1 "$OUT"/seqframe_*.png 2>/dev/null | wc -l
