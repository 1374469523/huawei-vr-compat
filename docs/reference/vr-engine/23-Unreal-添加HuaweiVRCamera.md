# 23-Unreal-添加HuaweiVRCamera

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-add-camera-0000001160169548

---

将HuaweiVRSDK内容/BluePrints/HuaweiVRCamera蓝图拖入游戏关卡中。
HuaweiVRCamera蓝图中VRCamera的旋转姿态表示VR头盔的旋转姿态，可以通过GeWorldRotation(VRCamera)获取头盔旋转信息。
也可以通过蓝图接口GetHMDOrientationAndPosition直接获取。如果开发者自定义相机蓝图，请将 HuaweiVRCamera中控制弹窗相关的部分加入，不然会导致应用内无弹窗提示信息。
VRLauncher图标要求
手柄适配
<div _ngcontent-ng-c3413314161="" class="
