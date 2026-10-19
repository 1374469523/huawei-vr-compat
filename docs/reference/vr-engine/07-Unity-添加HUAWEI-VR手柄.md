# 07-Unity-添加HUAWEI-VR手柄

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/dev-process-add-controller-0000001160166438

---

添加VR相机后，需要添加HUAWEI VR手柄预制件，即将Assets/HVRController/Prefabs目录下的HVRController、HVREventSystem拖到场景中。
HVRController预制件
手柄射线碰撞检测功能：
带碰撞器的物体，默认可响应碰撞检测。
若UI上未添加碰撞器，如BoxCollider， 则在UI所在的Canvas上，取消勾选原来的Graphic Raycaster脚本，绑定HVRGraphicRaycaster.cs脚本，并将LineRender拖拽绑定至RayObject，即可响应碰撞检测，若使用双手柄交互，需绑定HVRLeftGraphicRaycaster.cs脚本。
开发者可以参见API说明文档介绍，实现监听碰撞检测功能。
手柄按键信息提示功能，开发者可以参见API说明文档介绍，自定义提示信息。
3dof手柄模拟6dof功能，开发者可以参见API说明文档节介绍， 自定义手柄初始位置，及肘距。
手柄按键特殊说明
若要获取手柄按键的长按、短按事件，可参见示例代码Assets\HVR\Scripts\HVRControllerUtils.cs中的实现。
手柄默认快捷键
展开
动作
按键
按键时间
功能
单击
主页键Home
<1s
进入VRLauncher界面
长按
主页键Home
>=1s
视点重置
长按
返回键
>=3s
进入VRLauncher界面
同时按下
主页键Home & 扳机键
<1s
截图
注1：开发者如需自定义快捷键，请避免与上述快捷键组合冲突。
注2：手柄状态在HVRLayoutCore.cs脚本的Update()中更新，如果要保持应用中所有获取手柄状态的脚本每一帧获取到的手柄状态一致，则需要开发者手动调整脚本执行顺序，确保应用所有获取手柄状态的脚本都在SDK脚本之前或之后执行。
说明
手动设置脚本执行顺序的方式：“Edit > Project Settings >  >  > Script Execution Order”菜单项中，通过设置脚本数字实现。
至此，SDK预制件已全部添加完成。
在场景中添加HUAWEI VR相机
编译配置生成APK
<div _ngcontent-ng-c3413314161="" class="
