# 05-Unity-新建工程并导入SDK

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/dev-process-import-sdk-0000001205644941

---

打开Unity，新建3D工程。
依次点击“Assets >  > Import Package > Custom Package”。
在弹出的对话框选择已下载的hvrsdk-3.5.x.unitypackage，点击Import，即可导入。
导入时若弹出如下提示框，请选择点击 “I Made a Backup, Go Ahead!”，否则编译出的应用会有找不到接口的问题。
hvrsdk-3.5.x.unitypackage导入后，由Assets/HVR/Scripts/HVRAddUILayer.cs自动添加HVRUILayer和HVRVolumeUILayer两个UI Layer。分别绘制特定UI和音量弹框。
若自动添加UI Layer失败，会有弹框提示，如下图所示，需要开发者手动添加名称为HVRUILayer和HVRVolumeUILayer的UI Layer。
开发者不允许在这两个UI Layer上绘制其他内容，也不允许场景中其他Camera显示这两个UI层（例如：修改HVR SDK的左右Camera的CullingMask，致使显示这两层内容）。
开发者若要修改HUAWEI VR Camera的CullingMask，也一定要同时保证该Camera不绘制这两个UI Layer。代码示例如下：
收起
自动换行
深色代码主题
复制
HVRLayoutCore.m_LeftCamObj.GetComponent<Camera>().cullingMask &= ~(1 << LayerMask.NameToLayer(HVRDefCore. m_VolumeUILayerName));
开发准备
在场景中添加HUAWEI VR相机
<div _ngcontent-ng-c3413314161="" class="
