# 头盔控制通道：/dev/hwvr1 的真实协议（App 侧反汇编 + 原厂系统侧对照）

本文回答三件事：

1. 原厂应用到底是**怎么**跟眼镜说话的（逐条 ioctl，带常量）；
2. 原厂**系统侧**是谁提供了那个节点（EMUI 固件侧对照）；
3. 由此得出，我们要补的是哪一层，以及怎么做到「通用安卓 + 通用 VR 设备」。

结论先放前面：**所谓「华为私有驱动接口」全部是标准 HID
`HIDIOCGFEATURE` / `HIDIOCSFEATURE` 透传**，没有任何华为私有内核 ABI。
EMUI 在系统侧提供的只是一个把眼镜 HID 控制接口暴露成 `/dev/hwvrN` 的传输驱动。
我们要替换的正是这一层，所以这条路天然是通用的 —— 前提是**不写死厂商号/产品号**。

## 一、App 侧：谁在开节点、发了哪几条命令

### 1.1 两个包各自打开 `/dev/hwvr1`

| 位置 | 证据 |
| --- | --- |
| `com.huawei.appmarket.vr` 的 `lib/armeabi-v7a/libvrinfo.so` | `openDevice()` 用 `sprintf_s(buf, 32, "/dev/%s", "hwvr1")` 后 `open(path, O_RDWR)`；失败日志 `open path(%s) failed: fd(%d), errno(%d):%s` |
| `com.huawei.hvrsdkserverapp` 的 `assets/{armeabi-v7a,arm64-v8a}/libWalleDev.so` | 字符串表里有 `hwvr1`、`openDevice success, fd=%d, vendorId=%hd, productId=%hd`；`WalleCommon::openDev()` 打开后把 fd 存进成员 |

两边都**不是**写死厂商号的：`vendorId` / `productId` 是从设备问回来的值，
日志里只是 `%hd` 打印。这正是通用实现应该保持的形态。

### 1.2 `libWalleDev.so` 的完整命令表（`WalleCommon` 类，符号未剥离）

反汇编工具：`工具链/android-sdk/ndk/26.1.10909125/toolchains/llvm/.../llvm-objdump.exe -d -T`
（该库是 Thumb，必须按 thumb 解码，否则反出来是乱的）。

| 功能 | 函数 | ioctl 常量 | 解码 | report id | 传输长度 |
| --- | --- | --- | --- | --- | --- |
| 读厂商号 | `WalleCommon::ioGetVendorInfo()` | `0xC0044807` | `HIDIOCGFEATURE(4)` | `1` | 4 |
| 读眼镜(CV10/Glass)版本 | `WalleCommon::ioGetVersionInfo()` | `0xC03E4807` | `HIDIOCGFEATURE(62)` | `2` | 62 |
| 读 Halliday 版本 | `WalleCommon::IoGetHallidayVersionInfo()` | `0xC0504807` | `HIDIOCGFEATURE(80)` | `2` | 80 |
| 读光学信息 | `WalleCommon::ioGetGlassOpticalInfo()` | `0xC0304807` | `HIDIOCGFEATURE(48)` | `9` | 48 |
| 读显示偏移 | `WalleCommon::ioGetOffsetInfo()` | `0xC0104807` | `HIDIOCGFEATURE(16)` | `9` | 16 |
| 激活设备 | `WalleCommon::ioActiveDev(DEVICE_TYPE)` | `0xC0054806` | `HIDIOCSFEATURE(5)` | `5` | 5 |
| 去激活设备 | `WalleCommon::ioDeactiveDev(DEVICE_TYPE)` | `0xC0054806` | `HIDIOCSFEATURE(5)` | `6` | 5 |

`HIDIOCGFEATURE(len)` 即 `_IOC(_IOC_READ|_IOC_WRITE, 'H', 0x07, len)`，
`HIDIOCSFEATURE(len)` 即同一族的 `0x06`。**两个都是 Linux 标准 HID 接口**。

报文格式（缓冲区首字节是 report id，后面是负载）：

- `ioGetVendorInfo`：`buf[0]=1`，`ioctl(fd, 0xC0044807, buf)`，成功后 `memcpy_s(..., 4, buf, 4)`。
- `ioGetVersionInfo`：`buf[0]=2`，62 字节。
- `IoGetHallidayVersionInfo`：`buf[0]=2`，80 字节；失败时日志
  `ioGethallidayVersionInfo failed, try to get other dev version`。
- `ioGetGlassOpticalInfo`：`buf[0]=9`，48 字节，落到对象偏移 +184。
- `ioGetOffsetInfo`：`buf[0]=9`，16 字节，落到对象偏移 +232。
- `ioActiveDev`：`buf[0]=5`，`buf[1..4]=DEVICE_TYPE & 0x7E`，`HIDIOCSFEATURE(5)`。
- `ioDeactiveDev`：同上，只是 `buf[0]=6`。

有用的日志字符串（便于真机对照）：`active device(%d) OK` / `active device(%d) failed: ret(%d)`、
`helmet version: hwVer = %s, swVer = %s`、`halliday version: hwVer = %s, swVer = %s`。

### 1.3 `libvrinfo.so` 的两处 ioctl（另一条独立实现）

`com.huawei.appmarket.vr` 用 `libvrinfo.so` 的 `VRDeviceInfoUtils.getVRDeviceSN`
拿设备序列号，**整库只有两处 ioctl 调用点**：

| 函数 | ioctl | report id | 长度 |
| --- | --- | --- | --- |
| `ioGetGlassVersion` | `0xC03E4807` = `HIDIOCGFEATURE(62)` | `2` | 62 |
| `ioGetHallidayVersion` | `0xC0504807` = `HIDIOCGFEATURE(80)` | `2` | 80 |

逻辑：先试 Glass(62)，`ret <= 0` 再回落 Halliday(80)。两个缓冲区里各取三处固定偏移的
子串拼成 JSON（`getVRDeviceSN` 的格式串是 `{"sn":"…","hwVer":"…","swVer":"…"}`）：
Glass 缓冲用偏移 `{0x00, 0x08, 0x21}`，Halliday 缓冲用 `{0x00, 0x11, 0x33}`。
真机上拿到的实例值是 `hwVer = CV10AC`、`swVer = 10.0.1.357`。

## 二、原厂系统侧：那个节点是谁做的

### 2.1 EMUI 内核里有一个 HID 传输驱动

对 `系统固件/firmware-vr/emui9-kernel/sec_kernel`（内核镜像）做字符串提取，VR 相关条目是：

```
hwvr
hid_vr
ovr_init - Can't register drive.
ovr_init - Can't allocate chrdev region.
OVR: open(%d) err %d <<<
ovr - pid %d passed too large report
ovr - pid %d passed too short report
ovr - hidraw: pid %d passed too large report
ovr - hidraw: pid %d passed too short report
ovr - parse failed / Couldn't connect / hw start failed
Devices hwvr%d, opens %d, isr_count %u,
%shidraw%d
hwvr.img / firmware updated from hwvr.img / hwvrdfu
```

读法：模块名 `hwvr`、驱动名 `hid_vr`，内部残留 `ovr_*` 与 `ovr - hidraw` 前缀
说明它是从 Oculus 那套 hidraw 驱动改来的；它自己申请字符设备（`Can't allocate
chrdev region`）并创建设备节点 `hwvr%d`，还带固件升级路径（`hwvr.img` / `hwvrdfu`）。

**这个驱动里没有任何协议解析逻辑**：没有厂商号、版本号、偏移量的概念，也没有
`HIDIOCGFEATURE`/`HIDIOCSFEATURE` 之外的通道。它做的就是「把 HID 设备暴露成
`/dev/hwvrN` 并透传 feature report」。

### 2.2 系统侧还有谁在用这个节点

EMUI 的 sensors HAL：`系统固件/firmware-vr/emui9-vendor/lib64/hw/sensors.default.so`
字符串里有字面量 `/dev/hwvr1`、`/dev/%s` + `hwvr1`、`open device %s success`、
以及 `VR device added` / `VR device deleted` / `VR device modified`。
也就是说眼镜的 IMU 是通过同一个节点进 sensor 框架的动态传感器。

### 2.3 系统侧 VR HAL 与这件事无关

`android.hardware.vr@1.0-impl.so`、`vr.kirin980.so`、`hivr.kirin980.so`、
`vendor.huawei.hardware.hivrar@1.1-impl.so` 里**扫不到任何 HIDIOC 常量**，
内容围绕显示与调度（`android::DSSDevice` 的 `setLcdMode` / `setLowPersistence` /
`getVsyncTimeStamp` / `setScene`、`hivr_device_open` / `hivr_device_close`）。
那是 VR 显示/合成那条链，不是头盔控制通道。

## 三、由此得到的判断

1. **要补的层已经确定**：原厂在系统侧提供 `/dev/hwvrN`（HID 传输），
   我们用一个同名节点接同一块 HID 控制接口，就是在替换**同一层**。
   原版库一行不用改，SELinux 也不用放宽容模式。
2. **没有任何华为私有内核 ABI**。全部是 `H` 族 feature report ioctl，
   Linux `hidraw` 本来就有。所以「通用安卓」这条路是成立的。
3. **通用性靠什么保证**：靠**用协议应答挑接口**，不靠写死 VID/PID。
   现有 `ksu/hwvr_compat/hwvr-probe.c` 就是这么做的 —— 它只发
   `HIDIOCGFEATURE(4)`、缓冲区首字节 `1`，**谁按这个协议应答谁就是眼镜的控制接口**，
   注释里也写明了「不写死厂商/产品号，因此换任何 VR 设备都适用」。
   这条设计要保留。
4. **不要把设备相关的量当通用量**：62/80/48/16 字节结构里的字段含义、
   report id 的分配（版本用 2，光学/偏移用 9，激活用 5、去激活用 6）都是
   这台设备（CV10 / Halliday）的约定，属于设备侧协议，不属于传输层。
   做通用实现时这些要按「设备描述」分层，换设备就换这一层。

## 四、复现方式（不留只在对话里的结论）

```powershell
# 1. 列出字符串，定位相关库
node -e "…"   # 或任意 strings 工具；本次用的是自写的可打印字符扫描
# 2. 反汇编（注意：这些库是 Thumb）
llvm-objdump.exe -d -T --start-address=0xff64 --stop-address=0x1012c `
  decode\com.huawei.hvrsdkserverapp\assets\armeabi-v7a\libWalleDev.so
# 3. 扫 ioctl 常量（HIDIOCGFEATURE(len) = 0xC0000000 | (len<<16) | 0x4807）
```

已确认的相关文件：

- `decode/com.huawei.appmarket.vr/lib/armeabi-v7a/libvrinfo.so`（符号未剥离）
- `decode/com.huawei.hvrsdkserverapp/assets/{armeabi-v7a,arm64-v8a}/libWalleDev.so`（符号未剥离）
- `系统固件/firmware-vr/emui9-kernel/sec_kernel`（内核镜像）
- `系统固件/firmware-vr/emui9-vendor/lib{64}/hw/sensors.default.so`
- `系统固件/firmware-vr/emui9-vendor/lib{64}/hw/{android.hardware.vr@1.0-impl.so,vr.kirin980.so,hivr.kirin980.so}`

## 五、仍未确认的部分（不要当已知）

- `ioGetGlassOpticalInfo` 返回的 48 字节里各字段的含义未逐个确认（只知道落点偏移 +184）。
- `ioGetOffsetInfo` 的 16 字节当前由兼容层返回零偏移，是否所有固件版本都接受未验证。
- `device_type`（`DEVICE_TYPE & 0x7E`）各位的含义未逐位确认；只知道激活/去激活用它。
- 内核驱动对**哪些** HID 设备建立节点，其 match 表在镜像里是数值不是字符串，
  没有逐条还原。当前用「协议应答」代替它来选接口。