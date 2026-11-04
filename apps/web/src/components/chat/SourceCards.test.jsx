import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import SourceCards from './SourceCards.jsx';

describe('answer citations', () => {
  it('renders the source URL and license, and escapes source-provided text', () => {
    const html = renderToStaticMarkup(<SourceCards sources={[{ id: 'k:p01:0', title: '<img src=x onerror=alert(1)>', url: 'https://example.org/source', license: 'CC BY-SA 4.0' }]} />);
    expect(html).toContain('href="https://example.org/source"');
    expect(html).toContain('CC BY-SA 4.0');
    expect(html).toContain('k:p01:0');
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
  });
  it('keeps source text but never turns unsafe URLs into links', () => {
    const html = renderToStaticMarkup(<SourceCards sources={[{ title: 'Source', url: 'javascript:alert(1)', license: null }]} />);
    expect(html).toContain('Source');
    expect(html).toContain('ไม่ระบุ');
    expect(html).not.toContain('href=');
  });
});
