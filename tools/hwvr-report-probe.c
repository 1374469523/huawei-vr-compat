/*
 * hwvr-report-probe: 只读地把 /dev/hwvr1 的特性报告逐条问一遍。
 *
 * 用途：核对原版 VRServiceX（com.huawei.vrservice）里 UpgradeGlass.cpp 的那几条
 * HIDIOCGFEATURE 调用在这台设备上到底返回什么，特别是
 *
 *   接近（proximity）: ioctl(fd, HIDIOCGFEATURE(1), buf), buf[0] = 4
 *   电量（battery）  : ioctl(fd, HIDIOCGFEATURE(8), buf), buf[0] = 8
 *
 * 全部是 GET_REPORT（HIDIOCGFEATURE），不下发任何 SET_REPORT，不改设备状态。
 * report id / 长度取自 libvrservice.so 与 libWalleDev.so 的反汇编，不写死厂商号。
 *
 * 用法：
 *   hwvr-report-probe NODE                  # 跑下面这张原版用到的表
 *   hwvr-report-probe NODE 4:1 4:2 8:8 ...  # 自定义 report id:长度 列表
 */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define HIDIOC_GET_FEATURE(len) \
    _IOC(_IOC_WRITE | _IOC_READ, 'H', 0x07, len)

struct probe {
    unsigned char report;
    unsigned int len;
    const char *what;
};

/* 顺序与原版一致：先厂商号，再版本、接近、电量、光学/偏移。 */
static const struct probe probes[] = {
    {1, 4, "vendor info (libWalleDev::ioGetVendorInfo)"},
    {2, 62, "glass version (libWalleDev::ioGetVersionInfo)"},
    {4, 1, "proximity (UpgradeGlass::IoGetProximityStatus)"},
    {8, 8, "battery (UpgradeGlass::IoGetBatteryStatus)"},
    {9, 48, "optical info (libWalleDev::ioGetGlassOpticalInfo)"},
    {9, 16, "display offset (libWalleDev::ioGetOffsetInfo)"},
};

static void run(int fd, unsigned char report, unsigned int len, const char *what) {
    static unsigned char buf[512];
    if (len == 0 || len > sizeof(buf)) {
        printf("report %2u len %3u skipped (probe tool limit)\n", report, len);
        return;
    }
    memset(buf, 0, sizeof(buf));
    buf[0] = report;
    errno = 0;
    int ret = ioctl(fd, HIDIOC_GET_FEATURE(len), buf);
    printf("report %2u len %3u ret %3d errno %2d (%s)", report, len, ret, errno,
           strerror(errno));
    if (what != NULL) {
        printf("  <- %s", what);
    }
    printf("\n");
    if (ret > 0) {
        printf("    ");
        for (int b = 0; b < ret && b < (int)len; b++) {
            printf("%02x ", buf[b]);
        }
        printf("\n");
    }
    fflush(stdout);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s NODE [report:len ...]\n", argv[0]);
        return 2;
    }
    int fd = open(argv[1], O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        fprintf(stderr, "open %s failed: %s\n", argv[1], strerror(errno));
        return 3;
    }
    if (argc == 2) {
        for (unsigned int i = 0; i < sizeof(probes) / sizeof(probes[0]); i++) {
            run(fd, probes[i].report, probes[i].len, probes[i].what);
        }
    } else {
        for (int i = 2; i < argc; i++) {
            unsigned int report = 0, len = 0;
            if (sscanf(argv[i], "%u:%u", &report, &len) != 2 || report > 0xff) {
                fprintf(stderr, "bad spec '%s' (want report:len)\n", argv[i]);
                close(fd);
                return 4;
            }
            run(fd, (unsigned char)report, len, NULL);
        }
    }
    close(fd);
    return 0;
}
