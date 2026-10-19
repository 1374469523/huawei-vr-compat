#!/system/bin/sh
# 在手机上重新部署 hwvr_compat 模块并复位被冻结的显示方向。
#
#   adb push ksu/hwvr_compat/service.sh /data/local/tmp/hwvr-service-new.sh
#   adb push ksu/hwvr_compat/deploy.sh  /data/local/tmp/hwvr-deploy.sh
#   adb shell su -c "sh /data/local/tmp/hwvr-deploy.sh"
#
# 为什么要它：模块里的 service.sh 是靠常驻循环补 /dev/hwvr1 与显示尺寸的，
# 换了脚本必须**先杀掉还在跑旧逻辑的循环**再重启，否则新旧两套逻辑会互相打架
# （2026-09-16 现场就是旧循环把 user_rotation 留在横屏）。

MOD=/data/adb/modules/hwvr_compat
NEW=/data/local/tmp/hwvr-service-new.sh

[ -f "$NEW" ] || { echo "缺少 $NEW"; exit 1; }
[ -d "$MOD" ] || { echo "缺少模块目录 $MOD"; exit 1; }

cp "$NEW" "$MOD/service.sh"
chmod 755 "$MOD/service.sh"

for p in $(ps -A -o PID,ARGS | grep hwvr_compat/service.sh | grep -v grep | awk '{print $1}'); do
    kill "$p" 2>/dev/null
done
sleep 1

setsid sh "$MOD/service.sh" >/dev/null 2>&1 &
sleep 2

# 现场复位：把上一次 VR 会话留下的方向冻结清掉。
wm set-ignore-orientation-request false
settings put system accelerometer_rotation 1
settings put system user_rotation 0

echo "--- 模块进程"
ps -A -o PID,ARGS | grep hwvr_compat | grep -v grep
echo "--- 方向状态"
wm get-ignore-orientation-request
settings get system user_rotation
settings get system accelerometer_rotation
wm size | head -2
wm density | head -2
