#!/usr/bin/env python3
"""Static checks for nova-agent/index.html (single-file 3D landing)."""
import re, sys, html.parser

ROOT = __file__.rsplit('/', 2)[0]
page = open(f'{ROOT}/nova-agent/index.html').read()
fails = []
def check(name, ok):
    print(('PASS' if ok else 'FAIL'), 'nova has', name)
    if not ok: fails.append(name)

PRESENT = [
    ('title', '<title>Nova Agent'),
    ('topbar', 'Nova Agent V1 Is Here'),
    ('nav grid', 'grid-template-columns:17% 1fr 12% 17%'),
    ('launch button', 'LAUNCH NOVA'),
    ('rail', 'id="railtag"'),
    ('14 rail dots', None),
    ('intro section', 'id="intro"'),
    ('typing box', 'id="typed"'),
    ('prompt 1', 'token named NOVA on Ethereum'),
    ('prompt 4', 'market sentiment on BTC'),
    ('feature rows', 'MARKET ANALYSIS'),
    ('headline Thinking', '>Thinking<'),
    ('headline Machines', '>Machines<'),
    ('product section', 'id="product"'),
    ('tab strip', 'id="track"'),
    ('tab label', 'Smart-contract auditor'),
    ('gateway', 'Your Gateway'),
    ('reviews section', 'id="reviews"'),
    ('reviewer 1', 'Ilan Brooks'),
    ('reviewer 3', 'Mara Elling'),
    ('ghost', 'id="qghost"'),
    ('arrows', 'id="qprev"'),
    ('avatar svg', '<span class="ava"'),
    ('footer', 'NOVA AGENT &middot; 2026'),
    ('importmap', 'unpkg.com/three@0.160.0'),
    ('RoundedBoxGeometry import', 'geometries/RoundedBoxGeometry.js'),
    ('RoomEnvironment import', 'environments/RoomEnvironment.js'),
    ('robot pedestal', 'BoxGeometry(1.7, 1.6, 1.7)'),
    ('face ring', 'frameGeo(1.5, 1.44'),
    ('blink', 'nextBlink'),
    ('quote mode', "want !== faceMode"),
    ('camera states', 'z0:11.6'),
    ('mobile rules', '@media (max-width:900px)'),
    ('error overlay', 'id="err"'),
]
for name, needle in PRESENT:
    if needle is None: continue
    check(name, needle in page)
rail = page[page.find('<aside class="rail"'):page.find('</aside>')]
check('14 rail dots', rail.count('<i></i>') == 14)
check('4 embedded fonts', page.count('data:font/woff2;base64,') == 4)
check('no font placeholders', '__FONT_' not in page)
check('3 sections', len(re.findall(r'<section id=', page)) == 3)
check('no test hooks', 'window.__' not in page)

class P(html.parser.HTMLParser):
    VOID = {'meta','link','br','hr','img','input','line','circle','rect','path','stop'}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.stack=[]; self.errs=[]
    def handle_starttag(self, t, a):
        if t not in self.VOID: self.stack.append((t, self.getpos()))
    def handle_startendtag(self, t, a): pass
    def handle_endtag(self, t):
        if t in self.VOID: return
        if self.stack and self.stack[-1][0]==t: self.stack.pop()
        else: self.errs.append(f'{t} closes {self.stack[-1] if self.stack else None} at {self.getpos()}')
p = P(); p.feed(page)
check('tags balanced', not p.errs and not p.stack)
for e in p.errs[:5]: print('  TAG', e)
if p.stack: print('  OPEN', p.stack[:5])

urls = sorted(set(re.findall(r'https?://[^"\' )]+', page)))
print('external urls:', urls)
check('only unpkg external', all(u.startswith('https://unpkg.com/three@0.160.0/') for u in urls))

mods = re.findall(r'<script type="module">(.*?)</script>', page, re.S)
plain = re.findall(r'<script>(.*?)</script>', page, re.S)
open('/tmp/nova_check.mjs','w').write(mods[0] if mods else '')
open('/tmp/nova_classic.js','w').write(plain[0] if plain else '')
check('one module script', len(mods) == 1)
check('one classic script', len(plain) == 1)
print(f'\n{len(fails)} failure(s)')
sys.exit(1 if fails else 0)
