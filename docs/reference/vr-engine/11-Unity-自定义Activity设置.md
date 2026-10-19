# 11-Unity-自定义Activity设置

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/configuration-custom-activity-0000001160324976

---

如果开发者所编译的Android应用有自定义的Activity，这时应继承HUAWEI VR Unity SDK的HVRActivity。
说明
HVRActivity定义在Assets\Plugins\Android下的hvrbridge.jar中，继承自UnityPlayerActivity。
在Android工程中进行以下操作：
收起
自动换行
深色代码主题
复制
import com.huawei.vrlab.HVRActivity;
public class MainActivity extends HVRActivity {
……
}
同时在AndroidManifest.xml中将Activity名字修改为开发者自定义的Activity名，且需注意intent-filter必须符合应用程序的AndroidManifest配置的要求。
VRLauncher图标要求
2D界面提示设置
<div _ngcontent-ng-c3413314161="" class="
