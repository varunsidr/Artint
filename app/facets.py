"""Inspectable text signals, not sentiment scores or financial predictions."""
import re

FACET_VERSION = 'ai-coverage-1'
LENSES = [
    {'id': 'spending', 'label': 'Infrastructure & spending', 'short': 'Infrastructure',
     'pattern': r'\b(capex|capital expenditure\w*|capital spending|data cent(?:er|re)s?|hyperscalers?|build[- ]out|infrastructure spend\w*)\b'},
    {'id': 'valuations', 'label': 'Valuations & funding', 'short': 'Valuations',
     'pattern': r'\b(valuation\w*|overvalu\w*|price[- ]to[- ]earnings|p/e|venture capital|funding rounds?|market cap\w*|earnings multiples?)\b'},
    {'id': 'returns', 'label': 'Revenue & real-world returns', 'short': 'Revenue & returns',
     'pattern': r'\b(revenues?|monetiz\w*|monetis\w*|return on investment|ROI|profitabil\w*|cash flows?|enterprise adoption|productivity)\b'},
    {'id': 'credit', 'label': 'Debt & circular financing', 'short': 'Debt & financing',
     'pattern': r'\b(circular financ\w*|vendor financ\w*|debt|credit|leverage|loans?|bond issuance|securiti[sz]\w*)\b'},
    {'id': 'capacity', 'label': 'Power & capacity constraints', 'short': 'Power & capacity',
     'pattern': r'\b(electricity|energy demand|power demand|power supply|power grid|gigawatts?|megawatts?|cooling|capacity constraints?|oversupply|overcapacity)\b'},
    {'id': 'history', 'label': 'Dot-com & historical parallels', 'short': 'Historical parallels',
     'pattern': r'\b(dot[- .]?com|dotcom|1999|telecom bubble|railway mania|railroad bubble|technology bubbles?|speculative bubbles?)\b'},
]
ENTITIES = {
    'OpenAI': r'\b(openai|chatgpt)\b', 'Nvidia': r'\b(nvidia|nvda)\b',
    'Microsoft': r'\b(microsoft|msft|azure)\b', 'Alphabet': r'\b(alphabet|google|googl)\b',
    'Amazon': r'\b(amazon|aws|amzn)\b', 'Meta': r'\b(meta|facebook)\b',
    'Anthropic': r'\b(anthropic|claude)\b', 'Oracle': r'\b(oracle|orcl)\b',
    'SoftBank': r'\bsoftbank\b', 'AMD': r'\b(amd|advanced micro devices)\b',
    'CoreWeave': r'\bcoreweave\b', 'xAI': r'\b(xai|grok)\b',
}
CONCERNS = re.compile(r'\b(overvalu\w*|unsustainable|overinvest\w*|overcapacity|speculative|circular financing|bubble burst\w*|debt burden|investment risks?)\b', re.I)
COUNTERCASE = re.compile(r'\b(not (?:an? )?bubble|no (?:AI )?bubble|different (?:from|to) (?:the )?dot[- ]com|strong (?:earnings|fundamentals|cash flow)|real (?:revenues?|demand|adoption)|productivity gains?|revenue growth)\b', re.I)


def readable_text(text):
    text = re.sub(r'!?\[([^\]]*)\]\(https?://[^\s)]+\)', r'\1', text)
    return re.sub(r'https?://\S+', '', text)


def _preview(text, position):
    start = max(text.rfind('\n', 0, position), text.rfind('. ', 0, position)) + 1
    if position - start > 140:
        start = max(0, position - 100)
        next_space = text.find(' ', start)
        start = next_space + 1 if next_space >= 0 else start
    end = min(len(text), start + 330)
    value = text[start:end].strip()
    return ('…' if start else '') + value + ('…' if end < len(text) else '')


def extract_facets(article):
    text = readable_text(article.get('text', ''))
    headline = article.get('title', '')
    combined = headline + '\n' + text
    lenses, evidence = [], {}
    for lens in LENSES:
        match = re.search(lens['pattern'], combined, re.I)
        if match:
            lenses.append(lens['id'])
            body_match = re.search(lens['pattern'], text, re.I)
            evidence[lens['id']] = _preview(text, body_match.start()) if body_match else headline
    concerns, countercase = CONCERNS.search(text), COUNTERCASE.search(text)
    return {
        'lenses': lenses, 'evidence': evidence,
        'entities': [name for name, pattern in ENTITIES.items() if re.search(pattern, combined, re.I)],
        'concern': _preview(text, concerns.start()) if concerns else '',
        'countercase': _preview(text, countercase.start()) if countercase else '',
        'bubble': bool(re.search(r'\b(bubble|bubbles|overvalu\w*)\b', combined, re.I)),
    }
