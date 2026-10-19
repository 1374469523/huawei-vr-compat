# 15-Unity-降功耗优化措施

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/feature-options-reduce-power-0000001160006450

---

HUAWEI VR SDK针对不同VR应用场景提供Multiview和单目渲染两种降功耗优化措施，需要开发者基于新增接口选择适配。
场景与接口的匹配建议如下：
视频类：适用单目渲染
游戏类：适用Multiview
其他类：需要根据具体应用类型区分，普通工具类（如VR虚拟桌面）适用单目渲染接口，强3D类（如VR三维绘画）适用Multiview
Multiview模式开启方式：
勾选SinglePass选项。
勾选PlayerSettings中的Virtual Reality Supported，清空VirtualReality SDKs中的选项，Stereo Rendering Method选择Single Pass (Preview)。
说明
Multiview模式开启时，不支持集成HVRExtCamera预制件。
单目模式开启方式：调用接口：void EnableMonocularDisplay(bool enable)，调用方式参考EnableMonocularDisplay。
说明
Multiview和单目渲染两种方式不能同时开启。
在Unity Editor Play模式下预览调试
分区渲染
<div _ngcontent-ng-c3413314161="" class="
