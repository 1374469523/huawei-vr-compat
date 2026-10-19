# 12-Unity-2D界面提示设置

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/configuration-set-prompt-0000001205644943

---

HUAWEI VR SDK 3.5提供2D界面提示功能，该界面包含在Assets\Plugins\Android\hvrprompt.aar中，会默认打包到应用中。
只有当开发者的应用存在2D Activity，需要从2D Activity动态切换到VR Activity时才应使用该功能。
开发者只需在自己的2D Activity中，使用以下示例代码跳转到该Activity，就会弹出提示界面，插入头盔后就能跳过VrLauncher，直接启动应用自己的VR Activity，如下图所示。
收起
自动换行
深色代码主题
复制
Intent intent = new Intent();
intent.setPackage(getPackageName());
intent.setAction("com.huawei.android.vr.PROMPT");
startActivity(intent);
自定义Activity设置
集成多个相机
<div _ngcontent-ng-c3413314161="" class="
