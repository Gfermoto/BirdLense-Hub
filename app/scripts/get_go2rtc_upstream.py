#!/usr/bin/env python3
"""Extract Go2RTC upstream (host:port) from env or config. For nginx proxy."""
import os
import yaml

def main():
    url = os.environ.get('GO2RTC_URL', '').strip()
    if not url:
        for path in ('/app/app_config/user_config.yaml', '/app/app_config/default_config.yaml'):
            try:
                with open(path) as f:
                    c = yaml.safe_load(f) or {}
                url = (c.get('video') or {}).get('go2rtc_url', '')
                if url:
                    break
            except Exception:
                pass
    if url:
        url = url.replace('https://', '').replace('http://', '').rstrip('/').split('/')[0]
        print(url)
    else:
        # Не задан — nginx будет проксировать на несуществующий хост
        print('127.0.0.1:1984')

if __name__ == '__main__':
    main()
