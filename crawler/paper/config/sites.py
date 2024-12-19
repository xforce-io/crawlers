"""站点配置"""

SITES = {
    'arxiv': {
        'domain': 'arxiv.org',
        'name': 'arxiv',
        'enabled': True,
        'start_url': 'https://arxiv.org/list/cs.AI/recent?skip=0&show=50',
        'max_pages': 10,
        'page_size': 50,
        'selectors': {
            'title': 'div.list-title',
            'authors': 'div.list-authors',
            'abstract': 'div.abstract',
        }
    },
    'huggingface': {
        'domain': 'huggingface.co',
        'name': 'huggingface',
        'enabled': True,
        'start_url': 'https://huggingface.co/papers',
        'max_pages': 10,
        'page_size': 20,
        'selectors': {
            'title': 'h3 a.line-clamp-3',
            'authors': 'div.author-info',
            'abstract': 'p.text-gray-700',
        }
    },
    'paperswithcode': {
        'domain': 'paperswithcode.com',
        'name': 'paperswithcode',
        'enabled': True,
        'start_url': 'https://paperswithcode.com/latest',
        'max_pages': 10,
        'page_size': 20,
        'selectors': {
            'title': 'div.paper-title',
            'authors': 'div.author-name',
            'abstract': 'div.paper-abstract',
        }
    }
}