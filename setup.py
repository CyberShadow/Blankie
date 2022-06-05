from setuptools import setup

setup(
	name='blankie',
	description='X ScreenSaver manager',
	packages=['blankie'],
	package_dir={'':'src'},
	entry_points={
		'console_scripts': [
			'blankie=blankie:main',
		]
	}
)
