#!/usr/bin/env python3
"""Extract Go2RTC upstream (host:port) from env or config. For nginx proxy."""
import os
import yaml

def main():
    url = os.environ.get('GO2RTC_URL', '').strip()
    config_dir = os.environ.get('APP_CONFIG_DIR', '/app/app_config')
    if not url:
        for name in ('user_config.yaml', 'default_config.yaml'):
            path = os.path.join(config_dir, name)
            try:
                with open(path) as f:
                    c = yaml.safe_load(f) or {}
                url = (c.get('video') or {}).get('go2rtc_url', '')
                if url:
                    break
            except (OSError, yaml.YAMLError):
                pass
    if url:
        url = url.replace('https://', '').replace('http://', '').rstrip('/').split('/')[0]
        print(url)
    else:
        # Не задан — nginx будет проксировать на несуществующий хост
        print('127.0.0.1:1984')

if __name__ == '__main__':
    main()
