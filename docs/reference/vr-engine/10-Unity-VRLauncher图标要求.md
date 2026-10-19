# 10-Unity-VRLauncher图标要求

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/configuration-icon-0000001205764965

---

如果开发者需要在VRLauncher中显示应用图标，则需要按照如下规格设置：
方案1（推荐）：有错层效果
前景图
名称：vr_icon_foreground.png
大小：200KB以内
格式：png
分辨率：576*324
图标的存放路径：Unity3D工程的Assets/StreamingAssets/vr_icon_foreground.png
背景图
名称：vr_icon_background.png
大小：200KB以内
格式：png
分辨率：576*324
图标的存放路径：Unity3D工程的Assets/StreamingAssets/vr_icon_background.png
方案2：无错层效果，兼容老版本，可以与方案1并存
名称：vr_icon.png
大小：200KB以内
格式：png
分辨率：576*324
图标的存放路径：Unity3D工程的Assets/StreamingAssets/vr_icon.png
应用程序的AndroidManifest配置
自定义Activity设置
<div _ngcontent-ng-c3413314161="" class="
