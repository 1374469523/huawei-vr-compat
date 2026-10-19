# 19-Unreal-新建工程与Android环境配置

原链接：https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-env-config-0000001160488028

---

在Epic Games Launcher中启动已下载好的Unreal引擎，也可在下载好后创建快捷键方式直接启动。
新建项目，可选择创建“蓝图”工程，也可选择创建“C++”工程；然后，根据需求选择模板；Android开发，故平台选择为“移动设备/平板电脑”，同时为提高运行性能，选择“可缩放的3D或2D”。
打开“菜单 > 编辑 > 项目设置 > 平台 > Android软件开发工具包”。配置Android开发必要的SDK、NDK、JDK的路径，其中SDK API Level选择matchndk，NDK API Level选择android-24。
在主界面菜单栏中依次进入“编辑 > 项目设置 > 平台 > Android”，在“Build”选项下，勾选 Support armv7[aka armeabi-v7a] 选项。
注意
Android工程默认采用Gradle工具进行编译，如果在某些特殊情况下无法正常运行Gradle，可在配置选项中将“Enable Gradle instead of Ant”的勾选去掉，及采用Ant工具进行编译，当然采用Ant编译的前提是需要在Android软件开发工具包中正确配置Ant（可在Ant官网下载）目录。
开发准备
集成SDK Unreal插件包
<div _ngcontent-ng-c3413314161="" class="
