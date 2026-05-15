import glob
import os

from setuptools import find_packages, setup

package_name = "roboracer_nav2_vector_pursuit"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob.glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob.glob("config/*.yaml")),
        (os.path.join("share", package_name, "maps"), glob.glob("maps/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RoboRacer Team 7",
    maintainer_email="nabilafifahq@gmail.com",
    description="Nav2 bringup with vector pursuit + /global_path bridge for RoboRacer.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "global_path_follow_bridge = roboracer_nav2_vector_pursuit.global_path_follow_bridge:main",
            "twist_to_ackermann = roboracer_nav2_vector_pursuit.twist_to_ackermann:main",
        ],
    },
)
