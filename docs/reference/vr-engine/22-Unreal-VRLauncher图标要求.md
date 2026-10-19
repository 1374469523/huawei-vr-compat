# 22-Unreal-VRLauncher图标要求

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-launcher-icon-0000001160009564

---

如果开发者需要在VRLauncher中显示应用图标，则需要按照如下规格设置：
名称：vr_icon.png
大小：200KB以内
格式：png
分辨率：576*324
图标需要存放在Unreal工程目录下，并在APL文件中添加如下语句（也可以直接修改HuaweiVRSDK_APL.xml）：
收起
自动换行
深色代码主题
复制
<copyFile src="$S(PluginDir) /vr_icon.png" dst="$S(BuildDir)/assets/vr_icon.png" />
即只要保证名称为vr_icon.png的图标文件存放在apk的assets目录下即可。
应用程序的AndroidManifest配置
在关卡中添加HuaweiVRCamera
<div _ngcontent-ng-c3413314161="" class="
