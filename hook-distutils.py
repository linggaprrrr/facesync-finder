from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all distutils submodules
hiddenimports = collect_submodules('distutils')

# Add specific modules that are commonly missing
hiddenimports += [
    'distutils.util',
    'distutils.sysconfig',
    'distutils.command',
    'distutils.command.build',
    'distutils.command.build_ext',
    'distutils.command.install',
    'distutils.core',
    'distutils.extension',
    'distutils.version',
]

# Collect data files if any
datas = collect_data_files('distutils')