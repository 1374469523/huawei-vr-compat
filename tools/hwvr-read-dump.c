/*
 * hwvr-read-dump: 只读地把 /dev/hwvr1 上眼镜主动上报的报文打出来。
 *
 * 原版是两条路：特性报告（GET_REPORT）问一次，输入报告（read）持续收。
 * com.huawei.vrservice 的 VRDeviceNodeMonitor 走的是后者：read() 出来的
 * 缓冲区里，偏移 8 是数据类型（2 = 接近，3 = 心跳，5 = 电量，6 = 耳机，
 * 7 = 过热），前面 8 字节是头。这个工具用来核对这台设备到底有没有在推。
 *
 * 只做 read()，不写节点、不下发 SET_REPORT。
 *
 * 用法： hwvr-read-dump NODE [秒数] [最多报文数]
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static long long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s NODE [seconds] [max-packets]\n", argv[0]);
        return 2;
    }
    int seconds = argc > 2 ? atoi(argv[2]) : 5;
    int max_packets = argc > 3 ? atoi(argv[3]) : 200;
    int fd = open(argv[1], O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        fprintf(stderr, "open %s failed: %s\n", argv[1], strerror(errno));
        return 3;
    }
    long long deadline = now_ms() + (long long)seconds * 1000;
    int packets = 0;
    unsigned char buf[512];
    while (now_ms() < deadline && packets < max_packets) {
        struct pollfd pfd = {fd, POLLIN, 0};
        int ready = poll(&pfd, 1, 200);
        if (ready <= 0) {
            continue;
        }
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) {
                continue;
            }
            fprintf(stderr, "read failed: %s\n", strerror(errno));
            break;
        }
        packets++;
        printf("[%4d] t=%lldms len=%3zd", packets, now_ms(), n);
        if (n > 8) {
            printf(" type@8=%u", buf[8]);
        }
        printf("  ");
        for (ssize_t i = 0; i < n && i < 64; i++) {
            printf("%02x ", buf[i]);
        }
        if (n > 64) {
            printf("...");
        }
        printf("\n");
        fflush(stdout);
    }
    printf("done: %d packet(s) in %ds\n", packets, seconds);
    close(fd);
    return 0;
}
