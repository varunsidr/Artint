"""Explicit, bounded downloads for a large library."""
import csv
import io
import re
import zipfile
from pathlib import Path

from app.storage import metadata_rows

MAX_CSV_BYTES = 25 * 1024 * 1024
MAX_ZIP_INPUT_BYTES = 50 * 1024 * 1024


def pdf_download_name(article):
    slug = re.sub(r'[^\w-]+', '-', article['title'], flags=re.UNICODE).strip('-')[:100]
    return f'{slug or article["id"]}.pdf'


def metadata_csv(*, sort='Newest saved', **filters):
    fields = ['id', 'url', 'title', 'source', 'author', 'published', 'fetched_at', 'word_count']
    output = io.BytesIO()
    line = io.StringIO(newline='')
    writer = csv.DictWriter(line, fieldnames=fields)
    writer.writeheader()
    output.write(line.getvalue().encode('utf-8-sig'))
    for row in metadata_rows(sort=sort, **filters):
        line.seek(0)
        line.truncate()
        # Keep publisher-controlled strings from becoming spreadsheet formulas.
        safe = {key: ("'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value)
                for key, value in row.items()}
        writer.writerow(safe)
        encoded = line.getvalue().encode('utf-8')
        if output.tell() + len(encoded) > MAX_CSV_BYTES:
            raise ValueError('This CSV exceeds 25 MB. Narrow the publisher or search filter and try again.')
        output.write(encoded)
    return output.getvalue()


def page_pdf_zip(articles):
    if len(articles) > 100:
        raise ValueError('Export up to 100 reading copies in one batch.')
    files, total = [], 0
    for article in articles:
        path = Path(article['pdf_path']) if article.get('pdf_path') else None
        if path and path.is_file():
            total += path.stat().st_size
            files.append((article, path))
    if not files:
        raise ValueError('No saved PDFs are available on this page.')
    if total > MAX_ZIP_INPUT_BYTES:
        raise ValueError('These PDFs exceed 50 MB. Choose a smaller page size before exporting.')
    output = io.BytesIO()
    read_bytes = 0
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for article, path in files:
            with path.open('rb') as source, archive.open(f'{article["id"]}/{pdf_download_name(article)}', 'w') as target:
                while chunk := source.read(64 * 1024):
                    read_bytes += len(chunk)
                    if read_bytes > MAX_ZIP_INPUT_BYTES:
                        raise ValueError('These PDFs exceed 50 MB. Choose a smaller page size before exporting.')
                    target.write(chunk)
    return output.getvalue(), len(files)
