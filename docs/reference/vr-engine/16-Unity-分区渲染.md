# 16-Unity-分区渲染

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/feature-options-partity-render-0000001205526409

---

HVR SDK为应用提供分区渲染模式，提升中心区域清晰度，降低周边区域清晰度，需要开发者基于新增接口选择适配。
分区渲染开启方式：
1. 选择Partitioned Rendering Status中的选项。
选项描述：
展开
选项
描述
Off
关闭分区渲染
LowQuality
以低分辨率进行分区渲染
MiddleQuality
以中分辨率进行分区渲染
HighQuality
以高分辨率进行分区渲染
2. 勾选PlayerSettings中的Virtual Reality Supported，清空VirtualReality SDKs中的选项，Stereo Rendering Method选择Single Pass (Preview)，如图所示。
说明
分区渲染模式下请勿使用HVRExtCamera。
降功耗优化措施
业务简介
<div _ngcontent-ng-c3413314161="" class="
