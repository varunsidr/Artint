export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component;
  const root = parentElement.querySelector('#observatory');
  if (!root || !data || !data.snapshot) return;
  const incoming = Number(data.request || 0);
  if (root._request && incoming < root._request) return;
  // The renderer retains the returned disposer until unmount. Dispose the
  // previous render here too, so repeated updates cannot accumulate handlers.
  root._dispose?.();
  root._request = incoming;
  root._filters = { ...data.filters, page: data.snapshot.page };
  root._view = data.snapshot;
  const view = data.snapshot;
  const investment = view.mode === 'investment';
  root.dataset.mode = view.mode;
  const abort = new AbortController();
  const frames = new Set();
  const timers = new Set();
  const objectUrls = new Set();
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const q = selector => root.querySelector(selector);
  const focused = root.getRootNode().activeElement;
  const focusToken = focused && root.contains(focused) ? {
    id: focused.id, lens: focused.dataset.lens, entity: focused.dataset.entity,
    month: focused.dataset.month, source: focused.dataset.source, matrix: focused.dataset.matrix,
    topic: focused.dataset.topic, status: focused.dataset.status,
  } : null;
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const svg = (tag, attrs = {}) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    return node;
  };
  const on = (node, type, handler) => node.addEventListener(type, handler, { signal: abort.signal });
  const count = value => Number(value || 0).toLocaleString('en-US');
  const date = value => {
    if (!value) return 'Date unavailable';
    const parsed = new Date(String(value).slice(0, 10) + 'T12:00:00Z');
    return Number.isNaN(parsed.valueOf()) ? 'Date unavailable' : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  };
  const monthLabel = value => new Date(value + (value.length === 10 ? '' : '-01') + 'T12:00:00Z').toLocaleDateString('en-GB',
    value.length === 10 ? { day: 'numeric', month: 'short', timeZone: 'UTC' } : { month: 'short', year: '2-digit', timeZone: 'UTC' });
  const lensById = new Map(view.lenses.map(lens => [lens.id, lens]));
  const lensTones = { spending: 'blue', valuations: 'purple', returns: 'teal', credit: 'amber', capacity: 'clay', history: 'slate' };
  const lensColor = id => `var(--tone-${lensTones[id] || 'slate'})`;
  const percent = amount => view.stats.articles ? Math.round(amount / view.stats.articles * 100) : 0;
  const tooltip = q('#chart-tooltip');
  let tooltipTarget, dismissedTarget;
  const hideTooltip = () => {
    tooltipTarget?.removeAttribute('aria-describedby');
    tooltipTarget = null; tooltip.hidden = true;
  };
  const showTooltip = target => {
    const details = target?._tooltip;
    if (!details || !target.isConnected) { hideTooltip(); return; }
    if (target === dismissedTarget) return;
    dismissedTarget = null;
    tooltipTarget?.removeAttribute('aria-describedby');
    tooltipTarget = target;
    tooltip.querySelector('.obs-tooltip-label').textContent = details.label;
    tooltip.querySelector('strong').textContent = details.value;
    tooltip.querySelector('p').textContent = details.detail;
    tooltip.querySelector('small').textContent = details.hint;
    target.setAttribute('aria-describedby', 'chart-tooltip');
    tooltip.hidden = false;
    const anchor = (target.querySelector('.month-point') || target).getBoundingClientRect();
    const bounds = root.getBoundingClientRect();
    const width = tooltip.offsetWidth, height = tooltip.offsetHeight;
    const left = Math.min(Math.max(10, anchor.left + anchor.width / 2 - bounds.left - width / 2), Math.max(10, bounds.width - width - 10));
    const above = anchor.top - height - 12;
    tooltip.style.left = left + 'px';
    tooltip.style.top = (above >= 8 ? above : anchor.bottom + 12) - bounds.top + 'px';
  };
  const describe = (node, details) => { node.dataset.tooltip = 'true'; node._tooltip = details; };
  const hoverTarget = target => target?.closest?.('[data-tooltip]');
  on(root, 'pointerover', event => { const target = hoverTarget(event.target); if (target) showTooltip(target); });
  on(root, 'pointermove', event => {
    const target = hoverTarget(event.target);
    if (target && (tooltip.hidden || target !== tooltipTarget)) showTooltip(target);
  });
  on(root, 'pointerout', event => {
    const next = hoverTarget(event.relatedTarget);
    if (hoverTarget(event.target) === dismissedTarget && next !== dismissedTarget) dismissedTarget = null;
    if (next !== tooltipTarget) hideTooltip();
  });
  on(root, 'focusin', event => {
    const target = hoverTarget(event.target);
    if (target && target.matches(':focus-visible')) showTooltip(target);
  });
  on(root, 'focusout', () => { dismissedTarget = null; hideTooltip(); });
  on(root, 'pointerdown', hideTooltip);
  // A hovered mark may not own keyboard focus, so dismissal must also work
  // while focus remains on a native Streamlit control outside the shadow root.
  on(document, 'keydown', event => {
    if (event.key === 'Escape') { dismissedTarget = tooltipTarget; hideTooltip(); }
  });
  document.addEventListener('scroll', () => {
    const frame = requestAnimationFrame(() => {
      if (!tooltipTarget) return;
      const bounds = tooltipTarget.getBoundingClientRect();
      if (bounds.bottom <= 0 || bounds.top >= window.innerHeight) hideTooltip();
      else showTooltip(tooltipTarget);
    });
    frames.add(frame);
  }, { capture: true, signal: abort.signal });
  const reconcile = (container, nodes) => {
    nodes.forEach((node, index) => {
      if (container.children[index] !== node) container.insertBefore(node, container.children[index] || null);
    });
    while (container.children.length > nodes.length) container.lastElementChild.remove();
  };
  const animate = (duration, update) => {
    if (reduced || duration === 0) { update(1); return; }
    const start = performance.now();
    const step = now => {
      const progress = Math.min(1, (now - start) / duration);
      update(1 - Math.pow(1 - progress, 3));
      if (progress < 1) { const id = requestAnimationFrame(step); frames.add(id); }
    };
    const id = requestAnimationFrame(step); frames.add(id);
  };
  const counter = (selector, value) => {
    const node = q(selector), from = Number(node.dataset.value || 0), to = Number(value || 0);
    if (from === to) { node.textContent = count(to); return; }
    animate(360, progress => {
      const current = Math.round(from + (to - from) * progress);
      node.textContent = count(current); node.dataset.value = String(current);
    });
  };
  for (const [name, value] of Object.entries(data.colors || {})) root.style.setProperty('--' + name, value);
  root.style.colorScheme = data.theme || 'light';
  root.setAttribute('aria-busy', 'false');
  root.dataset.ready = 'true';
  root.dataset.total = String(view.stats.articles);
  q('#updating').hidden = true;

  const commit = (patch, reset = true) => {
    const next = { ...root._filters, ...patch };
    if (reset) next.page = 1;
    root._request += 1;
    next._request = root._request;
    root._filters = next;
    root.setAttribute('aria-busy', 'true');
    q('#updating').hidden = false;
    setStateValue('filters', next);
  };
  const chooseOptions = (select, values, selected) => {
    const signature = JSON.stringify(values);
    if (select.dataset.options !== signature) {
      select.replaceChildren(...values.map(value => {
        const option = make('option', '', value.label);
        option.value = value.value;
        return option;
      }));
      select.dataset.options = signature;
    }
    select.value = selected;
  };
  chooseOptions(q('#collection'), data.collections.map(row => ({ value: row.id, label: row.title + ' · ' + count(row.articles) })), root._filters.collection);
  chooseOptions(q('#publisher'), [{ value: '', label: 'All publishers' }, ...view.sources.map(source => ({ value: source, label: source }))], root._filters.source);
  q('#period').value = root._filters.period;
  q('#analysis-mode').value = view.mode;
  on(q('#analysis-mode'), 'change', event => commit({ mode: event.target.value, lens: '', entity: '', topic: '', status: 'All articles' }));
  const activeElement = root.getRootNode().activeElement || document.activeElement;
  if (activeElement !== q('#query')) q('#query').value = root._filters.query;
  on(q('#collection'), 'change', event => commit({ collection: event.target.value, source: '', lens: '', entity: '', month: '', day: '', topic: '', status: 'All articles', query: '' }));
  on(q('#publisher'), 'change', event => commit({ source: event.target.value }));
  on(q('#period'), 'change', event => commit({ period: event.target.value, month: '', day: '' }));
  let typing;
  on(q('#query'), 'input', event => {
    const value = event.target.value;
    clearTimeout(typing);
    typing = setTimeout(() => commit({ query: value }), 260); timers.add(typing);
  });
  on(q('#query'), 'keydown', event => {
    if (event.key === 'Enter') { clearTimeout(typing); commit({ query: event.target.value }); }
  });
  on(q('#refresh'), 'click', () => {
    root.setAttribute('aria-busy', 'true'); q('#updating').hidden = false;
    setTriggerValue('refresh', String(Date.now()));
  });
  on(q('#export'), 'click', () => setTriggerValue('export', String(Date.now())));
  const notes = q('#collection-notes');
  on(q('#notes-button'), 'click', () => {
    notes.hidden = !notes.hidden;
    q('#notes-button').setAttribute('aria-expanded', String(!notes.hidden));
  });
  const selectedCollection = data.collections.find(row => row.id === root._filters.collection);
  q('#collection-title').textContent = selectedCollection && selectedCollection.id ? selectedCollection.title : 'Your sources, connected.';
  const ranked = [...view.lenses].sort((a, b) => b.count - a.count);
  q('#brief').textContent = view.stats.articles ? investment ?
    `${count(view.stats.articles)} articles from ${count(view.stats.publishers)} publishers. ${ranked[0].short} appears in ${count(ranked[0].count)} of them${ranked[1].count ? `; ${ranked[1].short.toLowerCase()} in ${count(ranked[1].count)}` : ''}. Explore a lens or company to inspect the sources behind those counts.` :
    `${count(view.stats.articles)} articles from ${count(view.stats.publishers)} publishers. ${count(view.stats.analyzed)} have a current saved analysis; ${count(view.stats.articles - view.stats.analyzed)} are waiting for analysis. Explore publication activity, topics and publishers to focus the sources.` :
    'No articles match this selection. Clear a filter or try a broader search.';
  counter('#metric-articles', view.stats.articles);
  counter('#metric-publishers', view.stats.publishers);
  counter('#metric-bubble', investment ? view.stats.bubble : view.stats.analyzed);
  q('#metric-third-label').textContent = investment ? 'Bubble language' : 'Analyzed articles';
  q('#metric-third-note').textContent = investment ? 'Articles mentioning the debate' : 'Current saved analyses · qwen3:8b';
  q('#metric-articles-note').textContent = selectedCollection ? 'of ' + count(selectedCollection.articles) + ' in this collection' : '';
  const total = view.stats.articles, health = view.health, momentum = health.momentum;
  const share = (amount, denominator = total) => denominator ? Math.round(amount / denominator * 100) + '%' : '—';
  counter('#recent-volume', momentum.current);
  const change = momentum.previous ? Math.round((momentum.current - momentum.previous) / momentum.previous * 100) : null;
  q('#recent-comparison').textContent = change === null ?
    `${count(momentum.previous)} in the prior 30 days · no percentage baseline` :
    `${change > 0 ? '+' : ''}${change}% vs ${count(momentum.previous)} in the prior 30 days`;
  q('#recent-window').textContent = `${date(momentum.start)} – ${date(momentum.end)} · within current filters`;
  const leading = view.publishers[0];
  q('#leading-share').textContent = leading ? share(leading.count) : '—';
  q('#leading-publisher').textContent = leading ? `${leading.name} · ${count(leading.count)} articles` : 'No publishers in this selection';
  q('#concentration-note').textContent = total ? `Top ${Math.min(3, view.stats.publishers)} publishers account for ${share(view.publishers.slice(0, 3).reduce((sum, row) => sum + row.count, 0))} of saved articles` : 'Based on saved publisher labels';
  q('#analysis-share').textContent = share(view.stats.analyzed);
  q('#analysis-gap').textContent = `${count(total - view.stats.analyzed)} articles awaiting analysis`;
  q('#dated-share').textContent = share(total - view.stats.undated);
  q('#dated-gap').textContent = `${count(view.stats.undated)} articles without a usable date`;
  q('#collection-health').replaceChildren(...[
    ['Author recorded', health.with_author],
    ['Saved topic labels', health.with_topics],
    ['Capture checks recorded', health.checked],
    ['Capture flags to inspect', health.flagged],
    ['Capture checks unavailable', total - health.checked],
  ].map(([label, amount]) => {
    const row = make('div'); row.append(make('dt', '', label), make('dd', '', count(amount) + ' / ' + count(total))); return row;
  }));
  const coverage = view.topic_coverage;
  q('#research-detail-grid').hidden = investment;
  if (!coverage.topics.length) {
    q('#topic-coverage').replaceChildren(make('p', 'obs-topic-empty', total ? 'Analyze some of these articles in Research to compare their saved topic labels across publishers.' : 'No articles match these filters.'));
  } else {
    const table = make('table', 'obs-coverage-table');
    table.setAttribute('aria-label', 'Saved topic labels by publisher');
    const head = make('thead'), header = make('tr');
    const corner = make('th', '', 'Topic'); corner.scope = 'col'; header.append(corner);
    coverage.sources.forEach(source => {
      const cell = make('th'), button = make('button', 'obs-table-label', source);
      cell.scope = 'col'; button.dataset.source = source;
      button.setAttribute('aria-label', 'Focus publisher: ' + source); cell.append(button); header.append(cell);
    });
    head.append(header); const body = make('tbody');
    const lookup = new Map(coverage.cells.map(cell => [JSON.stringify([cell.topic, cell.source]), cell.count]));
    coverage.topics.forEach(topic => {
      const row = make('tr'), label = make('th'), button = make('button', 'obs-table-label', topic.name);
      label.scope = 'row'; button.dataset.topic = topic.name; button.setAttribute('aria-label', 'Focus topic: ' + topic.name);
      label.append(button, make('small', '', count(topic.publishers) + ' publishers in selection')); row.append(label);
      coverage.sources.forEach(source => {
        const amount = lookup.get(JSON.stringify([topic.name, source])) || 0;
        const cell = make('td'), mark = make('button', 'obs-coverage-count', amount ? count(amount) : '—');
        mark.dataset.comparison = 'true'; mark.dataset.topic = topic.name; mark.dataset.source = source;
        mark.disabled = !amount; mark.style.setProperty('--cell-strength', (10 + amount / Math.max(1, topic.count) * 24) + '%');
        mark.setAttribute('aria-label', `${topic.name}, ${source}: ${count(amount)} articles`);
        mark.setAttribute('aria-pressed', String(root._filters.topic === topic.name && root._filters.source === source));
        describe(mark, {label: topic.name + ' · ' + source, value: count(amount) + ' articles',
          detail: 'Current saved analyses with this topic label. A missing label does not establish missing reporting.', hint: 'Select to inspect these saved sources'});
        cell.append(mark); row.append(cell);
      });
      body.append(row);
    });
    table.append(head, body); q('#topic-coverage').replaceChildren(table);
  }
  q('#topic-coverage-note').textContent = `Up to 6 topics × 5 leading publishers · ${count(health.with_topics)} of ${count(total)} articles have saved labels. Counts may overlap; labels do not establish agreement or a publisher's omissions.`;
  q('#scope-status').textContent = investment ? `${count(view.stats.indexed)} sources with inspectable coverage signals` : 'Saved-source analytics · no model call required';
  q('#date-span').textContent = view.stats.earliest ? `${date(view.stats.earliest)} – ${date(view.stats.latest)}` : 'No dated sources';
  const audit = view.audit;
  const noteParagraphs = investment ? [
    'Counts describe mentions in saved titles and article text. An article can cover several lenses. Company and product aliases are grouped; a mention does not imply an investment, financing link, endorsement, or verified claim.',
    'The two passage cards show matched concerns and counterarguments. They are not classifications of an author’s overall position. Open the reading copy to inspect the surrounding text.',
    `${count(view.stats.undated)} articles in this selection have no usable publication date. Dates are extracted from publisher metadata and can be approximate. Timeline clicks and the other controls filter the evidence list together.`,
  ] : [
    'General analytics applies to any topic or language. Counts describe the selected saved sources, not all reporting on a subject. Publisher labels and publication dates come from saved metadata and may need review.',
    `Topics are model-generated labels from current saved qwen3:8b analyses. Up to 8 labels are shown; labels may overlap and are not verified facts. ${count(view.stats.articles - view.stats.analyzed)} articles in this view have no current analysis and contribute no topic labels.`,
    `${count(view.stats.undated)} articles have no usable publication date and are excluded from the timeline. Short date ranges use daily counts; longer ranges show up to the latest 60 months, including empty months. Reading times are estimates at 220 words per minute.`,
  ];
  noteParagraphs.push(`Publication momentum compares ${date(momentum.start)}–${date(momentum.end)} with ${date(momentum.previous_start)}–${date(momentum.previous_end)}, within every active filter. It counts saved articles by publication date, not total web coverage or the rate of new imports. Date filters can restrict either comparison window. A zero prior count has no percentage baseline.`);
  noteParagraphs.push('Publisher concentration uses saved source labels, not corporate ownership, editorial independence or political diversity. Capture checks describe automated reading-copy diagnostics; unrecorded checks are unknown. No model runs when these analytics open.');
  if (audit) {
    const summary = audit.summary || {}, statuses = summary.statuses || {};
    noteParagraphs.push(`Collection audit: ${count(summary.saved)} sources saved from ${count(summary.attempted)} candidates checked; ${count(statuses.failed)} fetch/extraction failures, ${count(statuses.unsupported)} unsupported pages, ${count(statuses.duplicate)} duplicates, and ${count(statuses.quality_rejected)} pages excluded in the source-type audit. Public HTML only; robots rules and access restrictions respected.`);
    noteParagraphs.push('The collection includes news, commentary, institutional analysis, and public research abstracts. Candidates were shuffled across website hosts, with a maximum of five per host. This is a research sample, not a representative market-wide sentiment survey. Extraction completeness is not guaranteed.');
  }
  notes.replaceChildren(...noteParagraphs.map(text => make('p', '', text)));
  q('#lenses').hidden = !investment;
  q('#topics').hidden = investment;
  q('#investment-panel').hidden = !investment;
  q('#general-panel').hidden = investment;
  q('#evidence-heading').hidden = !investment;
  q('#arguments').hidden = !investment;
  q('#topics-heading').textContent = investment ? 'What the stories examine' : 'Topics in this collection';
  q('#topics-note').textContent = investment ? 'Each article can match more than one lens' : 'Top saved labels · select a topic to explore';
  q('#final-note').textContent = investment ? 'AI investment coverage describes keyword mentions in the saved sources. It does not establish whether an AI bubble exists.' : 'Counts describe your saved sources, not all reporting on a topic. Open Research for summaries and answers with cited evidence.';

  const topicNodes = view.topics.map((topic, index) => {
    const button = make('button', 'obs-lens'); button.dataset.topic = topic.name;
    button.style.setProperty('--lens-color', `var(--tone-${['blue', 'purple', 'teal', 'amber', 'clay', 'slate'][index % 6]})`);
    button.setAttribute('aria-pressed', String(root._filters.topic === topic.name));
    button.setAttribute('aria-label', topic.name + ': ' + count(topic.count) + ' articles');
    const label = make('span', 'obs-lens-label'); label.append(make('span', '', topic.name), make('b', '', count(topic.count)));
    const track = make('div', 'obs-track'), fill = make('i'); fill.style.transform = `scaleX(${topic.count / Math.max(1, view.stats.articles)})`; track.append(fill);
    button.append(label, track); return button;
  });
  if (!topicNodes.length) topicNodes.push(make('p', 'obs-topic-empty', view.stats.articles ? 'No saved topic labels in this selection yet. Analyze articles in Research to see their topics here. Publication and publisher analytics are already available.' : 'No topic labels match these filters. Clear a filter to return to the collection.'));
  q('#topics').replaceChildren(...topicNodes);
  q('#analysis-status').replaceChildren(...[['Analyzed', view.stats.analyzed], ['Needs analysis', view.stats.articles - view.stats.analyzed]].map(([label, amount]) => {
    const button = make('button', 'obs-button', label + ' · ' + count(amount));
    button.dataset.status = label; button.setAttribute('aria-pressed', String(root._filters.status === label)); return button;
  }));
  q('#reading-profile').replaceChildren(...[['Up to 5 min', view.stats.short_reads], ['5–15 min', view.stats.medium_reads], ['Over 15 min', view.stats.long_reads]].map(([label, amount]) => {
    const row = make('div'), heading = make('div', 'obs-publisher-label'); heading.append(make('span', '', label), make('span', '', count(amount)));
    const track = make('div', 'obs-track'), fill = make('i'); fill.style.transform = `scaleX(${amount / Math.max(1, view.stats.articles)})`; track.append(fill); row.append(heading, track); return row;
  }));
  q('#reading-note').textContent = `${count(view.stats.words)} extracted words · ${count(Math.ceil(view.stats.words / 220))} estimated reading minutes · ${count(view.stats.undated)} undated articles`;

  const chips = [];
  const addChip = (key, label) => {
    if (!root._filters[key]) return;
    const button = make('button', 'obs-filter-chip', label);
    button.type = 'button'; button.dataset.clear = key;
    button.setAttribute('aria-label', 'Clear filter: ' + label);
    button.appendChild(make('span', '', '×')); chips.push(button);
  };
  addChip('lens', lensById.get(root._filters.lens)?.short || root._filters.lens);
  addChip('entity', root._filters.entity);
  addChip('topic', root._filters.topic);
  if (root._filters.status !== 'All articles') addChip('status', root._filters.status);
  addChip('source', root._filters.source);
  addChip('month', root._filters.month ? monthLabel(root._filters.month) : '');
  addChip('day', root._filters.day ? date(root._filters.day) : '');
  addChip('query', 'Search: ' + root._filters.query);
  if (root._filters.period !== 'all') {
    const button = make('button', 'obs-filter-chip', root._filters.period === '90d' ? 'Past 90 days ×' : 'Past 12 months ×');
    button.dataset.clear = 'period'; chips.push(button);
  }
  if (chips.length) {
    const reset = make('button', 'obs-text-button', 'Reset filters'); reset.dataset.reset = 'true'; chips.push(reset);
  } else chips.push(make('span', 'obs-footnote', 'All sources in this collection · Select any chart to explore'));
  q('#focus-chips').replaceChildren(...chips);

  root._lensNodes ||= new Map();
  const lensNodes = view.lenses.map(lens => {
    let button = root._lensNodes.get(lens.id);
    if (!button) {
      button = make('button', 'obs-lens'); button.dataset.lens = lens.id;
      const label = make('span', 'obs-lens-label'); label.append(make('span', '', lens.label), make('b', '', '0'));
      const track = make('div', 'obs-track'); track.appendChild(make('i'));
      button.append(label, track); root._lensNodes.set(lens.id, button);
    }
    button.setAttribute('aria-pressed', String(root._filters.lens === lens.id));
    button.setAttribute('aria-label', lens.label + ': ' + count(lens.count) + ' articles');
    button.style.setProperty('--lens-color', lensColor(lens.id));
    describe(button, { label: lens.label, value: count(lens.count) + ' articles',
      detail: `${percent(lens.count)}% of the current selection matches this coverage theme.`,
      hint: root._filters.lens === lens.id ? 'Click again to clear this theme' : 'Click to filter the sources' });
    button.querySelector('b').textContent = count(lens.count);
    button.querySelector('i').style.transform = `scaleX(${view.stats.articles ? lens.count / view.stats.articles : 0})`;
    return button;
  });
  reconcile(q('#lenses'), lensNodes);

  const renderTimeline = () => {
    const container = q('#timeline'), values = root._view.timeline.map(row => ({...row, month: row.day || row.month}));
    if (!values.length) { container.replaceChildren(make('div', 'obs-empty-chart', 'No dated articles in this selection')); return; }
    const width = Math.max(260, container.clientWidth), height = 210, left = 42, right = 12, top = 18, baseline = 175;
    const chart = svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'group', 'aria-label': 'Article count by publication ' + view.timeline_granularity });
    const high = Math.max(...values.map(value => value.count), 1);
    for (const value of new Set([0, Math.ceil(high / 2), high])) {
      const y = baseline - value / high * (baseline - top);
      chart.appendChild(svg('line', { x1: left, x2: width - right, y1: y, y2: y, class: 'grid-line' }));
      const text = svg('text', { x: left - 8, y: y + 3, 'text-anchor': 'end' });
      text.textContent = count(value); chart.appendChild(text);
    }
    const area = svg('path', { class: 'volume-area' }), line = svg('path', { class: 'volume-line' });
    chart.append(area, line);
    const step = values.length > 1 ? (width - left - right) / (values.length - 1) : 0;
    const target = values.map((value, index) => ({ ...value, x: values.length === 1 ? width / 2 : left + step * index, y: baseline - value.count / high * (baseline - top) }));
    const prior = root._timelinePoints || new Map();
    const origins = target.map(point => prior.get(point.month) || { x: point.x, y: baseline });
    const dots = [], focusRings = [];
    target.forEach((point, index) => {
      const group = svg('g', { role: 'button', tabindex: 0, 'data-month': point.month,
        'aria-label': `${monthLabel(point.month)}: ${count(point.count)} articles`, 'aria-pressed': String((root._filters.day || root._filters.month) === point.month) });
      group.appendChild(svg('rect', { class: 'month-hit', x: point.x - Math.max(10, step / 2), y: top, width: Math.max(20, step), height: baseline - top + 10 }));
      // Keep the generous column hit area, but draw keyboard focus around the
      // data point rather than the browser's full-height SVG group outline.
      const focusRing = svg('circle', { class: 'month-focus-ring', cx: point.x, cy: baseline, r: 9, 'aria-hidden': 'true' });
      const dot = svg('circle', { class: 'month-point', cx: point.x, cy: baseline, r: 3 });
      group.append(focusRing, dot); dots.push(dot); focusRings.push(focusRing);
      describe(group, { label: point.month.length === 10 ? date(point.month) : new Date(point.month + '-01T12:00:00Z').toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
        value: `${count(point.count)} ${point.count === 1 ? 'article' : 'articles'}`,
        detail: `${percent(point.count)}% of the current selection was published this ${view.timeline_granularity}.`,
        hint: (root._filters.day || root._filters.month) === point.month ? 'Click again to clear this date' : 'Click to filter this date' });
      chart.appendChild(group);
      const interval = Math.max(1, Math.ceil(values.length / Math.max(3, width / 85)));
      if (index % interval === 0 || index === target.length - 1) {
        const label = svg('text', { x: point.x, y: 200, 'text-anchor': index === target.length - 1 ? 'end' : index === 0 ? 'start' : 'middle' });
        label.textContent = monthLabel(point.month); chart.appendChild(label);
      }
    });
    container.replaceChildren(chart);
    animate(380, progress => {
      const points = target.map((point, index) => ({ month: point.month, x: origins[index].x + (point.x - origins[index].x) * progress, y: origins[index].y + (point.y - origins[index].y) * progress }));
      const path = points.map((point, index) => `${index ? 'L' : 'M'}${point.x},${point.y}`).join(' ');
      line.setAttribute('d', path);
      area.setAttribute('d', `${path} L${points[points.length - 1].x},${baseline} L${points[0].x},${baseline} Z`);
      points.forEach((point, index) => {
        for (const node of [dots[index], focusRings[index]]) {
          node.setAttribute('cx', point.x); node.setAttribute('cy', point.y);
        }
      });
      root._timelinePoints = new Map(points.map(point => [point.month, point]));
    });
  };
  renderTimeline();
  let timelineWidth = q('#timeline').clientWidth;
  const resize = new ResizeObserver(() => {
    const width = q('#timeline').clientWidth;
    if (width !== timelineWidth) { timelineWidth = width; renderTimeline(); }
  }); resize.observe(q('#timeline'));
  q('#timeline-note').textContent = `Publication ${view.timeline_granularity === 'day' ? 'days' : 'months'} in this selection`;
  q('#timeline-hint').textContent = `Select a ${view.timeline_granularity} to focus the sources`;
  q('#clear-month').hidden = !root._filters.month && !root._filters.day;
  on(q('#clear-month'), 'click', () => commit({ month: '', day: '' }));

  root._matrixNodes ||= new Map();
  const grid = q('#matrix').querySelector('.obs-matrix') || make('div', 'obs-matrix');
  if (!grid.parentElement) q('#matrix').appendChild(grid);
  const matrixNodes = [make('div')];
  view.lenses.forEach(lens => {
    const label = make('div', 'obs-matrix-label', lens.short);
    label.style.setProperty('--lens-color', lensColor(lens.id)); matrixNodes.push(label);
  });
  const companies = view.entities.slice(0, 7), lookup = new Map(view.matrix.map(cell => [cell.entity + ':' + cell.lens, cell.count]));
  if (!companies.length) {
    q('#matrix').replaceChildren(make('div', 'obs-empty-chart', 'No tracked company mentions in this selection'));
  } else {
    for (const company of companies) {
      const rowButton = make('button', 'obs-company'); rowButton.dataset.entity = company.name;
      rowButton.setAttribute('aria-pressed', String(root._filters.entity === company.name));
      rowButton.append(make('span', 'obs-company-mark', company.name[0]), make('span', '', company.name)); matrixNodes.push(rowButton);
      for (const lens of view.lenses) {
        const key = company.name + ':' + lens.id;
        let cell = root._matrixNodes.get(key);
        if (!cell) { cell = make('button', 'obs-cell'); cell.dataset.entity = company.name; cell.dataset.lens = lens.id; cell.dataset.matrix = 'true'; root._matrixNodes.set(key, cell); }
        const amount = lookup.get(key) || 0;
        cell.textContent = amount ? count(amount) : '–'; cell.classList.toggle('zero', !amount);
        cell.style.setProperty('--lens-color', lensColor(lens.id));
        cell.style.background = `color-mix(in srgb, ${lensColor(lens.id)} ${Math.round(amount / Math.max(1, view.stats.articles) * 32 + (amount ? 8 : 0))}%, var(--panel))`;
        cell.setAttribute('aria-label', `${company.name}, ${lens.short}: ${count(amount)} articles`);
        cell.removeAttribute('title');
        describe(cell, { label: company.name + ' · ' + lens.short, value: count(amount) + ' articles',
          detail: 'Sources mentioning both the company and this coverage theme. A co-mention does not establish a financial link.',
          hint: 'Click to filter by company and theme' });
        cell.setAttribute('aria-pressed', String(root._filters.entity === company.name && root._filters.lens === lens.id));
        matrixNodes.push(cell);
      }
    }
    reconcile(grid, matrixNodes);
  }

  root._publisherNodes ||= new Map();
  const publishers = view.publishers.map(publisher => {
    let button = root._publisherNodes.get(publisher.name);
    if (!button) {
      button = make('button', 'obs-publisher'); button.dataset.source = publisher.name;
      const label = make('div', 'obs-publisher-label'); label.append(make('span', '', publisher.name), make('span', '', '0'));
      const track = make('div', 'obs-track'); track.appendChild(make('i')); button.append(label, track); root._publisherNodes.set(publisher.name, button);
    }
    button.setAttribute('aria-pressed', String(root._filters.source === publisher.name));
    describe(button, { label: publisher.name, value: count(publisher.count) + ' articles',
      detail: `${percent(publisher.count)}% of the current selection.`, hint: 'Click to focus this publisher' });
    button.querySelector('.obs-publisher-label').lastElementChild.textContent = count(publisher.count);
    button.querySelector('i').style.transform = `scaleX(${publisher.count / Math.max(1, view.stats.articles)})`;
    let metadata = button.querySelector('.obs-publisher-meta');
    if (!metadata) { metadata = make('div', 'obs-publisher-meta'); button.append(metadata); }
    metadata.replaceChildren(make('span', '', `${share(publisher.count)} of selection · ${share(publisher.analyzed, publisher.count)} analyzed`),
      make('span', '', publisher.latest ? 'Latest ' + date(publisher.latest) : 'No publication dates'));
    return button;
  });
  reconcile(q('#publishers'), publishers);
  q('#publisher-note').textContent = view.stats.publishers > 8 ? `Top 8 of ${count(view.stats.publishers)} publishers. Use the selector to focus any source.` : 'Publisher labels reflect the saved source metadata.';

  const argumentCards = [];
  for (const [kind, label] of [['concern', 'Concerns raised'], ['countercase', 'The countercase']]) {
    const article = (view.evidence[kind] || [])[0];
    const card = make('article', 'obs-argument ' + kind);
    card.appendChild(make('div', 'obs-eyebrow', label.toUpperCase()));
    card.appendChild(make('blockquote', '', article ? article.excerpt : 'No matching passage in this selection. Broaden your filters to inspect more coverage.'));
    const footer = make('div', 'obs-argument-footer');
    if (article) {
      footer.appendChild(make('span', '', article.source + ' · ' + date(article.published)));
      const read = make('button', 'obs-text-button', 'Read in context ↗'); read.dataset.read = article.id; footer.appendChild(read);
    }
    card.appendChild(footer); argumentCards.push(card);
  }
  q('#arguments').replaceChildren(...argumentCards);

  root._rowNodes ||= new Map();
  const sourceRows = view.rows.map(article => {
    let row = root._rowNodes.get(article.id);
    if (!row) {
      row = make('div', 'obs-row'); row.dataset.article = article.id;
      const copy = make('div'); copy.append(make('div', 'obs-row-meta'), make('div', 'obs-row-title'), make('div', 'obs-row-excerpt'));
      const tags = make('div', 'obs-row-lenses');
      const read = make('button', 'obs-read', '↗'); read.dataset.read = article.id;
      read.setAttribute('aria-label', 'Read article: ' + article.title);
      row.append(copy, tags, read); root._rowNodes.set(article.id, row);
    }
    row.querySelector('.obs-row-meta').textContent = article.source + ' · ' + date(article.published);
    row.querySelector('.obs-row-title').textContent = article.title;
    row.querySelector('.obs-row-excerpt').textContent = article.excerpt;
    row.querySelector('.obs-row-lenses').replaceChildren(...(investment ? article.lenses : article.topics).slice(0, 2).map(id => {
      const tag = make('span', 'obs-row-tag', investment ? lensById.get(id)?.short || id : id);
      tag.style.setProperty('--lens-color', investment ? lensColor(id) : 'var(--tone-blue)'); return tag;
    }));
    return row;
  });
  if (!sourceRows.length) sourceRows.push(make('div', 'obs-empty-chart', 'No matching articles. Reset a filter to return to the collection.'));
  reconcile(q('#source-rows'), sourceRows);
  const currentIds = new Set(view.rows.map(article => article.id));
  for (const id of root._rowNodes.keys()) if (!currentIds.has(id)) root._rowNodes.delete(id);
  q('#notebook-caption').textContent = `${count(view.stats.articles)} sources match this view. Read the passages in their original context.`;
  q('#page-label').textContent = `Page ${count(view.page)} of ${count(view.pages)} · ${count(view.stats.articles)} articles`;
  q('#previous').disabled = view.page <= 1; q('#next').disabled = view.page >= view.pages;
  on(q('#previous'), 'click', () => commit({ page: view.page - 1 }, false));
  on(q('#next'), 'click', () => commit({ page: view.page + 1 }, false));

  const handleAction = target => {
    const clear = target.closest('[data-clear]');
    if (clear) { commit({ [clear.dataset.clear]: clear.dataset.clear === 'period' ? 'all' : clear.dataset.clear === 'status' ? 'All articles' : '' }); return; }
    if (target.closest('[data-reset]')) { commit({ query: '', source: '', period: 'all', lens: '', entity: '', month: '', day: '', topic: '', status: 'All articles' }); return; }
    const comparison = target.closest('[data-comparison]');
    if (comparison) {
      const same = root._filters.topic === comparison.dataset.topic && root._filters.source === comparison.dataset.source;
      commit({ topic: same ? '' : comparison.dataset.topic, source: same ? '' : comparison.dataset.source }); return;
    }
    const topic = target.closest('[data-topic]');
    if (topic) { commit({ topic: root._filters.topic === topic.dataset.topic ? '' : topic.dataset.topic }); return; }
    const status = target.closest('[data-status]');
    if (status) { commit({ status: root._filters.status === status.dataset.status ? 'All articles' : status.dataset.status }); return; }
    const read = target.closest('[data-read]');
    if (read) { setTriggerValue('open_article', read.dataset.read); return; }
    const matrixCell = target.closest('[data-matrix]');
    if (matrixCell) {
      const same = root._filters.entity === matrixCell.dataset.entity && root._filters.lens === matrixCell.dataset.lens;
      commit({ entity: same ? '' : matrixCell.dataset.entity, lens: same ? '' : matrixCell.dataset.lens }); return;
    }
    const lens = target.closest('[data-lens]');
    if (lens) { commit({ lens: root._filters.lens === lens.dataset.lens ? '' : lens.dataset.lens }); return; }
    const entity = target.closest('[data-entity]');
    if (entity) { commit({ entity: root._filters.entity === entity.dataset.entity ? '' : entity.dataset.entity }); return; }
    const source = target.closest('[data-source]');
    if (source) { commit({ source: root._filters.source === source.dataset.source ? '' : source.dataset.source }); return; }
    const month = target.closest('[data-month]');
    if (month) {
      const key = month.dataset.month.length === 10 ? 'day' : 'month';
      commit({ month: '', day: '', [key]: root._filters[key] === month.dataset.month ? '' : month.dataset.month });
    }
  };
  on(root, 'click', event => handleAction(event.target));
  on(q('#timeline'), 'keydown', event => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.closest('[data-month]')) {
      event.preventDefault(); handleAction(event.target);
    }
  });
  if (focusToken && !focused.isConnected) {
    const replacement = [...root.querySelectorAll('button,[data-month]')].find(node => {
      if (focusToken.id) return node.id === focusToken.id;
      return ['lens', 'entity', 'month', 'source', 'matrix', 'topic', 'status'].every(key => node.dataset[key] === focusToken[key]);
    });
    replacement?.focus({ preventScroll: true });
  }
  if (data.download && data.download.id !== root._downloaded) {
    root._downloaded = data.download.id;
    const url = URL.createObjectURL(new Blob(['\ufeff' + data.download.text], { type: 'text/csv;charset=utf-8' }));
    objectUrls.add(url);
    const anchor = make('a'); anchor.href = url; anchor.download = 'article-coverage.csv';
    anchor.hidden = true; root.appendChild(anchor); anchor.click(); anchor.remove();
    const timer = setTimeout(() => { URL.revokeObjectURL(url); objectUrls.delete(url); }, 1500); timers.add(timer);
  }
  const dispose = () => {
    hideTooltip();
    abort.abort(); resize.disconnect(); clearTimeout(typing);
    frames.forEach(id => cancelAnimationFrame(id)); timers.forEach(id => clearTimeout(id));
    objectUrls.forEach(url => URL.revokeObjectURL(url));
    if (root._dispose === dispose) delete root._dispose;
  };
  root._dispose = dispose;
  return dispose;
}
