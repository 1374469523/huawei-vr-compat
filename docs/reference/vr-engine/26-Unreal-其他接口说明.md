# 26-Unreal-其他接口说明

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-other-0000001160328084

---

FString GetHuaweiVRSDKVersion()
获取HuaweiVRSDK插件版本号。
int GetHMDInfo(HuaweiVRHelmetModel& helmetModel)
获取当前使用的头盔类型。
参数
展开
参数名称
参数类型
参数说明
helmetModel
HuaweiVRHelmetModel
HuaweiVR头盔类型：
HuaweiVRHelmet_FIRST_GEN：一代头盔
HuaweiVRHelmet_SECOND_GEN：二代头盔
HuaweiVRHelmet_NOT_FOUND：未找到头盔，可能是处于手机调试模式
HuaweiVRHelmet_UNKNOWN：未知
void GetHMDOrientationAndPosition(FQuat& Orientation, FVector& Position)
获取头盔的位置和姿态。其中3DoF模式下VRSDK不支持位置跟踪，故只能获取到正确的姿态，而位置数据始终为0。
参数
展开
参数名称
参数类型
参数说明
Orientation
FQuat
输出参数，用四元素表示的姿态数据
Position
FVector
输出参数，三维位置坐标
int ResetHMDYaw()
重置姿态偏航角。通常用于如下情况：当远离VR头盔，手机屏幕熄灭，再次佩戴头盔，点亮屏幕时，画面可能会发生视角偏离。
返回值
调用函数成功返回0，失败返回-1。
int SetHMDPoseLock(bool enable)
开启关闭姿态锁定。通常用于观看电影的情况，观看者在调整观看姿势前后，均调用该接口，分别开启、关闭姿态锁定，以保证观看的画面姿态不会发生变化。
参数
展开
参数名称
参数类型
参数说明
enable
bool
true：开启姿态锁定；false：解除姿态锁定
返回值
调用函数成功返回0，失败返回-1。
int SetChromaticAberration(bool enable)
开启或关闭色散功能，enable为true: 开启色散功能，enable为false:关闭色散功能。
参数
展开
参数名称
参数类型
参数说明
enable
bool
true: 开启色散功能；false:关闭色散功能
返回值
调用函数成功返回0，失败返回-1。
int SetSvsEffect(bool enable)
开启EMUI系统的SVS音效，该接口需要android.permission.MODIFY_AUDIO_SETTINGS权限。
开启后，应用中所有声音的方位会随着头转而发生变化，适用于VR中观看视频的场景，但开发者应注意开启的时机并及时关闭。
参数
展开
参数名称
参数类型
参数说明
enable
bool
使能SVS音效的输入参数（true: 开启SVS音效， false:关闭SVS音效）
返回值
调用函数成功返回0，失败返回-1。
bool IsLeftHandMode()
是否启用左手模式，开发者可以根据是否处于左手模式，调整虚拟手柄显示位置。
返回值
调用函数成功返回值为true：是左手模式，false：不是左手模式。
FRotator GetHVRControllerOrientation (const EControllerHand DeviceHand)
获取当前手柄的姿态。
返回值
展开
参数名称
参数类型
参数说明
Orientation
FQuat
输出参数，用四元素表示的姿态数据
void GetHVRControllerOrientationAndPosition(const EControllerHand DeviceHand, FRotator& Orientation, FVector& Position)
获取当前手柄的姿态和位置，未开启6DoF位置追踪时位置返回为0。
返回值
展开
参数名称
参数类型
参数说明
Orientation
FQuat
输出参数，用四元素表示的姿态数据
Position
FVector
输出参数，三维位置坐标
FVector2D GetHVRControllerTouchpadTouchPos(const EControllerHand DeviceHand)
获取用户触碰手柄上触控板（如有）的实时坐标。
返回值
触控板被触碰时的二维坐标。
FVector2D GetHVRControllerThumbstickPos(const EControllerHand DeviceHand)
获取用户手柄上摇杆（如有）的实时坐标。
返回值
摇杆键当前状态的二维坐标。
bool IsAvailable(const EControllerHand DeviceHand)
判断当前手柄实例是否可用。
返回值
可用时返回值为true，不可用返回false。
bool GetHVRControllerMessage(HVRControllerMessageType& type, int& priority, TMap<FString, FString>& message)
获取当前手柄的相关信息。
返回值
调用函数成功返回值为true：是左手模式，false：不是左手模式。
bool GetHVRControllerType(const EControllerHand DeviceHand, HVRControllerType& type)
获取当前手柄类型信息。
返回值
调用函数成功返回值为true：是左手模式，false：不是左手模式。
int StartControllerVibration(const EControllerHand DeviceHand, float amplitude, int durationTimeMs, float frequency, HVRControllerWaveformType waveform)
使当前手柄开始震动。
展开
Parameter Name
Description
amplitude
设置震动强度，取值范围：0-1
durationTimeMs
设置震动总时长，波形1-8总时长固定
frequency
设置震动频率，取值范围：0-1
waveform
设置震动波形，波形包括0-8，默认为0，仅默认波形可调节强度和频率
返回值
调用函数成功返回0，失败返回-1。
int StopControllerVibration(const EControllerHand DeviceHand)
使当前手柄停止震动。
返回值
调用函数成功返回0，失败返回-1。
中心注视点渲染适配
FAQ
<div _ngcontent-ng-c3413314161="" class="
