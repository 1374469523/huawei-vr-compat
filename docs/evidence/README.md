# 取证：眼镜显示与手机显示的对照（2026-09-15）

## 怎么抓眼镜那一路的画面

眼镜是外接显示，逻辑 id 会变，先查名字再抓：

```powershell
adb shell "dumpsys SurfaceFlinger --display-id"        # 找 HUAWEIAV03 那行的 id
adb shell "screencap -p -d <id> /data/local/tmp/glass.png"
```

本机实测可行。早先记录的「VR 层带 handleSkipScreenshotFlag，抓出来是黑图」在当前
配置下不成立，可以正常抓到 3200x1600 的合成结果。

## 三组配置对照

应用把 VR 画面画进**手机显示的逻辑缓冲**，再由系统镜像到眼镜面板。因此
**手机逻辑尺寸的比例决定了眼镜里的画面比例**——面板是 3200x1600（2:1），
每只眼占 1600x1600。

| 手机逻辑尺寸 | 眼镜里的结果 | 证据文件 |
|---|---|---|
| 1320x2640 竖屏 | 画面缩成正中一小块，四周大片黑 | `2026-09-15-glass-logical-1320x2640-portrait.png` |
| 2640x1320 横屏（2.44:1） | 大致铺满，但比例被拉伸，双眼对不齐 | `2026-09-15-glass-logical-2640x1320-landscape.png` |
| 3200x1600（与面板一致，2:1） | 双眼各占面板一半，镜片形状与畸变正常 | `2026-09-15-glass-logical-3200x1600.png` |

同一配置下手机与眼镜的对照（两张应当一致，因为走的是镜像）：
`2026-09-15-phone-logical-3200x1600.png` 与
`2026-09-15-glass-logical-3200x1600.png`。

设置方式（可回退）：

```powershell
adb shell "wm size 1600x3200"                          # 原生向，转横屏后即 3200x1600
adb shell "settings put system accelerometer_rotation 0"
adb shell "settings put system user_rotation 1"        # ROTATION_90
# 回退：adb shell "wm size reset"
```

## 结论

1. 比例不对的根因不是渲染，而是**手机逻辑尺寸与面板比例不一致**，镜像时被非等比
   缩放。把手机逻辑尺寸设成与面板一致（2:1）即可铺满且形状正确。
2. 手机屏与眼镜屏内容一致，说明当前走的是**镜像路径**，不是华为原设计的异步
   直出路径。首版可先用镜像路径验收，异步留待后续。
3. 画面仍与头部锁定。日志里每帧都在报：

   ```
   E VrHelmetExt: mVRDeviceExt is null
   E CtrlCpp: Controller.cpp:getPose(1250): no this controller index(0)
   I Unity_HVRController: Fail to GetPosture. Throw Controller out.
   ```

   `VrHelmetExt.init()` 全程没有被调用过（该方法进入时会打 "init" 日志，日志里没有），
   所以 `mVRDeviceExt` 一直是空，头盔姿态链路没有起来。这是「画面跟着头动」的直接原因。

## 待办

- 找到应当调用 `VrHelmetExt.init()` 的地方（当前只有 `LibUpdate` 用反射把该类交给
  原生层，Java 侧没有调用点），判断是原生库在某个条件下调用、还是需要补一处调用。
- 把「手机逻辑尺寸与面板一致」落进 `ksu/hwvr_compat` 模块，随眼镜在位自动设置、拔除
  恢复，避免每次手工执行。


## 附：当前配置（1600x3200 + 横屏）下的发热

把手机逻辑尺寸对齐到面板 2:1 之后，Unity 在手机上每帧渲染 3200x1600 像素再
镜像到面板，约为手机原生（1080x2640）像素量的 2.2 倍，GPU/SoC 负载明显上升，
机背有可感温升。这是镜像路径的权宜代价——真正的异步路径是让 Unity 直接画到
面板，手机侧不必多刷一份（见 `docs/PORTING_METHOD.md` 第 8 节"未做"清单）。

短期可以靠：
- 把 Unity 的 `Application.targetFrameRate` 限制在 30；
- 减小手机逻辑尺寸但保持 2:1（如 `wm size 960x1920` → 缩到 1/3），代价是
  镜像向上 1.6x、抗锯齿变差。

如果发热先于体验成为问题，优先选 30 fps 限帧。
