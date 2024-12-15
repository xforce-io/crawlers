SITES = {
    'huggingface': {
        'domain': 'huggingface.co',
        'start_url': 'https://huggingface.co/papers',
        'selectors': {
            'date': 'meta[property="article:published_time"]',
            'date_format': '%Y-%m-%dT%H:%M:%S.000Z',
            'title': 'h1',
            'content': '.paper-abstract',
            'author': '.author-name'
        },
        'content_selectors': ['.paper-abstract']
    },
    'paperswithcode': {
        'domain': 'paperswithcode.com',
        'start_url': 'https://paperswithcode.com/latest',
        'selectors': {
            'date': 'span.author-span',
            'date_format': '%d %b %Y',
            'title': 'h1',
            'content': '.paper-abstract',
            'author': '.author-name'
        },
        'content_selectors': ['.paper-abstract']
    }
}