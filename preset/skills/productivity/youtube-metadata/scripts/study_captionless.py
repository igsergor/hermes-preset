#!/usr/bin/env python3
"""Study captionless YouTube videos (Igor-approved pipeline).

download via cookie'd yt-dlp -> 2-min ffmpeg chunks -> muse-spark-1.3-contributor summary per chunk
-> assembled summary file -> delete local copy. Idempotent: IDs with an existing
summary are skipped; a rerun re-downloads only failures.
NOTE: chunks longer than ~3 min hang the model into multi-minute read-timeouts; if you
change CHUNK, also `rm workdir/chunk_*.mp4` so stale longer chunks are not reused.

Usage: python3 study_captionless.py <ids-file> [summaries-dir] [workdir]
Requires: deno in PATH (n-challenge solver), yt-dlp, ffmpeg,
OPENCODE_GO_API_KEY in ~/.hermes/.env (x-opencode-session header is generated per request).
"""
import base64, json, os, subprocess, sys, time, uuid

FFPROFILE = '/home/igor/snap/firefox/common/.mozilla/firefox/20wpd4km.default'
API = 'https://opencode.ai/zen/go/v1/responses'
MODEL = 'muse-spark-1.3-contributor'
CHUNK = 120  # 2 min per chunk: >3-min chunks hang the model into multi-minute timeouts; 2-min answers in ~30 s


def load_key():
    env = os.path.expanduser('~/.hermes/.env')
    for line in open(env):
        line = line.strip()
        if line.startswith('OPENCODE_GO_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise SystemExit('OPENCODE_GO_API_KEY not found in ~/.hermes/.env')


def summarize(path, key, prev=''):
    prompt = ('Подробно перескажи содержание фрагмента: что показано, о чём говорят. '
              '5-8 предложений.')
    if prev:
        prompt += (' Это продолжение видео; предыдущие фрагменты были о: ' + prev[:400] +
                   '. Не пересказывай уже сказанное.')
    b64 = base64.b64encode(open(path, 'rb').read()).decode()
    payload = json.dumps({'model': MODEL, 'max_output_tokens': 4000, 'reasoning': {'effort': 'low'},
                            'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': prompt},
            {'type': 'input_video', 'video_url': 'data:video/mp4;base64,' + b64}]}]})
    out = '/tmp/mimo_resp_%d.json' % os.getpid()
    for attempt in range(5):
        # curl, not urllib: urllib's default UA gets Cloudflare 403 code 1010
        subprocess.run(['curl', '-s', '--max-time', '560', '-X', 'POST', API,
                        '-H', 'Authorization: Bearer ' + key,
                        '-H', 'Content-Type: application/json',
                        '-H', 'x-opencode-session: ' + str(uuid.uuid4()),
                        '-d', '@-', '-o', out],
                       input=payload, text=True, capture_output=True, timeout=570)
        try:
            d = json.load(open(out))
            texts = []
            for o in d.get('output', []):
                for c in o.get('content', []):
                    if c.get('type') == 'output_text':
                        texts.append(c.get('text', ''))
            c = ' '.join(texts).strip()
            if len(c) > 40:  # short content = reasoning ate the budget or empty body
                os.remove(out)
                return c
        except Exception:
            pass
        time.sleep(30)
    try:
        os.remove(out)
    except OSError:
        pass
    return None


def download(vid, workdir):
    mp4 = os.path.join(workdir, vid + '.mp4')
    if os.path.exists(mp4) and os.path.getsize(mp4) > 100000:
        return mp4
    env = dict(os.environ)
    env['PATH'] = env.get('PATH', '') + ':' + os.path.expanduser('~/.deno/bin')
    r = subprocess.run(['yt-dlp', '--js-runtimes', 'deno', '--remote-components', 'ejs:github',
                        '--cookies-from-browser', 'firefox:' + FFPROFILE,
                        '-f', 'mp4[height<=360]/b[height<=360]/b', '--socket-timeout', '30',
                        '-o', mp4, 'https://www.youtube.com/watch?v=' + vid],
                       capture_output=True, text=True, env=env, timeout=900)
    if not os.path.exists(mp4) or os.path.getsize(mp4) < 100000:
        sys.stderr.write((r.stderr or '')[-400:] + '\n')
        return None
    return mp4


def duration(mp4):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', mp4], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def chunk(mp4, idx, workdir):
    cpath = os.path.join(workdir, 'chunk_%s_%d.mp4' % (os.path.basename(mp4)[:-4], idx))
    if os.path.exists(cpath) and os.path.getsize(cpath) > 10000:
        return cpath
    subprocess.run(['ffmpeg', '-y', '-ss', str(idx * CHUNK), '-i', mp4, '-t', str(CHUNK),
                    '-vf', 'scale=480:-2', '-r', '15', '-c:v', 'libx264', '-preset', 'fast',
                    '-crf', '30', '-c:a', 'aac', '-b:a', '48k', cpath],
                   capture_output=True, timeout=600)
    return cpath if os.path.exists(cpath) and os.path.getsize(cpath) > 10000 else None


def process(vid, key, outdir, workdir):
    out = os.path.join(outdir, vid + '.md')
    if os.path.exists(out) and os.path.getsize(out) > 200:
        print(vid, 'уже есть', flush=True)
        return True
    mp4 = download(vid, workdir)
    if not mp4:
        print(vid, 'скачивание не удалось', flush=True)
        return False
    dur = duration(mp4)
    n = max(1, int(dur // CHUNK) + (1 if dur % CHUNK > 30 else 0))
    print(vid, round(dur / 60), 'мин,', n, 'чанков', flush=True)
    parts, prev = [], ''
    for i in range(n):
        c = chunk(mp4, i, workdir)
        if not c:
            print('  чанк', i + 1, 'не нарезался', flush=True)
            continue
        print('  чанк', i + 1, '/', n, flush=True)
        s = summarize(c, key, prev)
        if s:
            ts = '%d:%02d' % (i * CHUNK // 60, (i * CHUNK) % 60)
            parts.append('**[' + ts + ']** ' + s)
            prev = s
        try:
            os.remove(c)
        except OSError:
            pass
        time.sleep(5)
    if not parts:
        print(vid, 'пусто', flush=True)
        return False
    with open(out, 'w') as f:
        f.write('# Автопересказ ' + vid + '\n\n' + '\n\n'.join(parts) + '\n')
    os.remove(mp4)
    print(vid, 'готово:', len(parts), 'частей, локальная копия удалена', flush=True)
    return True


if __name__ == '__main__':
    ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    outdir = sys.argv[2] if len(sys.argv) > 2 else '/tmp/yt_study/summaries'
    workdir = sys.argv[3] if len(sys.argv) > 3 else '/tmp/yt_study'
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(workdir, exist_ok=True)
    key = load_key()
    ok = 0
    for i, vid in enumerate(ids):
        print('===', i + 1, '/', len(ids), vid, flush=True)
        try:
            if process(vid, key, outdir, workdir):
                ok += 1
        except Exception as e:
            print(vid, 'ERR', str(e)[:150], flush=True)
        time.sleep(10)
    print('ИТОГО:', ok, 'из', len(ids), flush=True)
