from setuptools import setup

setup(
	name='xssmgr',
	description='X ScreenSaver manager',
	packages=['xssmgr'],
	package_dir={'':'src'},
	entry_points={
		'console_scripts': [
			'xssmgr=xssmgr:main',
		]
	}
)
