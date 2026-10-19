# 35-开发者FAQ

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/faq-0000001097358506

---

如果您在下面没有找到需要的问题，请加入Stack Overflow社区参与讨论。
在其他非华为手机上是否可以使用SDK 3.5？
不可以，SDK 3.5是基于华为手机开发的SDK，在华为手机系统层做了很多优化，开发者需选用华为手机进行开发。
是否可以在任意型号华为手机使用SDK 3.5？
不可以，SDK 3.5是基于华为头盔和相应型号的华为手机开发的SDK，请在指定型号的华为手机开发，参见开发指南。
对Unity开发平台版本是否有限制？
建议使用Unity5.6.0 - 2018.2的LTS版本的平台开发。
手机不连接头盔，是否可以运行HUAWEI VR应用？
可以，请按照以下两种方式配置：
方法一：若开发者的手机是Root过的，通过下面命令打开：adb shell setprop hvr.imm.mobile enable；
方法二：在AndroidManifest的application下包含meta-data 即可。但是，正式发布的应用程序中必须去掉该标签，此功能仅用于调试。
注意：使用手机调试，需要通过点击应用图标启动应用，修改AndroidManifest.xml的配置项如下，将应用图标显示到手机桌面：
收起
自动换行
深色代码主题
复制
<intent-filter>
<action android:name="android.intent.action.MAIN"/>
<category android:name="android.intent.category.LAUNCHER"/>
</intent-filter>
正式发布的应用中必须按照默认配置，去除桌面图标。
开发者开发的应用除了通过华为VRLauncher界面跳转启动，还有别的启动方式吗？
有，请按照以下两种方式执行：
方法一：可以通过命令：adb shell am start -n 应用包名/com.huawei.vrlab.HVRModeActivity，进入2D提示界面，再将手机连接头盔即可进入该应用。
方法二：若开发者的应用中包含2D Activity，请参见2D界面提示设置描述，直接启动自己VR Activity。
为什么集成了华为VR SDK后编译的VR应用没有手机桌面图标？
因为华为VR应用不支持在手机上运行，避免用户点击应用图标后出现闪退现象，无法理解，所以默认设置隐藏桌面图标。
但是，如果开发者需要在手机上调试，可以通过修改AndroidManifest.xml文件，将应用图标显示到手机桌面：
收起
自动换行
深色代码主题
复制
<intent-filter>
<action android:name="android.intent.action.MAIN"/>
<category android:name="android.intent.category.LAUNCHER"/>
</intent-filter>
更新hvrsdk-3.5.x.unitypackage时需要更新华为VR服务APK吗？
需要，需要安装与hvrsdk-3.5.x.unitypackage配套的华为VR服务APK：hvrsdk-server-3.5.x.apk至手机。
手柄无法连接是什么原因？
确定手柄电池安装正确。
确定手柄服务APK是否已经安装运行并与手柄正常配对。
使用Demo确认手柄运行是否正常。
适配SDK 3.5，只需要集成hvrsdk-3.5.x.unitypackage发布应用到手机上即可运行吗？
不行，需要确保手机上安装了华为VR SDK服务APK：hvrsdk-server-3.5.x.apk才行。
开发者如果需要在相机组件下绑定物体该怎么做？
SDK 3.5有开放左右及中心相机变换组件，开发者需要以代码的形式动态绑定，请参见 m_LeftCamObj 示例代码。
开发者在Unity2018.3及以上版本，出现画面卡顿现象，或频繁出现以下报错，该如何解决？E Unity : OPENGL NATIVE PLUG-IN ERROR: GL_INVALID_FRAMEBUFFER_OPERATION: Framebuffer is not complete or incompatible with command
将“Player Setting > Resolution Scaling > Blit Type”选项从“Always”切换为“Never”，尝试解决。
为什么应用的启动画面旋转方向不对？
由于Huawei VR Glass的屏幕方向旋转了导致的，所以开发者不能用伪3D图片加载应用的启动画面，如：不能用Splash Image加载应用的启动画面，在Unity中通过设置：Player Settings -> Splash Image -> 取消勾选“Show Splash Screen”。
开发者适配过SDK 2.0，更新SDK 3.5时需要注意些什么？
SDK 3.5中删除了HVRSafeMode预制件，且SafeMode相关的接口也删除了，如果场景中包含SDK 2.0的Demo，编译时会有关于SafeMode的报错，请删除相关代码片段即可。
SDK 3.5提供了手柄统一预制件，若开发者使用了SDK 2.0 Demo中的手柄预制件，导入SDK 3.5后，会存在脚本重复的报错，请删除SDKDemo/Scripts/Interactive中的重复脚本文件，使用SDK 3.5的手柄预制件。
SDK 2.0 Demo中碰撞检测的侦听接口类HvrEventListner，在SDK 3.5中随手柄预制件重新提供，类名更新为HVREventListener，包含的接口更全面，请开发者同步更新。
当 AndroidManifest.xml 中 "com.huawei.vr.application.freeDegree" 项设置为 "3dof|6dof" 时，应用支持3dof手柄，也支持6dof手柄，开发者如何才能知道当前用户使用的手柄类型呢？
开发者需先获取到IController手柄对象，当手柄可用时，可通过 GetControllerType() 获取手柄类型，然后进行判断。示例如下：
收起
自动换行
深色代码主题
复制
IController controller;
if (controller != null && controller.IsAvailable())
{
if (controller.GetControllerType() == ControllerType.Controller6DOF)
{
// 6dof手柄
}
else if (controller.GetControllerType() == ControllerType.Controller3DOF)
{
// 3dof手柄
}
else
{
// 其他类型手柄
}
}
应用上传规范
支持的国家/地区
<div _ngcontent-ng-c3413314161="" class="
