from setuptools import find_packages, setup

package_name = "reactive_control"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RoboRacer Team 7",
    maintainer_email="nabilafifahq@gmail.com",
    description="Reactive wall-follow controller with manual safety latch for RoboRacer indoor autonomy.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "wall_follow_node = reactive_control.wall_follow_node:main",
            "manual_map_logger = reactive_control.manual_map_logger:main",
            "manual_map_logger_smoke = reactive_control.manual_map_logger_smoke:main",
        ],
    },
)
