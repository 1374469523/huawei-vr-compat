# 30-OpenXR-应用开发

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-0000001097358498

---

新建Unity工程，进入工程界面后，依次选择：Assets->Import Package->Custom Package->HvrAudio.unitypackage，导入包中所有资源。
开发流程
设置系统音频属性
在Unity菜单栏中，依次选择：“Edit > Project Settings > Audio”，设置AudioManager中的属性。
System Sample Rate设置为48000，DSP Buffer Size设置为Best latency，Max Virtual Voices设置为128，Spatializer Plugin设置为HvrAudioSpatializer，其他选项采用默认值即可。
说明
Spatializer Plugin能够设置为HvrAudioSpatializer的前提是正确导入HvrAudio.unitypackage及平台正确，否则可能无法选择HvrAudioSpatializer。
创建混音器（Audio Mixer）
在Unity Assets中创建Audio Mixer，并编辑该Audio Mixer（双击进行编辑）。在Master界面中点击“Add”并选择“HvrAudioEffect”（注：此处不能选择HvrAudioSpatializer）。选中“HvrAudioEffect”将在Inspector面板中出现混响参数设置界面，可根据实际场景对混响参数进行设置。
创建声源（Audio Source）
当前音效插件只应用于对象声源场景，即声音必须与对象（object）绑定。
故在创建声源前需先创建对象，然后在此对象上绑定声源。编辑该声源，AudioClip设置为希望播放的音频文件，Output设置为上一步创建的Audio Mixer（Master），勾选Spatialize开启空间音效。
说明
如果要使VR音效处理生效，Audio Mixer和Spatialize都必须按上述说明正确选择（勾选），如开发人员对Unity音效不了解，除本文中有特殊说明的参数外，其他参数请保持默认设置（如Spatial Blend必须设置为0，如果设置为3D（1），则会出现重复混音处理，造成声音异常、引入杂音等）。
绑定UI脚本
给上一步创建的声源对象绑定预置的HvrAudioSource.cs脚本（位于Assets/HVRAudio目录下）。可以通过该脚本的UI界面进行空间音效参数的设置。
运行应用程序
在Android平台上运行该应用程序即可体验VR音效。
开发准备
业务简介
<div _ngcontent-ng-c3413314161="" class="
