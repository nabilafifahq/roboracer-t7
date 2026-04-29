from setuptools import find_packages, setup

package_name = "pure_pursuit_followpath"

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
    description="Pure Pursuit controller exposed as nav2_msgs/action/FollowPath for RoboRacer (Ackermann mux output, TF pose input).",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "pp_followpath_server = pure_pursuit_followpath.pp_followpath_server:main",
            "pp_csv_followpath_client = pure_pursuit_followpath.pp_csv_followpath_client:main",
            "csv_to_mav_path_publisher = pure_pursuit_followpath.csv_to_mav_path_publisher:main",
            "pp_mav_path_follower = pure_pursuit_followpath.pp_mav_path_follower:main",
        ],
    },
)

