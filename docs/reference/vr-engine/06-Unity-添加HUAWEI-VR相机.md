# 06-Unity-添加HUAWEI-VR相机

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/dev-process-add-camera-0000001160484918

---

为了让场景能够显示成VR模式，首先需要添加华为VR相机，即HVRCamera，目录为Assets/HVR/Prefabs。添加方法如下：
鼠标点击HVRCamera，并按住鼠标左键拖入至Hierarchy工作区，并且删除工程建立时自动生成的相机MainCamera。
添加HVRCamera之后，场景已经能够在手机 / 平板上显示VR模式，单击HVRCamera，在Inspector栏中会显示其属性。
其中：
RenderDepthFormat为Unity中初始化RenderTexture时的depth参数，默认为24bit，可选择设置为16bit、24bit或32bit。
RenderResolutionScale为Unity中初始化RenderTexture时的分辨率缩放倍数，默认值为1，默认分辨率：1080*1080，开发者可根据场景复杂度设置渲染分辨率。
说明
修改此分辨率会改变内容清晰度，同时也会影响性能和功耗。
默认情况SDK会根据温控方案设置、调整分辨率，通过RenderResolutionScale调节的分辨率仅在温控方案失效时起作用。
SinglePass仅在开启Multiview模式时勾选， 开启Multiview模式具体方式请降功耗优化措施。
说明
普通模式切勿勾选，否则会出现显示问题。
新建Unity工程并导入SDK
在场景中添加HUAWEI VR手柄
<div _ngcontent-ng-c3413314161="" class="
