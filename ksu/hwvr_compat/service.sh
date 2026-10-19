#!/system/bin/sh
# hwvr_compat: 补 EMUI 那层系统差异。眼镜在位时：
#   1. /dev/hwvr1 指向真实 HID 控制接口（按协议应答探测，不写厂商号）
#   2. 手机逻辑尺寸对齐面板 2:1（1600x3200 -> 横屏 3200x1600），
#      让镜像 1:1、每只眼占面板一半，比例与畸变正常
# EMUI 原来由系统/服务起 MyService 加载 libHVRSDKServerApp 并触发
# VrHelmetExt.init() 来启动姿态链路；通用安卓没有这个机制，目前姿态
# 链没起来（详见 docs/PATCH_AUDIT.md 第 14 节），但头盔/手柄识别与
# IMU 数据流仍工作，所以画面能动、按手柄有反应。
MOD=/data/adb/modules/hwvr_compat
[ -d "$MOD" ] || MOD=/data/adb/modules_update/hwvr_compat

# zip 安装不保留可执行位，这里补一次。
chmod 755 "$MOD/service.sh" 2>/dev/null
chmod 755 "$MOD/hwvr-probe" 2>/dev/null

while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done

probe() {
    [ -x "$MOD/hwvr-probe" ] || return 1
    "$MOD/hwvr-probe" "/dev/$1" >/dev/null 2>&1
}

# 首选：拿真实协议去问，谁答谁就是控制接口（与厂商号无关）。
# 兜底：探测不可用时按 HID 接口名选。
find_control_iface() {
    for d in /sys/class/hidraw/hidraw*; do
        [ -e "$d/device/uevent" ] || continue
        node="${d##*/}"
        if probe "$node"; then
            echo "$node"
            return 0
        fi
    done
    for d in /sys/class/hidraw/hidraw*; do
        [ -e "$d/device/uevent" ] || continue
        if grep -q "GLASS HID" "$d/device/uevent" 2>/dev/null; then
            echo "${d##*/}"
            return 0
        fi
    done
    return 1
}

# 应用把 VR 画面画进手机显示的逻辑缓冲，再镜像到面板。
# 面板 3200x1600（2:1）；手机显示 1080x2640（竖屏）-> 横屏 2640x1080（2.44:1）。
# 设成 1600x3200 -> 横屏 3200x1600（与面板 1:1），每只眼占面板一半、
# 比例与畸变正常。代价是手机 GPU 多渲染约 2.2 倍像素，会发热，见
# docs/evidence/README.md。设 wm size 需要 SET_FORCED_DISPLAY_SIZE
# 权限；KSU 域里 adb shell / su 域调用实际可用，不行再降级。
# 不存状态文件（模块目录不一定可写），直接读当前的 override 判断。
ROT_STATE=/data/local/tmp/hwvr_rotation_saved

# 改之前先把手机自己的方向设置存下来：2026-09-16 用户报「手机被强制横屏」，
# 就是因为旧版这里写了 user_rotation=1 却只还自动旋转、不还方向，
# 拔掉眼镜后整机停在横屏（再叠加 ignore-orientation-request=true，应用自己
# 也转不回来）。
set_size() {
    if wm size 2>/dev/null | grep -q "Override size: 1600x3200"; then
        return 0
    fi
    if [ ! -f "$ROT_STATE" ]; then
        echo "$(settings get system accelerometer_rotation) $(settings get system user_rotation)" > "$ROT_STATE"
    fi
    wm size 1600x3200 2>/dev/null
    settings put system accelerometer_rotation 0 2>/dev/null
    settings put system user_rotation 1 2>/dev/null
}
reset_size() {
    # 只有在「真的有东西要还原」时才动，否则每 2 秒重写一次方向设置会把
    # 用户自己的手动转屏按住。三种情况才算需要还原：
    #   1) 上次 set_size 存过原值；2) 还留着 wm size 覆盖；3) 方向冻结还是 true。
    need=0
    [ -f "$ROT_STATE" ] && need=1
    wm size 2>/dev/null | grep -q "Override size:" && need=1
    wm get-ignore-orientation-request 2>/dev/null | grep -q "true" && need=1
    [ "$need" = "0" ] && return 0

    wm size reset 2>/dev/null
    # 方向按进 VR 之前的原值还回去；没有存过就回到「自动旋转 + 竖屏」。
    if [ -f "$ROT_STATE" ]; then
        read accel user < "$ROT_STATE"
        rm -f "$ROT_STATE"
    fi
    [ -n "$accel" ] || accel=1
    [ -n "$user" ] || user=0
    settings put system accelerometer_rotation "$accel" 2>/dev/null
    settings put system user_rotation "$user" 2>/dev/null
    # 这个开关是 EMUI VR 模式用来冻结方向的：它一旦留着，拔掉眼镜后
    # 整机还是横的。复位时一起清掉（需要 shell/root 权限，本模块就是 root）。
    wm set-ignore-orientation-request false 2>/dev/null
}

while true; do
    node=$(find_control_iface)
    if [ -n "$node" ]; then
        # 节点
        majmin=$(cat "/sys/class/hidraw/$node/dev" 2>/dev/null)
        maj=${majmin%%:*}
        min=${majmin##*:}
        if [ -n "$maj" ] && [ -n "$min" ]; then
            want=$(printf "%x:%x" "$maj" "$min")
            cur=$(stat -c "%t:%T" /dev/hwvr1 2>/dev/null)
            if [ "$cur" != "$want" ]; then
                rm -f /dev/hwvr1
                mknod /dev/hwvr1 c "$maj" "$min"
                chcon u:object_r:null_device:s0 /dev/hwvr1 2>/dev/null
                chmod 666 /dev/hwvr1
            fi
        fi
        # 显示尺寸（幂等，已在目标状态时不动）
        set_size
    else
        rm -f /dev/hwvr1
        reset_size
    fi
    sleep 2
done
