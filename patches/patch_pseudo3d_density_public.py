"""把 `VRUtils.getPseudo3dNonCompatDensity` 里的 hidden 字段反射换成公开字段。

真机日志（com.huawei.vrservice）：

    E/uawei.vrservice: hiddenapi: Accessing hidden field Landroid/util/DisplayMetrics;->noncompatDensity:F
        (domain=platform ...) using reflection: denied

原版做法：

    DisplayMetrics metrics = getVrDisplayMetrics(context);
    Object value = ReflectUtil.getPrivateField(metrics, "noncompatDensity");
    if (!(value instanceof Float)) { log("noncompatDensityField invalid"); ... }

`noncompatDensity` 是隐藏字段，被平台拒绝 → 永远走 "invalid" 分支。
它的语义是「不做兼容缩放的密度」。而 `getVrDisplayMetrics()` 拿到的是**某块
Display 的** DisplayMetrics（不是应用的兼容资源），它的公开字段 `density`
本来就是非兼容密度，所以这里换成 `metrics.density` 即等价，且是公开 API。

只改这一段；后续 `instanceof Float` / `> 0` 判断和返回值语义全部保留。
"""
import sys
from pathlib import Path

MODULE = "com.huawei.vrservice"
TARGET = "smali/com/huawei/vrservice/utils/VRUtils.smali"
ANCHOR = ('    const-string v2, "noncompatDensity"\n'
          '\n'
          '    invoke-static {p0, v2}, Lcom/huawei/vrservice/utils/ReflectUtil;->'
          'getPrivateField(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;\n'
          '\n'
          '    move-result-object p0')
REPLACEMENT = ('    # 公开字段：从 Display 取得的 DisplayMetrics，其 density 就是非兼容密度\n'
               '    # （见 patches/patch_pseudo3d_density_public.py）\n'
               '    iget v2, p0, Landroid/util/DisplayMetrics;->density:F\n'
               '\n'
               '    invoke-static {v2}, Ljava/lang/Float;->valueOf(F)Ljava/lang/Float;\n'
               '\n'
               '    move-result-object p0')


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if "DisplayMetrics;->density:F" in body:
        raise SystemExit("already patched")
    if body.count(ANCHOR) != 1:
        raise SystemExit("anchor count != 1: %d" % body.count(ANCHOR))

    body = body.replace(ANCHOR, REPLACEMENT, 1)
    if eol != "\n":
        body = body.replace("\n", eol)
    path.write_text(body, encoding="utf-8", newline="")
    print("patched: %s -> DisplayMetrics.density (public)" % TARGET)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
