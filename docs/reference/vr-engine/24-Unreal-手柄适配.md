# 24-Unreal-手柄适配

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-controller-actor-0000001205529523

---

场景中显示虚拟手柄，有以下两种方式：
将HuaweiVRController内容/BluePrints/HVRControllerActor拖入游戏关卡中，设置虚拟手柄的位置、大小，即可在游戏场景中显示虚拟手柄。
开发者可以参考HVRControllerActor，自行创建蓝图，添加手柄模型、获取手柄姿态：
HuaweiVRController内容/ControllerModel中HVRMotionController为SDK自带手柄模型，开发者也可以自定义手柄模型。
添加组件：MotionControllerComponent为父物体，命名为HVRMotionController，添加StaticMeshComponent为HVRMotionController的子物体，命名为HVRController。
为HVRController添加StaticMesh及Materials。
为 HVRController 设置初始旋转值为（-90.0, 0.0, 90.0），并通过GetHVRControllerOrientation()蓝图接口，获取手柄旋转姿态，赋值给HVRMotionController。
选中 HVRControllerActor，设置“细节 > Input”下的Auto Receive Input 选为 Player0。
手柄按键与Unreal中运动控制器按键接口的映射关系（详见HuaweiVRController.cpp）
展开
手柄按键名称
Unreal插件蓝图接口
Home按键
FGamepadKeyNames::SpecialRight
FGamepadKeyNames::SpecialLeft
返回按键
FGamepadKeyNames::MotionController_Right_Shoulder
FGamepadKeyNames::MotionController_Left_Shoulder
扳机按键
FGamepadKeyNames::MotionController_Right_Trigger
FGamepadKeyNames::MotionController_Left_Trigger
触摸板按键
FGamepadKeyNames::MotionController_Right_FaceButton1
FGamepadKeyNames::MotionController_Left_FaceButton1
触摸板左滑/摇杆左推
FGamepadKeyNames::MotionController_Right_FaceButton2
FGamepadKeyNames::MotionController_Left_FaceButton2
触摸板右滑/摇杆右推
FGamepadKeyNames::MotionController_Right_FaceButton3
FGamepadKeyNames::MotionController_Left_FaceButton3
触摸板上滑/摇杆上推
FGamepadKeyNames::MotionController_Right_FaceButton4
FGamepadKeyNames::MotionController_Left_FaceButton4
触摸板下滑/摇杆下推
FGamepadKeyNames::MotionController_Right_FaceButton5
FGamepadKeyNames::MotionController_Left_FaceButton5
触摸板轻触
FGamepadKeyNames::MotionController_Right_FaceButton6
FGamepadKeyNames::MotionController_Left_FaceButton6
触摸板持续触摸
FGamepadKeyNames::MotionController_Right_FaceButton7
FGamepadKeyNames::MotionController_Left_FaceButton7
扳机键 [6DoF手柄]
FGamepadKeyNames::MotionController_Right_Trigger
FGamepadKeyNames::MotionController_ Left_Trigger
侧握键 [6DoF手柄]
FGamepadKeyNames::MotionController_Right_Grip1
FGamepadKeyNames::MotionController_ Left_Grip1
A/X键 [6DoF手柄]
FGamepadKeyNames::MotionController_Right_FaceButton1
FGamepadKeyNames::MotionController_ Left_FaceButton1
B/Y键 [6DoF手柄]
FGamepadKeyNames::MotionController_Right_Shoulder
FGamepadKeyNames::MotionController_ Left_Shoulder
摇杆键按下 [6DoF手柄]
FGamepadKeyNames::MotionController_Right_Thumbstick
FGamepadKeyNames::MotionController_ Left_Thumbstick
Home/Menu键 [6DoF手柄]
FGamepadKeyNames::SpecialRight
FGamepadKeyNames::Special Left
开发者只需在蓝图中查找并调用以上对应接口，就可以实现手柄按键的响应事件。
默认快捷键说明：
展开
动作
按键
按键时间
功能
单击
Home按键
<1s
进入VRLauncher界面
长按
Home按键
>=1s
视点重置
长按
返回按键
>=3s
进入VRSetting界面
长按
Home + Trigger
>=1s
实现截图
说明
开发者如需自定义快捷键，请避免与上述快捷键组合冲突。
在关卡中添加HuaweiVRCamera
中心注视点渲染适配
<div _ngcontent-ng-c3413314161="" class="
