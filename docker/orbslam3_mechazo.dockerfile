ARG BASE_IMAGE=nabilafifahq/roboracer-t7:full-stack
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV ORBSLAM3_WS=/opt/orbslam3_ws
ENV ORBSLAM3_SRC=${ORBSLAM3_WS}/src/ros2_orb_slam3

# Runtime + build deps for Mechazo ROS2 ORB-SLAM3 wrapper and OAK topic bridging.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3-pip \
    python3-rosdep \
    python3-colcon-common-extensions \
    python3-vcstool \
    libeigen3-dev \
    libssl-dev \
    libopencv-dev \
    python3-opencv \
    ros-humble-topic-tools \
    ros-humble-depthai-ros \
    v4l-utils \
    usbutils \
    pkg-config \
    cmake \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libglew-dev \
    libxkbcommon-dev \
    libwayland-dev \
    wayland-protocols \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavutil-dev \
    libavformat-dev \
    libswscale-dev \
    libavdevice-dev \
    libdc1394-dev \
    libraw1394-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

# Pangolin is not reliably available as apt package on all arm64/Jammy mirrors.
# Build it from source for deterministic cross-platform image builds.
RUN git clone --depth 1 https://github.com/stevenlovegrove/Pangolin /tmp/Pangolin && \
    cmake -S /tmp/Pangolin -B /tmp/Pangolin/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_EXAMPLES=OFF \
      -DBUILD_TOOLS=OFF \
      -DBUILD_PANGOLIN_FFMPEG=ON && \
    cmake --build /tmp/Pangolin/build -j"$(nproc)" && \
    cmake --install /tmp/Pangolin/build && \
    ldconfig && \
    rm -rf /tmp/Pangolin

# Clone Mechazo ORB-SLAM3 ROS2 wrapper in a dedicated workspace.
RUN mkdir -p "${ORBSLAM3_WS}/src" && \
    git clone --depth 1 https://github.com/Mechazo11/ros2_orb_slam3.git "${ORBSLAM3_SRC}"

# Initialize rosdep if needed, then install wrapper dependencies.
RUN if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then rosdep init; fi && \
    rosdep update

RUN pip3 install --no-cache-dir natsort

RUN source /opt/ros/humble/setup.bash && \
    cd "${ORBSLAM3_WS}" && \
    rosdep install -r --from-paths src --ignore-src -y --rosdistro humble --skip-keys="libcrypto python3-natsort"

# Mechazo repo links prebuilt DBoW2/g2o .so files. Rebuild these for arm64.
RUN source /opt/ros/humble/setup.bash && \
    cd "${ORBSLAM3_SRC}" && \
    rm -rf build lib && \
    rm -rf orb_slam3/build orb_slam3/lib && \
    rm -rf orb_slam3/Thirdparty/DBoW2/build orb_slam3/Thirdparty/DBoW2/lib && \
    rm -rf orb_slam3/Thirdparty/g2o/build orb_slam3/Thirdparty/g2o/lib && \
    find orb_slam3 -type f \( -name "*.so" -o -name "*.a" \) -delete && \
    sed -i 's|#include <opencv2/core/core.hpp>|#include <opencv2/core.hpp>|g' orb_slam3/Thirdparty/DBoW2/DBoW2/FORB.h && \
    sed -i 's|#include <opencv2/core/core.hpp>|#include <opencv2/core.hpp>|g' orb_slam3/Thirdparty/DBoW2/DBoW2/FClass.h && \
    sed -i 's|#include <opencv2/core/core.hpp>|#include <opencv2/core.hpp>|g' orb_slam3/Thirdparty/DBoW2/DBoW2/TemplatedVocabulary.h && \
    sed -i 's|set (dbow2_ROOR_DIR ".*")|set (dbow2_ROOR_DIR "${CMAKE_CURRENT_SOURCE_DIR}")|' orb_slam3/Thirdparty/DBoW2/CMakeLists.txt && \
    sed -i 's|set(g2o_SOURCE_DIR ".*")|set(g2o_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")|' orb_slam3/Thirdparty/g2o/CMakeLists.txt && \
    cmake -S orb_slam3/Thirdparty/DBoW2 -B orb_slam3/Thirdparty/DBoW2/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DOpenCV_INCLUDE_DIRS=/usr/include/opencv4 \
      -DOpenCV_LIBS=opencv_core && \
    cmake --build orb_slam3/Thirdparty/DBoW2/build -j"$(nproc)" && \
    cmake -S orb_slam3/Thirdparty/g2o -B orb_slam3/Thirdparty/g2o/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_FLAGS="-I/usr/include/eigen3" && \
    cmake --build orb_slam3/Thirdparty/g2o/build -j"$(nproc)"

# Build ORB-SLAM3 workspace.
RUN source /opt/ros/humble/setup.bash && \
    cd "${ORBSLAM3_WS}" && \
    colcon build --symlink-install --parallel-workers 1

# Convenience env for interactive docker exec shells.
RUN printf '\n# ORB-SLAM3 Mechazo overlay\nsource /opt/orbslam3_ws/install/setup.bash 2>/dev/null || true\n' >> /root/.bashrc

# Helpers to reduce repetitive command typing on car.
COPY scripts/orbslam3_mechazo_topics.sh /usr/local/bin/orbslam3_mechazo_topics
COPY scripts/orbslam3_mechazo_execs.sh /usr/local/bin/orbslam3_mechazo_execs
RUN chmod +x /usr/local/bin/orbslam3_mechazo_topics /usr/local/bin/orbslam3_mechazo_execs
