"""Recompute and verify published results without launching any applications."""
from pathlib import Path
import json
import math
import statistics

DATA = Path(__file__).resolve().parent.parent / 'results/2026-11-04-usb-baab'


def read(name):
    return json.loads((DATA / name).read_text())


def close(actual, expected, label):
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9):
        raise ValueError(f'{label}: computed {actual}, recorded {expected}')


def main():
    trials = []
    for path in sorted(DATA.glob('trial-*.json')):
        trial = read(path.name)
        recorded = trial['summary']
        samples = trial['snapshots']
        first, last = samples[0], samples[-1]
        duration = last['elapsed'] - first['elapsed']
        ticks = [(b - a) & 0xffffffff for a, b in zip(first['cpu_ticks'], last['cpu_ticks'])]
        cpu_ns = sum(last['usage'][k] - first['usage'][k] for k in ['ri_user_time', 'ri_system_time'])
        vm = trial['vm_delta']
        computed = {
            'duration_s': duration,
            'app_cpu_percent': cpu_ns / 1e9 / duration * 100,
            'app_footprint_mib': statistics.mean(s['usage']['ri_phys_footprint'] / 1048576 for s in samples),
            'app_resident_mib': statistics.mean(s['usage']['ri_resident_size'] / 1048576 for s in samples),
            'system_cpu_percent': 100 * (ticks[0] + ticks[1] + ticks[3]) / sum(ticks),
            'swapin_mib': vm['swapins'] * vm['page_size_bytes'] / 1048576,
            'swapout_mib': vm['swapouts'] * vm['page_size_bytes'] / 1048576,
            'receiver_samples': len(trial['receiver_stats']),
        }
        for key in ['fps', 'capFps', 'enc50', 'e2e50', 'e2e95', 'rtt', 'cur', 'curLost']:
            computed[key + '_mean'] = statistics.mean(r[key] for r in trial['receiver_stats'])
        for key, value in computed.items():
            close(value, recorded[key], f'{path.name}:{key}')
        if recorded['transports'] != ['USB'] or recorded['codecs'] != ['H.264']:
            raise ValueError('Unexpected transport or codec')
        trials.append(recorded)
    if trials != read('results.json') or [t['kind'] for t in trials] != ['B', 'A', 'A', 'B']:
        raise ValueError('Trial list or order differs')
    summary = read('summary.json')
    groups = {}
    for name, kind in [('normal', 'A'), ('light', 'B')]:
        selected = [t for t in trials if t['kind'] == kind]
        total = sum(t['duration_s'] for t in selected)
        group = {}
        for key, expected in summary[name].items():
            if key == 'runs':
                close(len(selected), expected, name + ':runs')
            elif key == 'cpu_range':
                observed = [min(t['app_cpu_percent'] for t in selected), max(t['app_cpu_percent'] for t in selected)]
                for a, b in zip(observed, expected):
                    close(a, b, name + ':cpu_range')
            else:
                group[key] = sum(t[key] * t['duration_s'] for t in selected) / total
                close(group[key], expected, name + ':' + key)
        groups[name] = group
    normal, light = groups['normal'], groups['light']
    differences = {
        'cpu_reduction_percent': (1 - light['app_cpu_percent'] / normal['app_cpu_percent']) * 100,
        'cpu_percentage_point_reduction': normal['app_cpu_percent'] - light['app_cpu_percent'],
        'fps_increase_percent': (light['fps_mean'] / normal['fps_mean'] - 1) * 100,
        'footprint_difference_mib': light['app_footprint_mib'] - normal['app_footprint_mib'],
        'system_cpu_difference_points': light['system_cpu_percent'] - normal['system_cpu_percent'],
    }
    for key, value in differences.items():
        close(value, summary[key], key)
    print('Verified all 4 trials, both aggregate groups, and reported differences.')
    print(json.dumps(differences, indent=2))


if __name__ == '__main__':
    main()
