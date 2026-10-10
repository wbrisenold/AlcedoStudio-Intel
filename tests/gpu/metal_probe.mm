#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main() {
  @autoreleasepool {
    NSOperatingSystemVersion ver = [[NSProcessInfo processInfo] operatingSystemVersion];
    printf("macOS: %ld.%ld.%ld\n", (long)ver.majorVersion, (long)ver.minorVersion, (long)ver.patchVersion);
    if (ver.majorVersion < 13 || (ver.majorVersion == 13 && ver.minorVersion < 3)) {
      fprintf(stderr, "Alcedo requires macOS 13.3+; Intel macOS Catalina is unsupported.\n");
      return 2;
    }
    id<MTLDevice> gpu = MTLCreateSystemDefaultDevice();
    if (!gpu) {
      fprintf(stderr, "No usable Metal GPU was detected.\n");
      return 3;
    }
    printf("Metal device: %s\n", [[gpu name] UTF8String]);
    printf("Unified memory: %s\n", [gpu hasUnifiedMemory] ? "yes" : "no");
    printf("Max threads per threadgroup: %lu x %lu x %lu\n",
           (unsigned long)[gpu maxThreadsPerThreadgroup].width,
           (unsigned long)[gpu maxThreadsPerThreadgroup].height,
           (unsigned long)[gpu maxThreadsPerThreadgroup].depth);
    return 0;
  }
}
