const { parseRich, parseInline } = await import(new URL('../../lib/richText.ts', import.meta.url).href);
let bad = 0;
const ok = (c: boolean, m: string) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) bad++; };
const j = (x: unknown) => JSON.stringify(x);

const doc = parseRich('## Title\n\nHello **bold** and *soft* :star:\n\n- one\n- two\n\n> careful\n> really');
ok(doc[0].t === 'h' && doc[1].t === 'p' && doc[2].t === 'ul' && doc[3].t === 'note', 'headings, paragraphs, lists and notes become blocks');
ok(doc[2].items.length === 2 && doc[3].lines.length === 2, 'consecutive lines group into one list and one note');
ok(j(doc[1].lines[0]).includes('"t":"bold"') && j(doc[1].lines[0]).includes('"t":"italic"') && j(doc[1].lines[0]).includes('"name":"star"'), 'bold, italic and an icon parse inline');
ok(j(parseInline('[site](https://example.com)')) === '[{"t":"link","label":"site","href":"https://example.com"}]', 'an https link stays a link');
ok(j(parseInline('[bad](http://example.com)')) === '[{"t":"text","v":"bad"}]', 'an http link falls back to its label');
ok(j(parseInline('[bad](javascript:alert(1))')).indexOf('href') === -1, 'a script link never becomes a link');
ok(j(parseInline(':notanicon: x')) === '[{"t":"text","v":":notanicon:"},{"t":"text","v":" x"}]', 'an unknown icon stays text');
const html = parseRich('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>');
ok(html.every((b: any) => b.t === 'p') && j(html).includes('<script>'), 'markup is kept as plain text for the renderer to escape');
ok(parseRich('').length === 0 && parseRich('\n\n\n').length === 0, 'empty input gives no blocks');
ok(parseRich('line one\nline two')[0].lines.length === 2, 'single line breaks stay inside a paragraph');
ok(parseRich('*unclosed and **also')[0].lines[0].every((i: any) => i.t === 'text'), 'unbalanced markers are plain text');
if (bad) throw new Error(`${bad} failed`);
