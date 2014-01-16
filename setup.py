from distutils.core import setup

setup(
    name='ec2-collective',
    version='0.0.1',
    author='Anders Dyekjaer Hansen',
    author_email='anders@dyejaer.dk',
    packages=[],
    scripts=['bin/ec2-cagent', 'bin/ec2-cmaster','bin/sqs-price-calculator'],
    url='http://pypi.python.org/pypi/ec2-collective/',
    license='LICENSE.txt',
    description='Mcollective alternative using AWS SQS',
    long_description=open('README.txt').read(),
    install_requires=[
      "boto >= 2.0",
      ],
    )
