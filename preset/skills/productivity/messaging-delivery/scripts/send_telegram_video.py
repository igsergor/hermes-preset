#!/usr/bin/env python3
"""
send_telegram_video.py — Send video files to a specific Telegram chat/thread.

Usage:
    python3 send_telegram_video.py file1.mp4 file2.mp4 ...
    python3 send_telegram_video.py --glob "/path/to/output/part_*.mp4"
    python3 send_telegram_video.py --dir /path/to/output/

Requirements:
    pip install python-telegram-bot

Token is read from ~/.hermes/.env (TELEGRAM_BOT_TOKEN=*** find it manually.
"""

import os
import sys
import glob
import asyncio
import pathlib
import argparse

def read_token():
    """Read TELEGRAM_BOT_TOKEN from hermes .env."""
    env_path = pathlib.Path('~/.hermes/.env')
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    # Fallback: environment variable
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in ~/.hermes/.env or environment")
        sys.exit(1)
    return token

async def send_videos(files, chat_id, thread_id, caption_template, dry_run, delay):
    """Send video files to Telegram."""
    from telegram import Bot
    from telegram.request import HTTPXRequest

    TOKEN = read_token()
    
    request = HTTPXRequest(
        connection_pool_size=1,
        read_timeout=300,
        write_timeout=300,
        connect_timeout=60,
    )
    bot = Bot(token=TOKEN, request=request)
    
    total = len(files)
    print(f"Found {total} files to send")
    print(f"Chat: {chat_id}, Thread: {thread_id}")
    
    for i, filepath in enumerate(files):
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        name = os.path.basename(filepath)
        
        if size_mb > 50:
            print(f"  SKIP {name} ({size_mb:.1f}MB) — exceeds 50MB Telegram Bot API limit!")
            continue
        
        caption = caption_template.format(i=i+1, total=total, name=name)
        
        if dry_run:
            print(f"  [DRY RUN] Would send {name} ({size_mb:.1f}MB)")
            continue
        
        print(f"  [{i+1}/{total}] Sending {name} ({size_mb:.1f}MB)...")
        
        try:
            with open(filepath, 'rb') as f:
                await bot.send_video(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    video=f,
                    caption=caption,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60,
                )
            print(f"    OK!")
        except Exception as e:
            print(f"    ERROR: {e}")
            if "Too Large" in str(e):
                print(f"    File is too large — re-encode with lower bitrate")
        
        if delay > 0 and i < total - 1:
            await asyncio.sleep(delay)
    
    print(f"\nDone! {total} files processed.")

def main():
    parser = argparse.ArgumentParser(description='Send video files to Telegram')
    parser.add_argument('files', nargs='*', help='Video files to send')
    parser.add_argument('--glob', help='Glob pattern for files (e.g., "output/part_*.mp4")')
    parser.add_argument('--dir', help='Directory — send all .mp4 files sorted')
    parser.add_argument('--chat', default='-1003961189874', help='Chat ID (default: GroupHermes1)')
    parser.add_argument('--thread', type=int, default=None, help='Thread ID (for group topics)')
    parser.add_argument('--caption', default='🎬 Part {i}/{total} — {name}', help='Caption template')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between sends in seconds (default: 1.0)')
    parser.add_argument('--dry-run', action='store_true', help='Just list files without sending')
    
    args = parser.parse_args()
    
    files = []
    if args.files:
        files = sorted(args.files)
    elif args.glob:
        files = sorted(glob.glob(args.glob))
    elif args.dir:
        files = sorted(glob.glob(os.path.join(args.dir, '*.mp4')))
    else:
        print("ERROR: Provide files, --glob, or --dir")
        parser.print_help()
        sys.exit(1)
    
    if not files:
        print("No files found!")
        sys.exit(1)
    
    print(f"Mode: {'DRY RUN' if args.dry_run else 'SEND'}")
    for f in files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        status = "OK" if size_mb <= 50 else "TOO LARGE"
        print(f"  {os.path.basename(f)} ({size_mb:.1f}MB) [{status}]")
    print()
    
    asyncio.run(send_videos(
        files=files,
        chat_id=args.chat,
        thread_id=args.thread,
        caption_template=args.caption,
        dry_run=args.dry_run,
        delay=args.delay,
    ))

if __name__ == '__main__':
    main()
