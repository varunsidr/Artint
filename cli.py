"""Optional command line mode: python cli.py urls.txt"""
import sys
import argparse
from app.extract import extract_article
from app.reports import create_pdf
from app.storage import upsert
from app.capture_quality import ERROR_ACTIONS, failure_details, saved_quality

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Save public articles as reading PDFs.')
    parser.add_argument('urls_file')
    parser.add_argument('--fetch-mode', choices=('auto', 'html'), default='auto')
    args = parser.parse_args()
    with open(args.urls_file, encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.lstrip().startswith('#')]
    for url in urls:
        try:
            article = extract_article(url, mode=args.fetch_mode)
            pdf = create_pdf(article)
            article['pdf_path'] = str(pdf)
            upsert(article)
            print(f"OK {article['title']} -> {pdf}")
            for warning in saved_quality(article)['warnings']:
                print(f"  {warning['severity'].upper()} {warning['code']}: {warning['message']}", file=sys.stderr)
        except Exception as err:
            failure = failure_details(err)
            print(f"FAILED [{failure['code']}] {url}: {failure['message']} {failure['action']}", file=sys.stderr)
