from setuptools import setup

setup(
    name='simple_drmaa_scheduler',
    version='0.1.0',
    packages=['scheduler', 'scheduler.parser', 'scheduler.executor'],
    url='',
    license='',
    author='nikita',
    author_email='',
    description='',
    entry_points={
        'console_scripts': [
            'scheduler = scheduler.cli:main'
        ]
    }, install_requires=['drmaa', 'PyYAML', 'ujson']
)
