# 13-Unity-集成多个相机

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/feature-options-multi-camera-0000001160166440

---

如果需要集成多个Unity相机的功能，可以按如下方式添加：
将Assets/HVR/Prefabs目录下的HVRExtCamera拖入至Hierarchy工作区中，我们可以看到HVRExtCamera下挂载了两个相机，如下图所示，分别为左眼相机LeftCamera和右眼相机RightCamera，对应华为VR头盔中的左眼视图和右眼视图，在这里可拖入多组HVRExtCamera，然后对每一组相机的Clear Flags、Culling Mask、Depth等参数进行修改，实现多相机功能。
2D界面提示设置
在Unity Editor Play模式下预览调试
<div _ngcontent-ng-c3413314161="" class="
