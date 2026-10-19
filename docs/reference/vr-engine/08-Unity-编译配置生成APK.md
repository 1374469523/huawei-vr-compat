# 08-Unity-编译配置生成APK

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/dev-process-build-apk-0000001205446437

---

选择Unity界面中“File > Build Settings...”，在弹出Build Settings对话框中，Platform选择Android。
点击对话框中的Player Settings…，在出现的Inspector页面下，选择Other Settings，勾选Multithreaded Rendering选项。
SDK暂不支持Vulkan，建议勾选GLES3 / Auto Graphics API选项，其中2019版本的Unity的Auto Graphics API选项会自动包含Vulkan，请注意手动勾选GLES3。
在Package Name设置包名，如com.huawei.vrdemo。点击Build Settings对话框中的Build生成APK，或者连接手机再点击Build And Run直接下载到手机运行。
在场景中添加HUAWEI VR手柄
应用程序的AndroidManifest配置
<div _ngcontent-ng-c3413314161="" class="
