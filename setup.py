from setuptools import setup, find_packages

setup(
    name="falcon_forecast",
    version="1.0.0",
    description="猛禽迁徙预测系统",
    long_description=open('ReadMe.md', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    author="Jason Zhou",
    author_email="raptor@migration.ai",
    url="https://github.com/jasonzhouyu/falcon_forecast",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'app': ['templates/*'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires='>=3.8',
    install_requires=[
        'Flask>=3.1.0',
        'PyQt6>=6.5.0',
        'requests>=2.30.0',
        'openmeteo-requests>=1.7.0',
        'requests-cache>=1.3.0',
        'retry-requests>=2.0.0',
        'python-dotenv>=1.0.0',
        'numpy>=2.0.0',
    ],
    entry_points={
        'console_scripts': [
            'falcon_forecast=falcon_gui:main',
            'falcon_forecast_web=app.app:main',
        ],
    },
)