# `?0x0201xxxx` 不是普通主题属性：EMUI 共享库 `androidhwext` 的属性（2026-09-16）

## 一、现象

`com.huawei.vrservice` 的安装/条款页一进去就崩，进程 `com.huawei.vrinstaller`：

    FATAL EXCEPTION: main  Process: com.huawei.vrinstaller
    Unable to start activity ComponentInfo{com.huawei.vrservice/com.huawei.vrinstaller.activity.ServiceTermActivity}
    Caused by: android.view.InflateException: Binary XML file line #19 in
        com.huawei.vrservice:layout/activity_service_term: Error inflating class android.widget.TextView
    Caused by: java.lang.UnsupportedOperationException:
        Can't convert value at index 2 to dimension: type=0x8
      at android.widget.TextView.readTextAppearance(TextView.java:4712)
      at android.widget.TextView.<init>(TextView.java:...)

去掉眼镜、只在手机上单跑这个页面同样复现，与显示链路无关。

## 二、`0x02` 是什么，为什么 `type=0x8`

布局里那条属性写的是 `android:textSize="?0x020100e9"`。`0x02` 是 **EMUI 的扩展
框架资源包**（`/system/framework/framework-res-hwext.apk`，包名 `androidhwext`，
`aapt2 dump resources -> Package name=androidhwext id=02`）。

它和上一轮修的样式父级（`0x0206xxxx`）是**同一个包的两种用法**：

| 写法 | 编码 | 通用安卓的后果 |
| --- | --- | --- |
| `parent=0x020600cd`（继承 hwext 的样式） | bag 的 parent 字段 | 父级找不到 → 样式退化（只有观感/日志） |
| `?0x020100e9`（引用 hwext 的属性） | `Res_value` 的 `TYPE_DYNAMIC_ATTRIBUTE = 0x8` | 主题里查不到 → **0x8 原样透传** → `getDimension()` 转换失败 → **崩** |

共享库属性编译成 `TYPE_DYNAMIC_ATTRIBUTE`（带包名的属性引用），普通属性是
`TYPE_ATTRIBUTE = 0x2`。EMUI 上 `androidhwext` 作为共享库加载，主题里这些属性
有值，引用就解析成具体尺寸/字体族；通用安卓没有这个包，于是三星的
`TextView.readTextAppearance()` 拿到一个它转不了的 `0x8`。

## 三、这 15 条属性的原厂取值（不是猜的）

HMA-AL00 EMUI 11.0.0.155 整包里取出 `/system/framework/framework-res-hwext.apk`
（21639272 字节，`aapt2 dump resources` 结果 6.1 MB），
`androidhwext:Theme.Emui`（`0x02060008`）里每条属性各指向一个 dimen/string，
再取那些 dimen/string 的**默认配置**值：

| 属性 id | androidhwext 名字 | Theme.Emui 里指向 | 默认值 |
| --- | --- | --- | --- |
| `0x020100c8` | `maxPaddingStart` | `@dimen/emui_dimens_max_start` | 24dp |
| `0x020100ca` | `maxPaddingEnd` | `@dimen/emui_dimens_max_end` | 24dp |
| `0x020100cd` | `defaultPaddingBottomFixed` | `@dimen/emui_dimens_default_bottom_fixed` | 24dp |
| `0x020100da` | `elementsMarginHorizontalL` | `@dimen/emui_dimens_element_horizontal_large` | 16dp |
| `0x020100e8` | `textSizeBody1` | `@dimen/emui_text_size_body1` | 16sp |
| `0x020100e9` | `textSizeBody2` | `@dimen/emui_text_size_body2` | 14sp |
| `0x020100ea` | `textSizeBody3` | `@dimen/emui_text_size_body3` | 12sp |
| `0x020100eb` | `textSizeCaption` | `@dimen/emui_text_size_caption` | 10dp（原厂就是 dp） |
| `0x020100e1` | `textSizeHeadline6` | `@dimen/emui_text_size_headline6` | 30sp |
| `0x020100e2` | `textSizeHeadline7` | `@dimen/emui_text_size_headline7` | 20sp |
| `0x020100e4` | `textSizeSubTitle2` | `@dimen/emui_text_size_subtitle2` | 16sp |
| `0x020100e5` | `textSizeSubTitle3` | `@dimen/emui_text_size_subtitle3` | 14sp |
| `0x020100ef` | `textFontFamilyRegular` | `@string/emui_text_font_family_regular` | `sans-serif` |
| `0x020100f0` | `textFontFamilyMedium` | `@string/emui_text_font_family_medium` | `HwChinese-medium` |
| `0x02010013` | `buttonStyleEmphasize` | `@style/Widget.Emui.Dark.Button.Emphasize` | 见第五节 |

字体族：regular 那个原厂值本来就是 AOSP 的 `sans-serif`；medium 那个是华为自带
字体族名，通用安卓没有这个族（拿它去 `Typeface.create` 会退回常规字重），
语义等价的是 `sans-serif-medium`。

## 四、修法：只把「指向平台包的那一个值」换成平台原本会给的值

`patches/patch_hwext_attr_refs.py`，改的是 `com.huawei.vrservice` 里 7 个
**二进制布局**（该包用 `apktool d -r` 解，`res/` 里是原始 AXML），共 63 处：

| 布局 | 处数 |
| --- | --- |
| `activity_install.xml` | 13 |
| `activity_service_term.xml` | 14 |
| `activity_welcome.xml` | 4 |
| `apk_item.xml` | 1 |
| `fragment_ui_cable_detail_panels.xml` | 18 |
| `layout_permission_item.xml` | 4 |
| `layout_permission_notice.xml` | 9 |

元素、层级、顺序、文案、其它属性（含 AOSP 的 `?0x01010036` 这类）全部不动，
只把 `Res_value` 从 `type=0x8 + 0x020100xx` 换成 `type=0x5`（dimension）或
`type=0x3`（string）。脚本按文件断言处数，改前改后各扫一遍，剩余的非
`buttonStyleEmphasize` 引用一律报错。

## 五、没内联的那一条：`style="?0x02010013"`

`buttonStyleEmphasize` 指向的是**整套样式**（`Widget.Emui.Dark.Button.Emphasize`），
里面两项是

    android:textColor = @color/button_text_emphasize_emui_translucent（状态色选择器）
    android:background = @drawable/btn_emphasize_emui_translucent（九宫格 + 状态选择器，
                          图本身还在 androidhwext 包里）

它不像尺寸那样能内联成一个属性值，而把图搬进本包需要往 `resources.arsc` 里
**新增资源条目**（本包资源表是原样打进包的，apktool 不重建它）。现状：引用解析
不到，按钮走应用主题自己的按钮样式——这正是框架的失败分支，**不伪造背景**。
留 3 处（`activity_install.xml` 2 处、`activity_service_term.xml` 1 处），
台账里单列为待补项，补法是「把 hwext 的九宫格与状态色选择器加进本包资源并
指向本地条目」，不是回退。

## 六、同类扫描（全仓七个包）

新增两个只读工具：

- `tools/axml-ref-scan.py`——扫二进制 AXML 里指向 `0x02` 的属性/引用；
- `tools/arsc-ref-scan.py`——扫 `resources.arsc` 里 bag 的 parent、bag 条目的键、
  以及普通 entry 的 `Res_value`（`@ref` / `?attr` / 动态两种）。

结果：

| 位置 | 命中 |
| --- | --- |
| 七个包的 `res/**/*.xml`（文本） | 0 |
| `com.huawei.vrservice` / `com.huawei.hvrsdkserverapp` 的 `resources.arsc` | 0 |
| `com.huawei.vrservice` 的 7 个二进制布局 | 66（63 已内联，3 为上面的按钮样式） |
| `com.huawei.vrvirtualscreen` 的原包清单 | 2 个 Activity 的主题 `@0x0206002b` |

## 七、顺带查出的丢项：投屏两个对话框的主题没了

`tools/manifest-themes.py`（逐组件对照原包与产物的主题）跑七个包，只有投屏包
出现非预期差异：两个 6DoF 对话框 Activity 原文是

    android:theme="@androidhwext:style/Theme.Emui.Dialog.Alert"   (0x0206002b)

apktool 解不出这个外来包引用，把它写成了 `@null`，重建后进包的也是 `@null`
——主题被丢掉。这不是观感问题：这两个对话框会落到应用默认主题上，不再悬浮。

原厂继承链（三条都 dump 过）：

    Theme.Emui.Dialog.Alert(0x0206002b)
      -> Theme.Emui.Dialog(0x02061010)   windowBackground=@drawable/bg_dialog, windowIsFloating=true
        -> Theme.Emui(0x02060008)
          -> @android:style/Theme.Holo

即 AOSP 一侧的等价物就是它自己的对话框主题
`@android:style/Theme.Holo.Dialog.Alert`。`patches/patch_hwext_dialog_themes.py`
只改这两处 `android:theme`，Activity 名、其它属性不动。

## 八、真机验证（SM-F731U1，`r58`）

| 项 | 结果 |
| --- | --- |
| `ServiceTermActivity`（原崩溃页） | 进程存活，无 `InflateException`；`uiautomator` 层级里能看到「欢迎使用 / 华为 VR 安装向导 / 下载、安装 VR 应用 / 取消 / 同意」 |
| 内联尺寸是否生效 | 按钮栏 `[1218,802]-[1516,1008]`，窗口 `[1146,0]-[1588,1080]`，左右各 72px = 24dp（`maxPaddingStart/End`），两个按钮间距 48px = 16dp（`elementsMarginHorizontalL`），与内联值一致 |
| `WelcomeActivity` / `InstallActivity` / `VRUserPromptActivity` / `VRGlassUpgradeActivity` | 逐个拉起，均无 `InflateException` |
| 投屏 `NoloDialogActivity`（`r58`） | `ActivityTaskManager: Non-opaque activity is created, styleTranslucent=false, floating=true` —— 对话框主题已生效 |

截图与层级文件在 `build/evidence/`（不入库）。

## 九、没做的

- `style="?0x02010013"` 的按钮背景（第五节的待补项）。
- 只在三星 Android 16 上验过；Android 10–15 未验。
- 手柄/视频/桌面三包不涉及这一项（扫描 0 命中），未重跑它们的主线。
