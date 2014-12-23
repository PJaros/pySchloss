from distutils.core import setup

setup(
    name='pySchloss',
    version='0.2',
    packages=['pySchloss'],
    url='https://github.com/PJaros/pySchloss',
    license='Apache License, Version 2.0',
    author='Paul Jaros',
    author_email='jaros.paul@gmail.com',
    description='Programm zum Schlosssystem im Ruum42',
    
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',

        # Indicate who your project is intended for
        'Intended Audience :: Other Audience',
        'Topic :: Home Automation',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: Apache Software License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],

    # What does your project relate to?
    # keywords='sample setuptools development'    
)
