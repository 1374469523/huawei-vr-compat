# 资源 bag 的 parent 不是重打包丢的：EMUI 的 `androidhwext` 资源包（2026-09-16）

## 现象

真机上从启动起一直刷，各进程都在报同一个 bag：

    E system_server : Failed to find parent 0x020600cd of bag 0x7f100123.
    E ndroid.systemui: Failed to find parent 0x020600cd of bag 0x7f100123.
    E wei.vrlauncherx: Failed to find parent 0x020600cd of bag 0x7f100123.
    E huawei.vrhandle: Failed to find parent 0x020600cd of bag 0x7f1100c3.
    E huawei.vrhandle: Failed to find parent 0x02060189 of bag 0x7f110118.

（`boot.log` / `run1.log` / `run4.log` 里都有。日志里那几个 `…vrservice` 进程不是
vrservice 包自己的资源——`VRPrepareActivity` 这些 Activity 声明在桌面包里，只是
写了 `android:process="com.huawei.vrservice"`，所以打出来的是桌面包的 bag。）

台账里原先记为「重打包后资源 bag 的 parent 丢失」。**这个归因是错的**，
本轮已用原包哈希基准推翻，并定位到真正的边界。

## 一、不是重打包丢的

用 `原包/*.apk`（未改动）和重打包产物各 dump 一次 `resources.arsc`：

    原包 com.huawei.vrlauncherx.apk:
        resource 0x7f100123 style/Theme_NoTitle
          () (style) size=1 parent=0x020600cd

    重打包 com.huawei.vrlauncherx-r37.apk:
        resource 0x7f100123 style/Theme_NoTitle PUBLIC
          () (style) size=1 parent=0x020600cd

父级引用一字不差。重打包没有丢过任何东西，**原包里就是这么写的**。

## 二、`0x02` 是 EMUI 的扩展框架资源包

`0x020600cd` = 资源包 `0x02` / type `0x06` / entry `0xcd`。在 HMA-AL00
EMUI 11.0.0.155 整包固件里，资源包 `0x02` 就是

    /system/framework/framework-res-hwext.apk      21639272 字节
    sha256 683f4d87662f3ea26fec3d0de6a4988c6b2307988742751b7214870ad4cc4a0c
    aapt2 dump resources -> Package name=androidhwext id=02

三条被本项目引用的样式（原文见 `docs/reference/emui-androidhwext-styles.txt`）：

| id | androidhwext 里的名字 | 父级 |
| --- | --- | --- |
| `0x02060008` | `style/Theme.Emui` | `@android:style/Theme.Holo`（AOSP） |
| `0x020600cd` | `style/Theme.Emui.Dark` | `androidhwext:Theme.Emui` |
| `0x02060189` | `style/Theme.Emui.Dark.Emphasize` | `androidhwext:Theme.Emui.Dark` |

也就是说：EMUI 上这几个样式最终坐在 **AOSP 的 `Theme.Holo`** 上，中间那两层
（`Theme.Emui*`）是华为加的。通用安卓手机没有 `androidhwext` 这个包，父级解析
不到，样式就退化成「只剩自己那几条 item」——`Theme_NoTitle` 只剩一条
`windowNoTitle=true`，其余继承全部落空。这正是日志里那一行的含义。

## 三、受影响范围（四个包，逐条 dump 过）

原始包 `原包/*.apk` 里 `parent=0x0206…` 的样式：

| 包 | 样式（资源 id） | 原本的父级 | 谁在用 |
| --- | --- | --- | --- |
| vrlauncherx | `Theme_NoTitle` `0x7f100123` | Theme.Emui.Dark | `MainActivity`（Unity 空间）+ 六个 `com.huawei.client.vrservice.activity.*` 提示/准备页 |
| vrlauncherx | `ThemeBlack` `0x7f100118` / `Theme_Dark_NoTitle` `0x7f100122` | Theme.Emui.Dark.Emphasize | `Vr2dStartUpActivity` / `PrivacyStatementActivity` / `GlassesTipActivity` / `Vr6DofFirmwareUpgradeActivity` |
| vrlauncherx | `AppBaseTheme` `0x7f100005` | Theme.Emui | 无引用（保留同样处理，避免以后再查一遍） |
| vrhandle | `SplashTheme` `0x7f1100c3`、`SubBgTheme` `0x7f1100c4`、`ThemeBlack` `0x7f110118` | Theme.Emui / Theme.Emui.Dark / Theme.Emui.Dark.Emphasize | 手柄模块自身的启动页与页面 |
| vrvirtualscreen | `AppHwTheme` `0x7f0e0006`、`ThemeBlack` `0x7f0e010d` | Theme.Emui / Theme.Emui.Dark.Emphasize | 投屏模块自身页面 |
| vrservice | `Theme_NoTitle` `0x7f0a000c` | Theme.Emui.Dark | vrservice 自己的 `VRPromptActivity` 等（主线第 2 步那个提示） |

`com.huawei.appmarket.vr` / `com.huawei.himovie.vr`：dump 过，**没有**这类父级，
无需处理（它们的 manifest 里只有 `hwc-theme` 那条字符串 meta-data，不是资源引用）。

## 四、修法：只改「指向」

按 `docs/PORTING_METHOD.md` 第 2 节第四步——优先做到「只改指向、不改代码」：
样式名、条目、用它的 Activity 全不动，只把父级换成原厂主题底下那层 AOSP 主题。

| androidhwext 的样式 | 换成 |
| --- | --- |
| `Theme.Emui` | `@android:style/Theme.Holo.Light.NoActionBar` |
| `Theme.Emui.Dark` | `@android:style/Theme.Holo.NoActionBar` |
| `Theme.Emui.Dark.Emphasize` | `@android:style/Theme.Holo.NoActionBar` |

深浅色与原厂一致（`Theme.Emui` 是浅色默认、另外两个是深色）。统一取
`NoActionBar` 变体：这些样式在原包里都不带 AOSP 动作栏（父级解析不到时是一条都
没有的），取带动作栏的变体会凭空多出一条系统动作栏，那是肉眼可见的改变。

两个补丁脚本：

- `patches/patch_emui_theme_parents.py`——改**文本解码树**（launcher / vrhandle /
  vrvirtualscreen 的 `res/values*/styles.xml`）。解码树里 apktool 把父级写成占位名
  `@com.huawei.fakeframework:style/huawei_*`（`tools/framework/2.apk` 就是那张
  name→id 存根表），脚本按表替换并断言处数。
- `patches/patch_arsc_bag_parent.py`——vrservice 是用 `apktool d -r` 解的（资源表有
  重复项，不带 `-r` 解不出来），`res/` 里没有 `values/styles.xml`，父级只存在于
  二进制资源表里。脚本按 chunk 走 `ResTable_type` → entry → `ResTable_map_entry.parent`，
  只改这 4 个字节；改前改后各扫一遍，确认表里不再有指向 `0x02xxxxxx` 的 bag。
  （先核对过：`apktool b` 会把解码树里的 `resources.arsc` 原样打进包，sha256 一致。）

## 五、验证（静态，四包）

构建 `-Revision r38t`：

| 产物 | sha256 |
| --- | --- |
| `com.huawei.vrlauncherx-r38t.apk` | `D7F68CAF1FE99AFA7E5F78C5F2C2826737371609665FD5C36BAC4596A274F1B9` |
| `com.huawei.vrhandle-r38t.apk` | `01E45871D91211708A26B3F563A3319C5157D59B2C77B266FFB82500C12A3336` |
| `com.huawei.vrvirtualscreen-r38t.apk` | `2D10FE073E23E3BEE5AA1B9ECB4EB8A3C627803A73A4E17965E9787AAF09B3A6` |
| `com.huawei.vrservice-r38t.apk` | `69B9695AE07BDC0A670BB9CCC70138CFEC656F839B9915A5ECB17CCE7D16C87C` |

对四个产物各 `aapt2 dump resources`：

- `rg 'parent=0x0206'` **零命中**（改前每个包都有命中）；
- 目标样式已落在 AOSP 主题上，例如

      resource 0x7f100123 style/Theme_NoTitle PUBLIC
        () (style) size=1 parent=0x0103006c        # Theme.Holo.NoActionBar
        0x01010056=true
      resource 0x7f100005 style/AppBaseTheme PUBLIC
        () (style) size=2 parent=0x010300f0        # Theme.Holo.Light.NoActionBar

构建脚本自带的静态核对（包名、组件数、无 INTERNET、无调试开关）四包全过。

## 六、没做的

- **真机验证没做。** 这一轮设备被同一仓库的另一个并行改动占着（它刚装了桌面包 r38
  在验），再装一套会把对方正在看的现场冲掉，所以只做到「构建 + 静态核对」。
  要补的一步：装 `r38t` 四包，确认 `Failed to find parent` 这一行彻底消失，
  并确认 VR 空间与准备/提示页的观感没有变化。
- 这一层是**观感与日志**层面的问题，不是主线卡点：父级解析不到时页面照样起得来
  （主线那几屏现在是通的），所以按优先级它排在主线之后。

## 七、顺带修掉的工具 bug（否则这轮查不出来）

`tools/erofs/erofs-extract.py` 把 `FLAT_INLINE`（dl=2）当成「整个文件内联在 inode
后面」读。实际语义是**前 `size // BLK` 个整块仍在 `i_u` 指向的位置，只有不足一块
的尾部内联**。后果：`/system/framework` 这种超过 4KB 的目录只读到尾巴，
开头几十个文件凭空消失——`framework-res-hwext.apk`、`framework-res.apk` 都在
消失的那一截里，`find`/`extract` 都报「镜像内不存在」。按正确语义拆成
「头部整块 + 内联尾块」后，该目录 203 个文件全部可见，两个资源包都能正常取出。
