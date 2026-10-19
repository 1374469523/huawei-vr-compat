# 21-Unreal-AndroidManifest配置

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-manifest-config-0000001205648055

---

应用程序的AndroidManifest必须符合以下内容：
在application下包含以下meta-data，用来标明应用为华为VR应用。收起
自动换行
深色代码主题
复制
<meta-data android:name="com.huawei.android.vr.application.mode" android:value="vr_only"/>
在application下包含以下meta-data, 为了在Mate10 Pro等特殊比例的屏幕上显示正常。收起
自动换行
深色代码主题
复制
<meta-data android:name="android.max_aspect" android:value="2.1" />
在application下包含以下meta-data，设置应用类型："game"或"video"，默认类型为"game"，SDK会根据类型调整温控策略。收起
自动换行
深色代码主题
复制
<meta-data android:name="com.huawei.android.vr.application.type" android:value="game" />
将VR Activity中的intent-filter修改为以下形式，为了去除桌面图标并让VrLauncher可以跳转。收起
自动换行
深色代码主题
复制
<activity android:name="yourPackage.yourActivity">
<intent-filter>
<action android:name="com.huawei.android.vr.action.MAIN"/>
<category android:name="android.intent.category.DEFAULT"/>
</intent-filter>
</activity>
包含以下权限，用来使用系统VR服务。收起
自动换行
深色代码主题
复制
<uses-permission android:name="com.huawei.android.permission.VR"/>
包含以下权限，用来连接手柄服务。收起
自动换行
深色代码主题
复制
<uses-permission android:name="com.huawei.vrhandle.permission.DEVICE_MANAGER" />
包含以下权限，用来支持截图功能。收起
自动换行
深色代码主题
复制
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
在application下包含以下meta-data，设置应用使用的手柄类型："3dof"或"6dof"或"3dof|6dof"，默认类型为"3dof"，SDK会根据类型调整手柄接入模式。当设置为"3dof|6dof"时，应用同时支持3dof和6dof手柄。收起
自动换行
深色代码主题
复制
<meta-data android:name="com.huawei.vr.application.freeDegree" android:value="3dof|6dof" />
以上内容都可参考Assets\Plugins\Android下默认的AndroidManifest.xml文件。
如果应用的目标平台为 Android 11（API 级别 30）或更高版本，则另外需要在manifest标签下增加如下配置，以可正常支持手柄连接。
收起
自动换行
深色代码主题
复制
<queries>
<package android:name="com.huawei.vrhandle" />
<package android:name="com.huawei.hvrsdkserverapp" />
<intent>
<action android:name="com.huawei.vrhandle.service.vrdeviceservice"/>
</intent>
</queries>
另外，如果开发者需要不连接头盔看到手机上的显示，需要在AndroidManifest的application下包含以下meta-data，但是，正式发布的应用程序中必须去掉该标签，此功能仅用于调试。
收起
自动换行
深色代码主题
复制
<meta-data android:name="com.huawei.android.vr.sensor.mode" android:value="mobile"/>
说明
在Unreal上修改AndroidManifest.xml的方法可参考插件源码目录下的HuaweiVRSDK_APL.xml，开发者也可以直接修改该APL文件，对于已有的语句请勿删除，否则可能会出现未知错误。
集成SDK Unreal插件包
VRLauncher图标要求
<div _ngcontent-ng-c3413314161="" class="
