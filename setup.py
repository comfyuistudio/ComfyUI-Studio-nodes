from setuptools import setup, find_packages

setup(
    name='ComfyUI-Studio-nodes',
    version='0.1.5',
    description='Image Size, Aspect Ratio, Image resize, HuggingFace model downloader, Git cloner',
    author='ComfyUI-Studio',
    packages=find_packages(where="custom_nodes"),
    package_dir={"": "custom_nodes"},
    install_requires=[
        "numpy",
        "torch",
        "Pillow"
    ],
    include_package_data=True,
    zip_safe=False,
)
