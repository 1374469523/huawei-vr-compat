# 头盔接近（佩戴）与电量：原版要什么、这台眼镜给什么

日期：2026-09-16。设备：SM-F731U1 + HUAWEI VR Glass（`HUAWEIAV03` / HID `12d1:107e`）。

## 0. 结论

**这两个量在这台眼镜上取不到，原因不在兼容层，而在眼镜本身。**

原版读接近/电量用的是 `/dev/hwvr1` 上的 HID 特性报告，两条请求都带具体
report id 与长度（见第 2 节）。真机逐条问过去，眼镜对这两条一律 STALL
（`EPIPE`），对 1 字节的接近请求更是被内核直接以 `EINVAL` 挡下。
眼镜实际只应答三条特性报告：厂商号、版本、显示偏移。

因此本轮**不伪造、不填常量**：接近与电量继续按「无数据源」处理，
即原来那两条 `E/UpgradeGlass: proximity value -1` / `battery info 0, 0, 0`
日志会照旧出现，这是眼镜的真实答复。

## 1. 原版是谁在用这两个量

三个消费方，各自独立：

| 消费方 | 位置 | 用途 |
| --- | --- | --- |
| 桌面（VR 空间） | `t0/c` → 系统服务 `a3.a.v(0x838, …)`（方法名 getProximityState） | 进空间前的「眼镜是否戴上」判断、`helmet away now, wait for proximity msg to start.` |
| Runtime | `com.huawei.vrframework.VrSystemClient$VRStateListener` → `onProximityChanged` → `PhoneController.setProximityStatus`；`VrTouchService$VRStateListener.onProximityChanged` 里做休眠 | 佩戴/摘下时休眠与状态同步 |
| VRServiceX（`com.huawei.vrservice`） | `VRDeviceNodeMonitor.initGlassProximity/initGlassBattery` + `UpgradeGlass.cpp`；`VRService.sendProximityStatus` 广播 `com.huawei.vrservice.vr.vrproximitystatus` | 安装/欢迎页按接近决定何时拉起（`InstallActivity`） |

原厂系统侧还有一处旁证：EMUI 的 `vendor/lib64/hw/sensors.default.so` 里直接
`open("/dev/hwvr1")`，并把节点上的流解析成 `android.sensor.proximity`
（字符串：`proximity`、`android.sensor.proximity`、`proximitg data: %s`、
`heartbeat data: %0x`、`/dev/hwvr1`）。也就是说**接近传感器是眼镜上的真实器件**，
EMUI 由系统把这路数据接进 sensor 框架；通用安卓没有这一层。

## 2. 原版到底发了哪两条请求

从 `com.huawei.vrservice` 的 `lib/arm64-v8a/libvrservice.so`（VRServiceX 自带，
源文件路径串为 `…/VRServiceX/app/src/main/jni/UpgradeGlass.cpp`）反汇编得到：

| 功能 | 函数 | ioctl | 解码 | 缓冲区 |
| --- | --- | --- | --- | --- |
| 读接近 | `IoGetProximityStatus`（`0xb…755c`） | `0xC0014807` | `HIDIOCGFEATURE(1)` | `buf[0] = 4`，取回 1 字节 |
| 读电量 | `IoGetBatteryStatus`（`0x…76d4`） | `0xC0084807` | `HIDIOCGFEATURE(8)` | `buf[0] = 8`，取回 8 字节，按 `短,短,整` 打印 |

两条都走 `open("/dev/hwvr1")`（`0x6908` 处的打开助手从全局 `std::string`
拼 `"/dev/%s"`，该串的静态初始化写的就是 `hwvr1`）。

## 3. 真机实测

工具：`tools/hwvr-report-probe.c`（只发 GET_REPORT）。执行方式见第 6 节。

```text
report  1 len   4 ret   4 errno  0 (Success)      d1 12 7e 10
report  2 len  62 ret  -1 errno 32 (Broken pipe)
report  2 len  80 ret  80 errno  0 (Success)
   43 56 31 30 41 43 00 …  "CV10AC"、"10.0.1.357"、"Jul"、SN 串
report  4 len   1 ret  -1 errno 22 (Invalid argument)   ← 接近
report  8 len   8 ret  -1 errno 32 (Broken pipe)         ← 电量
report  9 len  16 ret  16 errno  0 (Success)     00 00 40 40 00 00 00 c0 00 00 00 c0 00 00 40 40
report  9 len  48 ret  -1 errno 32 (Broken pipe)
```

把 report id 1…9 与长度 1、2、3、4、5、6、7、8、16、20、24、32、40、48、56、
62、64、80、96、127、128 交叉问了一遍（`tools/hidraw-probe.sh reports`），
**只有三条成功**：`1:4`（厂商号，答 `d1 12 7e 10`）、`2:80`（版本串，
答 `CV10AC` / `10.0.1.357`）、`9:16`（显示偏移，答 `3.0, -2.0, -2.0, 3.0`）。
其余全部 STALL；长度 1 的一律 `EINVAL`（通用内核的 hidraw 不接受
「只有 report id、没有负载」的缓冲）。

眼镜自己的 HID 报告描述符（`/sys/class/hidraw/hidraw1/device/report_descriptor`）：

```text
06 ff 00 09 01 a1 01
  85 01 09 07 75 08 95 3b 81 82   Input  id1  59 字节（IMU）
  85 04 09 07 75 08 95 7f b1 82   Feature id4 127 字节（升级通道）
  85 02 09 03 75 08 95 04 81 82   Input  id2   4 字节
  85 06 09 05 75 08 95 14 81 82   Input  id6  20 字节
  85 03 09 01 75 08 95 04 81 82   Input  id3   4 字节
  85 04 09 02 75 08 95 04 81 82   Input  id4   4 字节
c0
```

描述符里**没有** report id 8，也没有 1 字节的 report id 4；这解释了
`EPIPE`（设备 STALL）：请求的报告根本不存在。

另一台 `12d1:1092`（`HUAWEI GLASS CV10`，hidraw0）全程不应答任何特性报告，
25 秒里一条输入报文都没有——它是音频+一个 HID 口的组合设备，不是控制通道。

## 4. 输入流里也没有状态报文

`tools/hwvr-read-dump.c` 在 `/dev/hwvr1` 上连续读 25 秒、4000 个报文：

```text
packets: 4000     分布：01 len=60 ×4000
```

全部是 report id 1 的 IMU 帧（60 字节含 id，约 160 Hz），**没有** 描述符里
的 id 2 / 3 / 4 / 6 状态帧，也没有任何"接近/心跳"记录。
帧内可辨的字段：字节 4–7 是递增计数器，8–11 是时间戳，16–43 是四元数，
44–47 是状态字节，48–59 是三个缓变的浮点（疑似温度）。

## 5. 剩下的两种可能（尚未排除，别当已知）

1. **佩戴事件才上报**。25 秒采集期间没有人戴上/摘下眼镜，所以「状态帧只在
   事件发生时出现」这种可能还没排除。要排除它，需要一次「戴上→摘下」的
   长采集（把 `tools/hidraw-probe.sh … read 60 20000` 挂在后台，人把眼镜
   戴上再摘下）。
2. **厂商专有接口上的 vcom 通道**。`12d1:107e` 除两个 `usbhid` 口外还有
   三个 `class=0xff`（子类 `0x13`）的厂商专有接口，本机**没有任何驱动绑定**。
   原版 `UpgradeGlass.cpp` 里那套 `ttyUSB0/ttyUSB1`（`AT^DEVMODEL?`、`AT^SWVER`、
   `AT^QUERYEXCEPTION`、`AT^SWITCHSCREEN=`，配 `tcgetattr`）在 EMUI 上就是
   挂在这些接口上的；那才是真正的 MCU 串口。要补这一层，需要自己跟这些
   接口说话（或做一层 PTY 桥），本轮没有做，也**没有**证据说接近/电量从
   这条通道来（`IoGetProximityStatus/IoGetBatteryStatus` 反汇编里走的是
   HID 特性报告，不是 vcom）。

补充一条硬事实：这台眼镜回答的是 **Halliday 格式**的版本请求（report 2 × 80 字节），
而 CV10 格式（report 2 × 62）与光学信息（report 9 × 48）都被拒。
带电池的是 Halliday 那一代眼镜，CV10 由手机供电、本身没有电池；
换到别的眼镜型号时应当重新跑这套探测，而不是照搬这里的结论。

## 6. 复现方式

```powershell
# 1) 编译两个诊断工具（arm64，动态链接即可）
$cc = 'D:\Code\华为VR\华为VR_兼容版本\工具链\android-sdk\ndk\26.1.10909125\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android24-clang.cmd'
& $cc -O2 -o build/evidence/hwvr-report-probe tools/hwvr-report-probe.c
& $cc -O2 -o build/evidence/hwvr-read-dump     tools/hwvr-read-dump.c

# 2) 推上去
adb push build/evidence/hwvr-report-probe /data/local/tmp/
adb push build/evidence/hwvr-read-dump     /data/local/tmp/
adb push tools/hidraw-probe.sh             /data/local/tmp/

# 3) 逐条问特性报告 / 看输入流（脚本内部临时改标签，跑完恢复）
adb shell su -c "sh /data/local/tmp/hidraw-probe.sh /dev/hwvr1 reports 1:4 2:62 2:80 4:1 8:8 9:16 9:48"
adb shell su -c "sh /data/local/tmp/hidraw-probe.sh /dev/hwvr1 read 25 4000"

# 4) 眼镜自己的报告描述符
adb shell su -c "od -An -tx1 -v /sys/class/hidraw/hidraw1/device/report_descriptor"
```

## 7. 对当前兼容层的影响

- 桌面问的 `0x838`（getProximityState）现在由
  `SystemServiceBinder` 回 0（=不在近处）。**不改**：没有真实来源时不编值；
  真机上空间仍能正常进入（空间启动由 `0x3eb` 头盔-戴上那条消息驱动，
  与接近查询是两条独立路径）。
- `VirtualScreen`/Runtime 的 `onProximityChanged` 这条回调同样没有来源，
  保持不触发。
- 眼镜的「接近」在 EMUI 上由系统 sensor HAL 提供；通用安卓要补，
  得先解决第 5 节那两条未排除项，属于后续项，不是本轮的"差一行代码"。
