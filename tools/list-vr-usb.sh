#!/system/bin/sh
# 诊断脚本：列出手柄/眼镜那台 USB 设备暴露了哪些接口、各自绑了什么驱动。
# 按厂商号 12d1（华为）筛，不写死产品号。
for d in /sys/bus/usb/devices/*; do
    idv=$(cat "$d/idVendor" 2>/dev/null)
    [ "$idv" = "12d1" ] || continue
    echo "== $d idVendor=$idv idProduct=$(cat "$d/idProduct" 2>/dev/null) product=$(cat "$d/product" 2>/dev/null)"
    for i in "$d"/*/; do
        ic=$(cat "$i/bInterfaceClass" 2>/dev/null)
        [ -n "$ic" ] || continue
        drv=$(basename "$(readlink -f "$i/driver" 2>/dev/null)" 2>/dev/null)
        echo "   $(basename "$i") class=$ic sub=$(cat "$i/bInterfaceSubClass" 2>/dev/null) proto=$(cat "$i/bInterfaceProtocol" 2>/dev/null) driver=$drv"
    done
done
