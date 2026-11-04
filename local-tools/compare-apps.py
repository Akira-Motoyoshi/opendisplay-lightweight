"""Authorized BAAB comparison of the installed release and built light app.

Only OpenDisplay processes are stopped. App binaries, signatures, settings,
other applications, and the receiver are left unchanged. The light app is
restored at the end. CPU uses kernel cumulative nanosecond counters rather
than ps's recent exponentially weighted estimate.
"""
from pathlib import Path
import ctypes
import datetime
import json
import os
import re
import signal
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
OUT = HOME / 'Documents/Mac診断' / ('OpenDisplay比較_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)
APPS = {
    'B': {'label': 'light', 'bundle': 'com.peetzweg.opensidecar.mac.debug',
          'app': ROOT / 'build/Build/Products/Debug/OpenDisplay Dev.app',
          'log': HOME / 'Library/Logs/OpenDisplay Dev/opendisplay.log'},
    'A': {'label': 'release', 'bundle': 'com.peetzweg.opensidecar.mac',
          'app': Path('/Applications/OpenDisplay.app'),
          'log': HOME / 'Library/Logs/OpenDisplay/opendisplay.log'},
}
FIELDS = ['ri_user_time', 'ri_system_time', 'ri_pkg_idle_wkups',
          'ri_interrupt_wkups', 'ri_pageins', 'ri_wired_size',
          'ri_resident_size', 'ri_phys_footprint', 'ri_proc_start_abstime',
          'ri_proc_exit_abstime', 'ri_child_user_time', 'ri_child_system_time',
          'ri_child_pkg_idle_wkups', 'ri_child_interrupt_wkups',
          'ri_child_pageins', 'ri_child_elapsed_abstime',
          'ri_diskio_bytesread', 'ri_diskio_byteswritten']

class Usage(ctypes.Structure):
    _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in FIELDS]

class Cpu(ctypes.Structure):
    _fields_ = [('ticks', ctypes.c_uint32 * 4)]

PROC = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
PROC.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
SYSTEM = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
SYSTEM.mach_host_self.restype = ctypes.c_uint32
HOST = SYSTEM.mach_host_self()

def command(args, timeout=20):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.PIPE, timeout=timeout).strip()

def app_pid(kind):
    asn = command(['lsappinfo', 'find', 'bundleID=' + APPS[kind]['bundle']])
    if not asn:
        return None
    text = command(['lsappinfo', 'info', '-only', 'pid', asn])
    match = re.search(r'"pid"\s*=\s*(\d+)', text)
    return int(match.group(1)) if match else None

def usage(pid):
    value = Usage()
    if PROC.proc_pid_rusage(pid, 2, ctypes.byref(value)):
        raise ProcessLookupError(pid)
    return {name: int(getattr(value, name)) for name in FIELDS}

def host_cpu():
    value, count = Cpu(), ctypes.c_uint32(4)
    code = SYSTEM.host_statistics(HOST, 3, ctypes.byref(value), ctypes.byref(count))
    if code:
        raise RuntimeError(f'host_statistics returned {code}')
    return list(value.ticks)

def vm():
    text = command(['vm_stat'])
    values = {k.strip(): int(v) for k, v in re.findall(r'^([^:\n]+):\s*([0-9]+)\.', text, re.M)}
    return {'swapins': values['Swapins'], 'swapouts': values['Swapouts']}

def cpu_percent(a, b):
    ticks = [(y - x) & 0xffffffff for x, y in zip(a, b)]
    return 100 * (ticks[0] + ticks[1] + ticks[3]) / max(1, sum(ticks))

def log_data(kind, offset=0):
    path = APPS[kind]['log']
    if not path.exists():
        return ''
    with path.open('rb') as f:
        size = path.stat().st_size
        f.seek(offset if offset <= size else 0)
        return f.read().decode('utf-8', errors='replace')

def config(text):
    matches = re.findall(r'capture started: (\d+)x(\d+) display \d+ generation \d+ mode (\w+) localCursor=(\w+)', text)
    if not matches:
        return None
    w, h, mode, cursor = matches[-1]
    return {'width': int(w), 'height': int(h), 'mode': mode, 'local_cursor': cursor == 'true'}

def phone_stats(text):
    rows = []
    for line in text.splitlines():
        if 'PHONE-STATS ' not in line:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(line.split('PHONE-STATS ', 1)[1])
        except (ValueError, json.JSONDecodeError):
            continue
        # Keep performance measurements only, without receiver identifiers.
        keys = ['fps', 'capFps', 'enc50', 'dec50', 'e2e50', 'e2e95', 'rtt',
                'stalls', 'hitch', 'mbps', 'transport', 'codec', 'cur', 'curLost']
        rows.append({key: obj[key] for key in keys if key in obj})
    return rows

def switch(kind):
    other = 'A' if kind == 'B' else 'B'
    pid = app_pid(other)
    if pid:
        # Only the two OpenDisplay identities explicitly approved for this test.
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                usage(pid)
            except ProcessLookupError:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f'{other} did not exit; no forced kill was used')
    pid = app_pid(kind)
    old_size = APPS[kind]['log'].stat().st_size if APPS[kind]['log'].exists() else 0
    offset = old_size if not pid else 0
    if not pid:
        if kind == 'B':
            command(['zsh', './run.sh'])
        else:
            command(['open', str(APPS[kind]['app'])])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            pid = app_pid(kind)
            if pid:
                break
            time.sleep(0.5)
        if not pid:
            raise RuntimeError(f'{kind} did not start')
    # Display the same control panel for each version before the warm-up.
    command(['open', str(APPS[kind]['app'])])
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        text = log_data(kind, offset)
        active_config = config(text)
        if active_config and phone_stats(text):
            print(json.dumps({'event': 'connected', 'kind': kind, 'pid': pid,
                              'config': active_config}), flush=True)
            return pid, active_config
        time.sleep(1)
    raise RuntimeError(f'{kind}: no fresh capture and receiver statistics; check connection/permissions')

def phase(index, kind):
    pid, capture = switch(kind)
    print(json.dumps({'event': 'warmup', 'index': index, 'kind': kind, 'seconds': 20}), flush=True)
    time.sleep(20)
    offset = APPS[kind]['log'].stat().st_size
    before_vm, before_cpu = vm(), host_cpu()
    first = usage(pid)
    start = time.monotonic()
    snapshots = [{'elapsed': 0.0, 'usage': first, 'cpu_ticks': before_cpu}]
    print(json.dumps({'event': 'measurement_started', 'index': index, 'kind': kind, 'seconds': 60}), flush=True)
    for step in range(1, 31):
        time.sleep(max(0, start + step * 2 - time.monotonic()))
        snapshots.append({'elapsed': time.monotonic() - start, 'usage': usage(pid), 'cpu_ticks': host_cpu()})
        if step in [15, 30]:
            print(json.dumps({'event': 'measurement_progress', 'index': index, 'kind': kind,
                              'elapsed': round(snapshots[-1]['elapsed'], 1)}), flush=True)
    duration = snapshots[-1]['elapsed']
    final, end_cpu = snapshots[-1]['usage'], snapshots[-1]['cpu_ticks']
    after_vm = vm()
    rows = phone_stats(log_data(kind, offset))
    latest_config = config(log_data(kind))
    # Preserve every observation even when a trial fails validation.
    (OUT / f'raw-trial-{index}-{kind}.json').write_text(json.dumps(
        {'capture': capture, 'latest_capture': latest_config,
         'snapshots': snapshots, 'receiver_stats': rows,
         'vm_before': before_vm, 'vm_after': after_vm}, ensure_ascii=False, indent=2))
    if latest_config != capture:
        raise RuntimeError('Capture dimensions/mode changed during a trial')
    if final['ri_proc_start_abstime'] != first['ri_proc_start_abstime']:
        raise RuntimeError('App restarted during a trial')
    transports = sorted({str(r.get('transport')) for r in rows})
    codecs = sorted({str(r.get('codec')) for r in rows})
    if not rows or transports != ['USB'] or len(codecs) != 1:
        raise RuntimeError(f'Incomplete or changing receiver stream: {transports}, {codecs}')
    summary = {
        'trial': index, 'kind': kind, 'label': APPS[kind]['label'], 'pid': pid,
        'duration_s': duration, 'capture': capture,
        'app_cpu_percent': (final['ri_user_time'] + final['ri_system_time'] - first['ri_user_time'] - first['ri_system_time']) / 1e9 / duration * 100,
        'app_footprint_mib': statistics.mean(s['usage']['ri_phys_footprint'] / 1048576 for s in snapshots),
        'app_resident_mib': statistics.mean(s['usage']['ri_resident_size'] / 1048576 for s in snapshots),
        'system_cpu_percent': cpu_percent(before_cpu, end_cpu),
        'swapin_mib': (after_vm['swapins'] - before_vm['swapins']) * os.sysconf('SC_PAGE_SIZE') / 1048576,
        'swapout_mib': (after_vm['swapouts'] - before_vm['swapouts']) * os.sysconf('SC_PAGE_SIZE') / 1048576,
        'receiver_samples': len(rows), 'transports': transports, 'codecs': codecs,
    }
    for key in ['fps', 'capFps', 'enc50', 'e2e50', 'e2e95', 'rtt', 'cur', 'curLost']:
        values = [r[key] for r in rows if isinstance(r.get(key), (float, int))]
        summary[key + '_mean'] = statistics.mean(values) if values else None
    samples = {'summary': summary, 'snapshots': snapshots, 'receiver_stats': rows}
    (OUT / f'trial-{index}-{kind}.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2))
    print(json.dumps({'event': 'trial_complete', **summary}, ensure_ascii=False), flush=True)
    return summary

def main():
    print(json.dumps({'event': 'experiment_started', 'output': str(OUT),
                      'order': ['B', 'A', 'A', 'B'], 'cpu_100_is_one_core': True}), flush=True)
    initial = {'timestamp': datetime.datetime.now().isoformat(), 'order': ['B', 'A', 'A', 'B'],
               'logical_cpus': os.cpu_count(), 'measurement_seconds': 60, 'warmup_seconds': 20,
               'load_initial': command(['uptime']), 'user_approved_switching': True,
               'other_apps_closed': False, 'binaries_modified': False,
               'workload': 'Fixed Core Animation moving bar on the streamed display; stationary pointer'}
    (OUT / 'protocol.json').write_text(json.dumps(initial, ensure_ascii=False, indent=2))
    results = []
    scene = ROOT / 'build/comparison/comparison-scene'
    if not scene.is_file():
        raise RuntimeError('Compile local-tools/ComparisonScene.swift before testing')
    scene_output = (OUT / 'scene.log').open('w')
    scene_process = subprocess.Popen([str(scene), '4128835'], stdout=scene_output, stderr=subprocess.STDOUT)
    initial['test_scene_pid'] = scene_process.pid
    (OUT / 'protocol.json').write_text(json.dumps(initial, ensure_ascii=False, indent=2))
    try:
        for index, kind in enumerate(['B', 'A', 'A', 'B'], 1):
            results.append(phase(index, kind))
        assert all(r['capture'] == results[0]['capture'] for r in results), 'Different capture configurations'
        assert all(r['codecs'] == results[0]['codecs'] for r in results), 'Different codecs'
        (OUT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(json.dumps({'event': 'experiment_complete', 'output': str(OUT)}), flush=True)
    except BaseException as error:
        (OUT / 'error.json').write_text(json.dumps({'error': str(error), 'completed_trials': len(results)}, indent=2))
        raise
    finally:
        # The participant starts and finishes with the lightweight app.
        try:
            if not app_pid('B') or app_pid('A'):
                switch('B')
        finally:
            # Only remove the temporary scene created by this experiment.
            if scene_process.poll() is None:
                scene_process.terminate()
                try:
                    scene_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            scene_output.close()

if __name__ == '__main__':
    main()
