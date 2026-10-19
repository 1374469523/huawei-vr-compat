#!/system/bin/sh
# 在设备上跑一次 hidraw 诊断：临时把目标节点标签改成 null_device（与
# hwvr_compat 模块给 /dev/hwvr1 的标签一致），跑完立刻改回原标签。
# 只改这一个节点的标签，不动 SELinux 的 enforcing 模式。
#
# 用法（设备上，root）：
#   sh /data/local/tmp/hidraw-probe.sh /dev/hidraw1 reports 1:4 2:80 4:1 8:8
#   sh /data/local/tmp/hidraw-probe.sh /dev/hidraw1 read 20 500
#
# reports <id:len ...>  用 hwvr-report-probe 逐条 GET_REPORT
# read <秒> [最多报文]   用 hwvr-read-dump 打印眼镜主动上报的报文
set -e
NODE="$1"
MODE="$2"
shift 2
chmod 755 /data/local/tmp/hwvr-report-probe /data/local/tmp/hwvr-read-dump 2>/dev/null || true
ctx=$(ls -Z "$NODE" 2>/dev/null | awk '{print $1}')
chcon u:object_r:null_device:s0 "$NODE" 2>/dev/null || true
rc=0
case "$MODE" in
    reports) /data/local/tmp/hwvr-report-probe "$NODE" "$@" || rc=$? ;;
    read)    /data/local/tmp/hwvr-read-dump "$NODE" "$@" || rc=$? ;;
    *)       echo "usage: $0 NODE {reports|read} ..." >&2; rc=2 ;;
esac
[ -n "$ctx" ] && chcon "$ctx" "$NODE" 2>/dev/null
exit $rc
