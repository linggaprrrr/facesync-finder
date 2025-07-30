from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all setuptools submodules
hiddenimports = collect_submodules('setuptools')

# Add specific modules
hiddenimports += [
    'setuptools.extension',
    'setuptools.command',
    'setuptools.command.build_ext',
    'setuptools.command.install',
    'setuptools.dist',
    'pkg_resources',
    'pkg_resources.extern',
]

# Collect data files
datas = collect_data_files('setuptools')
datas += collect_data_files('pkg_resources')