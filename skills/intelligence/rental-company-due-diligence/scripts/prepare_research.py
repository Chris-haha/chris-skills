#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare public-company search routes. Does not fetch or assess any source."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode


ENGINES = {
    '360': ('https://www.so.com/s', 'q'),
    'baidu': ('https://www.baidu.com/s', 'wd'),
    'sogou': ('https://www.sogou.com/web', 'query'),
    'bing': ('https://cn.bing.com/search', 'q'),
}


def prepare(name, city='', credit_code='', former_names=(), engines=('360', 'baidu', 'bing')):
    names = list(dict.fromkeys(n.strip() for n in [name, *former_names] if n.strip()))
    if not name.strip():
        raise ValueError('Company name must not be empty')
    if any(not e or e not in ENGINES for e in engines):
        raise ValueError('Supported engines: ' + ', '.join(ENGINES))
    queries = []
    for alias in names:
        anchor = ' '.join(part for part in [city.strip(), json.dumps(alias, ensure_ascii=False)] if part)
        for purpose, suffix in [('identity', ''), ('refund', '押金 退款 投诉'),
                                ('official-records', '经营异常 判决 执行 备案'),
                                ('follow-up', '已退 履行 结案 移出 整改 回应')]:
            queries.append({'id': 'Q' + str(len(queries) + 1), 'purpose': purpose,
                            'query': (anchor + ' ' + suffix).strip()})
    if credit_code.strip():
        queries.append({'id': 'Q' + str(len(queries) + 1), 'purpose': 'identity',
                        'query': credit_code.strip()})
    routes = []
    for engine in dict.fromkeys(engines):
        base, parameter = ENGINES[engine]
        for query in queries:
            routes.append({'query_id': query['id'], 'query': query['query'],
                           'engine': engine, 'backend_family': engine,
                           'url': base + '?' + urlencode({parameter: query['query']}),
                           'status': 'planned'})
    return {'generated_at': datetime.now(timezone.utc).isoformat(),
            'subject': {'names': names, 'city': city.strip(), 'credit_code': credit_code.strip()},
            'collection_performed': False, 'queries': queries, 'routes': routes,
            'note': 'Routes are starting points, not executed queries or independent evidence. '
                    'Inspect results, split over-specific queries, and record access limits separately.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--city', default='')
    parser.add_argument('--credit-code', default='')
    parser.add_argument('--former-name', action='append', default=[])
    parser.add_argument('--engines', default='360,baidu,bing', help='Comma-separated engine names')
    parser.add_argument('--output', type=Path, help='New JSON file; existing files are never overwritten')
    args = parser.parse_args()
    try:
        plan = prepare(args.name, args.city, args.credit_code, args.former_name,
                       [e.strip() for e in args.engines.split(',')])
        content = json.dumps(plan, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as handle:
                handle.write(content)
        else:
            print(content, end='')
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
