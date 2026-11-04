"""Build a separate development app with the installed Command Line Tools.

The existing release app is read only. Its signed Sparkle framework supplies
the dependency that Xcode normally resolves through Swift Package Manager.
This script neither launches the app nor grants Screen Recording permission.
"""
from pathlib import Path
import json
import os
import plistlib
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
RELEASE = Path('/Applications/OpenDisplay.app')
APP = ROOT / 'build/Build/Products/Debug/OpenDisplay Dev.app'

def run(args):
    subprocess.run(args, cwd=ROOT, check=True)

def sparkle_sdk():
    framework = RELEASE / 'Contents/Frameworks/Sparkle.framework'
    if (framework / 'Headers/Sparkle.h').is_file():
        return framework.parent
    # Distributed apps normally strip headers and Clang module maps. Read
    # matching public headers from Sparkle's official source release; keep
    # linking the installed, signed framework binary.
    version = plistlib.loads((framework / 'Resources/Info.plist').read_bytes())['CFBundleShortVersionString']
    source = ROOT / 'build/deps/SparkleSource'
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run(['git', 'clone', '--depth', '1', '--filter=blob:none', '--sparse',
             '--branch', version, 'https://github.com/sparkle-project/Sparkle.git', str(source)])
        run(['git', '-C', str(source), 'sparse-checkout', 'set', 'Sparkle'])
    tag = subprocess.check_output(['git', '-C', str(source), 'describe', '--tags', '--exact-match'], text=True).strip()
    if tag != version:
        raise SystemExit(f'Sparkle headers {tag} do not match installed binary {version}')
    sdk_framework = ROOT / 'build/deps/SparkleSDK/Sparkle.framework'
    if not sdk_framework.exists():
        run(['ditto', str(framework), str(sdk_framework)])
    headers = sdk_framework / 'Headers'
    modules = sdk_framework / 'Modules'
    headers.mkdir(exist_ok=True)
    modules.mkdir(exist_ok=True)
    for header in (source / 'Sparkle').glob('*.h'):
        shutil.copy2(header, headers / header.name)
    if not (headers / 'Sparkle.h').is_file():
        raise SystemExit('Official Sparkle umbrella header is missing')
    (modules / 'module.modulemap').write_text(
        'framework module Sparkle {\n umbrella header "Sparkle.h"\n export *\n module * { export * }\n}\n')
    return sdk_framework.parent

def main():
    if APP.exists():
        if (APP / 'Contents/MacOS/OpenDisplay Dev').exists():
            raise SystemExit(f'Build output already exists; inspect before rebuilding: {APP}')
        suffix = 1
        while APP.with_name(f'OpenDisplay Dev.incomplete-{suffix}').exists():
            suffix += 1
        APP.rename(APP.with_name(f'OpenDisplay Dev.incomplete-{suffix}'))
    sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
    framework_search_path = sparkle_sdk()
    contents = APP / 'Contents'
    (contents / 'MacOS').mkdir(parents=True)
    (contents / 'Resources').mkdir()
    (contents / 'Frameworks').mkdir()
    info = plistlib.loads((RELEASE / 'Contents/Info.plist').read_bytes())
    info.update({
        'CFBundleIdentifier': 'com.peetzweg.opensidecar.mac.debug',
        'CFBundleExecutable': 'OpenDisplay Dev',
        'CFBundleName': 'OpenDisplay Dev',
        'CFBundleDisplayName': 'OpenDisplay Dev',
        'CFBundleShortVersionString': '1.30.1',
        'CFBundleVersion': '13001',
        'SUEnableAutomaticChecks': False,
    })
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    icon = info.get('CFBundleIconFile', '')
    for name in ['Assets.car', icon, icon + '.icns' if icon else '']:
        if name and (RELEASE / 'Contents/Resources' / name).is_file():
            shutil.copy2(RELEASE / 'Contents/Resources' / name, contents / 'Resources' / name)
    run(['ditto', str(RELEASE / 'Contents/Frameworks/Sparkle.framework'),
         str(contents / 'Frameworks/Sparkle.framework')])
    sources = sorted(str(p.relative_to(ROOT)) for folder in ['Mac', 'Shared']
                     for p in (ROOT / folder).glob('*.swift'))
    command = ['nice', '-n', '15', 'xcrun', 'swiftc', '-O', '-whole-module-optimization',
               '-num-threads', '1', '-swift-version', '5', '-D', 'DEBUG',
               '-target', 'x86_64-apple-macosx14.0', '-sdk', sdk,
               '-import-objc-header', 'Mac/OpenSidecarMac-Bridging-Header.h',
               '-F', str(framework_search_path), '-framework', 'Sparkle',
               '-Xlinker', '-rpath', '-Xlinker', '@executable_path/../Frameworks',
               *sources, '-o', str(contents / 'MacOS/OpenDisplay Dev')]
    start = time.monotonic()
    run(command)
    requirement = 'designated => identifier "com.peetzweg.opensidecar.mac.debug"'
    run(['codesign', '--force', '--sign', '-', '--requirements', '=' + requirement,
         '--entitlements', 'Mac/OpenSidecarMac.entitlements', str(APP)])
    run(['codesign', '--verify', '--deep', '--strict', str(APP)])
    result = {'app': str(APP), 'bundle_id': info['CFBundleIdentifier'],
              'build_seconds': round(time.monotonic() - start, 1),
              'release_app_modified': False, 'launched': False}
    (ROOT / 'build/local-build-result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
