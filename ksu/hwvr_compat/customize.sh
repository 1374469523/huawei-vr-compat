#!/system/bin/sh
# zip 打包不保留 Unix 可执行位，安装时补上。
ui_print "- setting exec permissions"
chmod 755 "$MODPATH/hwvr-probe" 2>/dev/null
chmod 755 "$MODPATH/service.sh" 2>/dev/null
