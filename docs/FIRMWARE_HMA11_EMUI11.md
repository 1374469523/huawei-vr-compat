# HMA-AL00 EMUI 11 整包固件分析：缺件 `com.huawei.vrservice` 已找到

> 整包与解包结果现在统一放在仓库目录下的 `系统固件/`（不入库，见该目录的
> `README.md` 清单）。本文里出现的整包名字，都指 `系统固件/<同名目录>`。

日期：2026-09-15。本轮**没有改动任何原版代码**，只做固件取证。
结论先行：**缺件链的最后一环（第 20/22 节那个找不到的第七个包）在这一版固件里就有，
已完整提取并入库为 `原包/com.huawei.vrservice.apk`。**

## 一、手上这两包固件是什么

| 目录 | 机型 | 版本 | 说明 |
| --- | --- | --- | --- |
| `Firmware_Huawei_HMA-AL00_EmotionUI_11.0.0.155(C00E139R3P6)_full_azurekiln` | HMA-AL00（Mate 20） | EMUI 11.0.0.155 / Android 10 | **本轮重点**，全量包 |
| `LYA-AL00C 9.0.0.107(C00E107R1P16)_Firmware_9.0.0_r3_EMUI9.0 V100R001_05015GLF` | LYA-AL00（Mate 20 Pro） | EMUI 9.0.0.107 | 早于 VR Glass 上市（2019-12），本轮未展开 |

EMUI 11 包的结构（逐层）：

```
update_full_base.zip
  └─ UPDATE.APP (5.55 GB)        华为自家容器
       ├─ 若干裸镜像（xloader / modem / kernel / version / preload ...）
       └─ 71.super.img (稀疏镜像, 展开后 7.81 GB)
            └─ LP 元数据（Android 动态分区 super）
                 ├─ system     3760 MB  ← EROFS + LZ4
                 ├─ hw_product 1984 MB  ← EROFS + LZ4   ★ 目标在这里
                 ├─ cust        192 MB
                 ├─ vendor     1230 MB
                 └─ odm
```

判定依据：`super.img` 的 LP 几何在 `0x1000`（magic `0x616c4467`），元数据头在 `0x3000`
（magic `0x414c5030`，header_size=128，tables 紧随其后）；各逻辑分区超级块在各自镜像
`0x400` 处，magic `0xE0F5E1E2`（EROFS），`feature_incompat = 0x1`（LZ4_0padding）。

## 二、工具链（已入库，可复现）

Windows 上的 7-Zip 26 能认 ext4 / squashfs / LP，但**不认 EROFS**，所以 EMUI 10/11
的镜像以前一直取不出来。本轮补上了：

- `tools/erofs/erofs-extract.py` —— 纯 Python 的 EROFS 只读提取器
  - 支持 FLAT_PLAIN / FLAT_INLINE / **COMPRESSED_FULL / COMPRESSED_COMPACT + LZ4**
  - 自带 LZ4 块解码（不依赖 python-lz4），实现了 EROFS 的 “0padding” 语义
    （每个物理簇数据前导补零要先跳过）与紧凑索引的 4B/2B 两种打包
  - 用法：
    ```
    python tools/erofs/erofs-extract.py find    <image.img> <关键字>
    python tools/erofs/erofs-extract.py list    <image.img> [目录]
    python tools/erofs/erofs-extract.py extract <image.img> <镜像内路径> <输出文件>
    ```

提取步骤（本轮实际执行）：

1. `7z x update_full_base.zip UPDATE.APP`
2. 按稀疏镜像头把 `UPDATE.APP` 里的 super 展开（块偏移 `0xec33050`，561 个 chunk，
   输出 7,809,794,048 字节）
3. 解析 LP 元数据得到 5 个逻辑分区，按 extent 切出 `system.img` / `hw_product.img` 等
4. 用上面的工具在分区镜像里遍历/导出文件

## 三、核心发现：`com.huawei.vrservice` 就在这里

```
/hw_product/region_comm/china/app/VRServiceX/VRServiceX.apk
    包名    com.huawei.vrservice
    版本    11.0.0.322 (versionCode 110000322)
    大小    3,042,010 字节（101 个文件，CRC 全通过）
    label   Huawei VR Service
    附带    lib/arm64-v8a/libvrservice.so (112,560 字节)
```

用 `aapt2 dump badging` 与 `aapt2 dump xmltree` 核过，它**正好提供第 20/22 节
逐条推断出来的那些组件**：

| 之前推断“缺的” | 这个包里实际有的 |
| --- | --- |
| `com.huawei.vrinstaller.service.VrParamsInitializeService` | ✔ 同名 service（`permission=com.huawei.vrservice.VRSystemApp`） |
| `com.huawei.vrinstaller.service.VrParamsProviderService` | ✔ 同名 service |
| `ISysServiceInterface`（混淆为 `a3.a`）的实现方 | ✔ 由本包承担 |
| `com.huawei.vrservice.CLIENT_SERVICE` 权限 | ✔ 本包 `<permission>` 定义 |
| `com.huawei.vrservice.permission.VR` | ✔ 本包 `<permission>` 定义 |
| `com.huawei.vrservice.VRSystemApp` | ✔ 本包 `<permission>` 定义（signature 级） |

除上述之外，包里还有与本移植主线直接相关的组件：

- `com.huawei.vrservice.VRService`（service）、`UsbReceiver`（receiver）
- `com.huawei.vrservice.VRSysAppRequestService`（service，要求 `VRSystemApp` 权限）
- **`com.huawei.vrservice.activity.VRPromptActivity` / `VRUserPromptActivity`**
  —— 这就是“插入眼镜后手机上弹的那一步确认/提示”
- `VrSoLoadFailActivity` / `VRGlassUpgradeActivity` / `VRGlassWarningActivity` /
  `VRUpgradePromptActivity`
- `com.huawei.vrinstaller.activity.WelcomeActivity` / `InstallActivity` /
  `ServiceTermActivity`

## 四、同一版固件里其他与 VR 有关的文件

`system.img`（EROFS，非 APK）：

| 路径 | 大小 | 说明 |
| --- | --- | --- |
| `/system/framework/hwPartVr.jar` | 24,691 | VR 平台类（EMUI “part jar”），已可解出 |
| `/system/framework/hwPartVrService.jar` | 22 | **空占位**（EMUI 把实现搬到了别处） |
| `/system/framework/vr.jar` | 200 | 空占位（只有一个 MANIFEST.MF） |
| `/system/framework/vr.vdex` / `oat/{arm,arm64}/vr.odex` | 4,396 / 21 KB | 预编译产物 |
| `/system/etc/permissions/android.software.vr.xml` | 826 | `android.software.vr.mode` **被注释掉了** |
| `/system/etc/init/hivrarserver.rc` | 237 | hivrar（AR）服务启动脚本 |
| `/system/lib64/vendor.huawei.hardware.hivrar@1.0/2.0/2.1/2.2.so` | 100 KB – 492 KB | AR/HIDL 侧 |
| `/system/usr/idc/AVRCP.idc`、`/system/usr/keylayout/AVRCP.kl` | 634 / 811 | 蓝牙 AVRCP 输入映射 |

`hw_product` 的 `/region_comm/china/app/` 下共 19 个区域预装应用，其中 VR/XR 相关：

- `VRServiceX`（就是本文的主角）
- `XRKit`
- `HuaweiAREngine`

全量 APK 清单（system 248 个 + hw_product 137 个）见
`docs/reference/hma11-apk-inventory.txt`。

## 五、这份固件解开的与没解开的

**解开的**

1. 第七个包确实存在，不是我们推断错了；它就在区域预装目录里。
2. 它自带“插入眼镜后的手机侧提示”Activity，与主线的第 2 步对得上。
3. `com.huawei.vrservice.CLIENT_SERVICE` / `.permission.VR` / `.VRSystemApp`
   这几个权限都由它定义，和桌面包、手柄包里引用到的名字完全一致。

**没解开的 / 新的约束**

1. 它是**系统签名级**应用：`huawei.android.permission.HW_SIGNATURE_OR_SYSTEM`、
   自定义 `signature` 权限。直接装到三星机器上不会以系统身份运行——
   要么重签名+改权限，要么只取它的实现思路。这是新一轮的“系统层替换”工作，
   与前面六个包的处理原则一致：**接口不动，实现换成通用安卓**。
2. 本包为 EMUI 11 版（11.0.0.322）；用户手上六个包里有的是 EMUI 10/11 混版，
   版本要对齐需要再核对。
3. LYA-AL00C（EMUI 9）那包还没展开——它早于 VR Glass，预期不含该组件，
   本包暂按“未分析”记录。

## 六、已定方案（A）与落地情况

2026-09-15 用户选定 **A**：把 `com.huawei.vrservice` 当作第七个模块纳入移植，
按与另外六个包相同的口径处理（保留原包名/组件/流程，替换系统签名与平台依赖），
并收回 `vr_system` 上那层「本地自答」。

已完成的落地（详见 `docs/PATCH_AUDIT.md` 第 25 节）：

- 解码树入 `decode/com.huawei.vrservice/`（资源表有重复项，用 `apktool d -r`）；
- 新增 `patches/patch_vrservice_manifest.py`：去掉 system UID、去掉四条在线权限、
  摘掉两个在线组件、补 `<queries>`、并声明 `com.huawei.vrservice.CLIENT_SERVICE`
  （通用安卓上这个权限原本没人定义，会导致绑定桌面服务被拒）；
- 接入 `build/build-all.ps1` 与 `install-six.ps1`（含 `WRITE_SETTINGS` appop 与
  deviceidle 白名单）；
- 构建产物 `build/out/com.huawei.vrservice-r3.apk`，静态核对通过
  （包名一致、16 个原组件全在、无 INTERNET）。

后续进展：用户裁定**禁止兜底**，本地那份自答的 `vr_system` 实现已整块删除，改为
跨进程转发（registry provider 由本包托管），查不到真服务就返回 `null`。
详见 `docs/PATCH_AUDIT.md` 第 26 节。仍未完成的是真机验证。
