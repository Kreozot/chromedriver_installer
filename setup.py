from distutils.command.install import install
from distutils.command.install_data import install_data
from setuptools import setup, find_packages
import hashlib
import os
import platform
import re
import tempfile
import sys
import zipfile

try:
    from urllib import request
except ImportError:
    import urllib as request


CHROMEDRIVER_INFO_URL = (
    'https://sites.google.com/a/chromium.org/chromedriver/downloads'
)
CHROMEDRIVER_URL_TEMPLATE = (
    'http://chromedriver.storage.googleapis.com/{version}/chromedriver_{os_}'
    '{architecture}.zip'
)

CHROMEDRIVER_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
CROMEDRIVER_LATEST_VERSION_PATTERN = re.compile(
    r'ChromeDriver (\d+\.\d+\.\d+\.\d+)'
)

# Global variables
chromedriver_version = None
chromedriver_checksums = None


def get_chromedriver_version():
    """Retrieves the most recent chromedriver version."""
    global chromedriver_version

    response = request.urlopen(CHROMEDRIVER_INFO_URL)
    content = response.read()
    match = CROMEDRIVER_LATEST_VERSION_PATTERN.search(str(content))
    if match:
        return match.group(1)
    else:
        raise Exception('Unable to get latest chromedriver version from {0}'
                        .format(CHROMEDRIVER_INFO_URL))


class InstallChromeDriver(install_data):
    """Downloads and unzips the requested chromedriver executable."""

    def _download(self, zip_path, validate=False):
        plat = platform.platform().lower()
        if plat.startswith('darwin'):
            os_ = 'mac'
            architecture = 64
        elif plat.startswith('linux'):
            os_ = 'linux'
            architecture = platform.architecture()[0][:-3]
        elif plat.startswith('win'):
            os_ = 'win'
            architecture = 32
        else:
            raise Exception('Unsupported platform: {0}'.format(plat))

        url = CHROMEDRIVER_URL_TEMPLATE.format(version=chromedriver_version,
                                               os_=os_,
                                               architecture=architecture)

        download_report_template = ("\t - downloading from '{0}' to '{1}'"
                                    .format(url, zip_path))

        def reporthoook(x, y, z):
            global download_ok

            percent_downloaded = '{0:.0%}'.format((x * y) / float(z))
            sys.stdout.write('\r')
            sys.stdout.write("{0} [{1}]".format(download_report_template,
                                                percent_downloaded))
            download_ok =  percent_downloaded == '100%'
            if download_ok:
                sys.stdout.write(' OK')
            sys.stdout.flush()

        request.urlretrieve(url, zip_path, reporthoook)

        print('')
        if not download_ok:
            print('\t - download failed!')

        if validate:
            if not self._validate(zip_path):
                raise Exception("The checksum of the downloaded file '{0}' "
                                "matches none of the checksums {1}!"
                                .format(zip_path,
                                        ', '.join(chromedriver_checksums)))

    def _unzip(self, zip_path):
        zf = zipfile.ZipFile(zip_path)
        out = tempfile.mkdtemp('chromedriver_distr')

        print("\t - extracting '{0}' to '{1}'.".format(zip_path, out))
        zf.extractall(out)

        return (os.path.join(out, f) for f in os.listdir(out))

    def _validate(self, zip_path):
        checksum = hashlib.md5(open(zip_path, 'rb').read()).hexdigest()
        return checksum in chromedriver_checksums

    def initialize_options(self):
        super().initialize_options()
        self.scripts_dir = None
        self.data_files = []

    def finalize_options(self):
        self.set_undefined_options('install', ('install_scripts', 'scripts_dir'))
        super().finalize_options()

    def run(self):
        global chromedriver_version, chromedriver_checksums

        validate = False

        if chromedriver_version:
            if chromedriver_checksums:
                validate = True
        else:
            chromedriver_version = get_chromedriver_version()

        file_name = 'chromedriver_{0}.zip'.format(chromedriver_version)
        zip_path = os.path.join(tempfile.gettempdir(), file_name)

        if validate:
            if os.path.exists(zip_path):
                print("\t - requested file '{0}' found at '{1}'."
                      .format(file_name, zip_path))

                if self._validate(zip_path):
                    print("\t - cached file '{0}' is valid.".format(zip_path))
                else:
                    print("\t - cached file '{0}' is not valid!"
                          .format(zip_path))
                    self._download(zip_path, validate=True)
            else:
                self._download(zip_path, validate=True)
        else:
            self._download(zip_path)

        chromedriver_files = self._unzip(zip_path)
        self.data_files = [(self.scripts_dir, chromedriver_files)]
        install_data.run(self)


class Install(install):
    """Used to get chromedriver version and checksums from install options"""

    # Fix an error when pip calls setup.py with the
    # --single-version-externally-managed and it is not supported due to
    # old setuptools version.
    _svem = list(filter(lambda x: x[0] == 'single-version-externally-managed',
                        install.user_options))
    sub_commands = [*install.sub_commands,
                    ('install_chrome_driver', lambda self: True)]

    if not _svem:
        single_version_externally_managed = None
        install.user_options.append(('single-version-externally-managed',
                                     None, ""))

    user_options = install.user_options + [
        ('chromedriver-version=', None, 'Chromedriver version'),
        ('chromedriver-checksums=', None, 'Chromedriver checksums'),
    ]

    def initialize_options(self):
        self.chromedriver_version = None
        self.chromedriver_checksums = []
        install.initialize_options(self)

    def run(self):
        global chromedriver_version, chromedriver_checksums

        if self.chromedriver_version:
            if not CHROMEDRIVER_VERSION_PATTERN.match(self.chromedriver_version):
                raise Exception('Invalid --chromedriver-version={0}! '
                                'Must match /{1}/'
                                .format(self.chromedriver_version,
                                        CHROMEDRIVER_VERSION_PATTERN.pattern))

        chromedriver_version = self.chromedriver_version
        chromedriver_checksums = self.chromedriver_checksums
        if chromedriver_checksums:
            chromedriver_checksums = [ch.strip() for ch in
                                      self.chromedriver_checksums.split(',')]

        install.run(self)


setup(
    name='chromedriver_installer',
    version='0.0.6',
    author='Peter Hudec',
    author_email='peterhudec@peterhudec.com',
    description='Chromedriver Installer',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst'))
        .read(),
    keywords='chromedriver installer',
    url='https://github.com/peterhudec/chromedriver_installer',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Installation/Setup',
    ],
    license='MIT',
    packages=find_packages(),
    cmdclass=dict(install_chrome_driver=InstallChromeDriver, install=Install)
)
