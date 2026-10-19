/*
 * hwvr-probe: 判断某个 hidraw 节点是不是 VR 眼镜的控制接口。
 *
 * 原版 libWalleDev 打开 /dev/hwvr1 后做的第一件事就是 HIDIOCGFEATURE(4)，
 * 缓冲区首字节填 1（厂商号查询）。会说这个协议的就是眼镜的控制接口，
 * EMUI 上的 /dev/hwvr1 对应的正是它。
 *
 * 用真实设备响应来判断，不写死厂商/产品号，因此换任何 VR 设备都适用。
 */
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define HIDIOC_GET_FEATURE(len) \
    _IOC(_IOC_WRITE | _IOC_READ, 'H', 0x07, len)

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    int fd = open(argv[1], O_RDWR | O_NONBLOCK);
    if (fd < 0) return 3;
    unsigned char buf[8];
    memset(buf, 0, sizeof(buf));
    buf[0] = 1;
    int r = ioctl(fd, HIDIOC_GET_FEATURE(4), buf);
    close(fd);
    return r == 4 ? 0 : 4;
}