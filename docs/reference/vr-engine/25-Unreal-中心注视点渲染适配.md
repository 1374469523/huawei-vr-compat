# 25-Unreal-中心注视点渲染适配

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-render-config-0000001205449549

---

中心注视点渲染保证中心区域清晰度高于边缘区域，在插件中设置如下：
将HuaweiVRSDK内容/BluePrints/HuaweiVRCamera蓝图拖入游戏关卡中。
选中HuaweiVRCamera，在Auto Possess Player，设置Player 0。
在Project Settings-Platforms-Android设置OpenGL ES支持类型，选中OpenGL ES 3.1。
在Project Settings-Engine-Rendering-Mobile，去掉HDR勾选，在VR项，勾选Mobile Multi-View，Mobile Multi-View Direct。
更改图像渲染分辨率，分辨率有三种选择720*720，1080*1080，1280*1280，具体在void FHuaweiVRSDK::SetRenderSize(int width, int height)进行设置。
手柄适配
其他接口说明
<div _ngcontent-ng-c3413314161="" class="
