'use strict';

/* Canvas-based layout editor — adapted from VP_Sim's GroundCanvasView with
 * a dark palette and simplified scope (no simulation overlay, no 3D view).
 *
 * Owns its own state (layout JSON), tools, selection, and drawing. Exposes
 * load/serialize hooks for the surrounding app.js to plumb to /api/layouts.
 *
 * window.LayoutEditor = { create(canvas, opts), ... }
 */

const POSITION_SNAP = 10;

const COLORS = {
  /* canvas backdrop (outside the grid) */
  bg: '#080d14',
  /* grid surface fill — clearly lighter than the backdrop so the working
   * area is visually anchored even before any entity is placed. */
  gridFill: '#142436',
  /* lines */
  grid: '#3e577f',         /* every cell (20m)  — minor */
  gridMajor: '#6e8bb5',    /* every 5 cells (100m) — major */
  gridBorder: '#9cb6dc',   /* outer boundary */
  axisLabel: '#bcd0ee',
  /* entities & links — link colors are deliberately picked OUTSIDE the
   * blue/gray grid palette so taxiways stay readable on top of the grid. */
  gate: '#34c77a',
  fato: '#3b82f6',
  fatoTakeoff: '#a78bfa',
  fatoLanding: '#f59e0b',
  takeoffPoint: '#a78bfa',
  landingPoint: '#f59e0b',
  commonAirPoint: '#22d3ee',
  node: '#aab6c5',
  link: '#e2e8f0',         /* ground taxiway — near-white slate */
  airLink: '#22d3ee',      /* air corridor — bright cyan */
  selected: '#fbbf24',
  text: '#e6edf5',
  subtext: '#aab6c5',
};

const RADII = {
  gate: 22,
  fato: 26,
  node: 7,
  takeoffPoint: 15,
  landingPoint: 15,
  commonAirPoint: 15,
};

const ENTITY_LABELS = {
  gate: 'Gate',
  fato: 'FATO',
  node: 'Node',
  takeoffPoint: 'Takeoff',
  landingPoint: 'Landing',
  commonAirPoint: 'Common',
};

const ENTITY_PREFIX = {
  gate: 'gate',
  fato: 'fato',
  node: 'node',
  takeoffPoint: 'takeoff-point',
  landingPoint: 'landing-point',
  commonAirPoint: 'common-air-point',
};

const DEFAULT_ALTITUDE = { takeoffPoint: 15, landingPoint: 15, commonAirPoint: 15 };

function blankLayout(name = '새 레이아웃') {
  return {
    meta: { name },
    grid: { width: 1000, height: 720, size: 20, unit: 'm' },
    entities: [],
    links: [],
    simulationParameters: {
      vehicle: { groundSpeedMps: 5, airSpeedMps: 35, verticalSpeedMps: 3 },
      gateProcedure: {
        engineStartAndTowDisconnectMinutes: 4,
        engineStopAndTowConnectMinutes: 3,
        groundHandlingMinutes: 10,
      },
      fatoProcedure: { postOperationLockMinutes: 1 },
    },
  };
}

class LayoutEditor extends EventTarget {
  constructor(canvas, opts = {}) {
    super();
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.layout = null;
    this.tool = 'select';
    this.fatoMode = 'both';
    this.selectedId = null;
    this.selectedLinkId = null;
    this.linkStartId = null;
    this.dirty = false;
    this.scale = 0.7;
    this.offset = { x: 60, y: 50 };
    this.pointer = { x: 0, y: 0 };
    this.pointerScreen = null;
    this.drag = null;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this._bindEvents();
  }

  /* ---------- public API ---------- */

  loadLayout(layout) {
    this.layout = structuredClone(layout || blankLayout());
    if (!this.layout.entities) this.layout.entities = [];
    if (!this.layout.links) this.layout.links = [];
    this._normalizeCoords();
    this.selectedId = null;
    this.selectedLinkId = null;
    this.linkStartId = null;
    this.dirty = false;
    this._emit('layout');
    this.fit();
  }

  serialize() {
    if (!this.layout) return null;
    return structuredClone(this.layout);
  }

  setTool(tool) {
    this.tool = tool;
    if (tool !== 'link') this.linkStartId = null;
    this._emit('tool');
  }

  setFatoMode(mode) {
    this.fatoMode = mode;
    this._emit('tool');
  }

  selectEntity(id) {
    this.selectedId = id;
    this.selectedLinkId = null;
    this._emit('selection');
  }

  selectLink(id) {
    this.selectedId = null;
    this.selectedLinkId = id;
    this._emit('selection');
  }

  clearSelection() {
    this.selectedId = null;
    this.selectedLinkId = null;
    this._emit('selection');
  }

  get selectedEntity() {
    return this.layout?.entities.find((e) => e.id === this.selectedId) || null;
  }

  get selectedLink() {
    return this.layout?.links.find((l) => l.id === this.selectedLinkId) || null;
  }

  updateEntity(id, updates) {
    const entity = this.layout?.entities.find((e) => e.id === id);
    if (!entity) return;
    Object.assign(entity, updates);
    if (typeof entity.x === 'number') entity.x = this._snapX(entity.x);
    if (typeof entity.y === 'number') entity.y = this._snapY(entity.y);
    if (typeof entity.altitude === 'number') entity.altitude = Math.max(0, Math.round(entity.altitude));
    this._markDirty();
  }

  deleteSelected() {
    if (!this.layout) return;
    if (this.selectedId) {
      const id = this.selectedId;
      this.layout.entities = this.layout.entities.filter((e) => e.id !== id);
      this.layout.links = this.layout.links.filter((l) => l.from !== id && l.to !== id);
      this.selectedId = null;
      if (this.linkStartId === id) this.linkStartId = null;
      this._markDirty();
    } else if (this.selectedLinkId) {
      const id = this.selectedLinkId;
      this.layout.links = this.layout.links.filter((l) => l.id !== id);
      this.selectedLinkId = null;
      this._markDirty();
    }
  }

  clearLayout() {
    if (!this.layout) return;
    this.layout.entities = [];
    this.layout.links = [];
    this.selectedId = null;
    this.selectedLinkId = null;
    this.linkStartId = null;
    this._markDirty();
  }

  setGridSize(width, height) {
    if (!this.layout) return;
    const w = Math.max(200, Math.round((Number(width) || this.layout.grid.width) / POSITION_SNAP) * POSITION_SNAP);
    const h = Math.max(200, Math.round((Number(height) || this.layout.grid.height) / POSITION_SNAP) * POSITION_SNAP);
    if (w === this.layout.grid.width && h === this.layout.grid.height) return;
    this.layout.grid.width = w;
    this.layout.grid.height = h;
    this._normalizeCoords();
    this._markDirty();
  }

  fitGridToContent(padding = 80) {
    if (!this.layout?.entities.length) return;
    const pad = Math.max(POSITION_SNAP * 4, Math.round(padding / POSITION_SNAP) * POSITION_SNAP);
    const xs = this.layout.entities.map((e) => Number(e.x) || 0);
    const ys = this.layout.entities.map((e) => Number(e.y) || 0);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const w = Math.max(400, Math.round((maxX - minX + pad * 2) / POSITION_SNAP) * POSITION_SNAP);
    const h = Math.max(400, Math.round((maxY - minY + pad * 2) / POSITION_SNAP) * POSITION_SNAP);
    const dx = pad - minX;
    const dy = pad - minY;
    this.layout.grid.width = w;
    this.layout.grid.height = h;
    for (const ent of this.layout.entities) {
      ent.x = this._snapX(ent.x + dx);
      ent.y = this._snapY(ent.y + dy);
    }
    this._markDirty();
    this.fit();
  }

  markSaved() {
    this.dirty = false;
    this._emit('dirty');
  }

  /* ---------- view ---------- */

  fit() {
    if (!this.layout) {
      this.draw();
      return;
    }
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const { width, height } = this.layout.grid;
    /* leave room for axis labels (top + left side) */
    const pad = 70;
    this.scale = Math.min((rect.width - pad * 2) / width, (rect.height - pad * 2) / height);
    this.scale = clamp(this.scale, 0.25, 2.4);
    this.offset.x = (rect.width - width * this.scale) / 2;
    this.offset.y = (rect.height - height * this.scale) / 2;
    this.draw();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    this.canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.draw();
  }

  draw() {
    const ctx = this.ctx;
    const rect = this.canvas.getBoundingClientRect();
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, rect.width, rect.height);
    if (!this.layout) return;

    ctx.save();
    ctx.translate(this.offset.x, this.offset.y);
    ctx.scale(this.scale, this.scale);
    this._drawGrid();
    this._drawAxisLabels();
    this._drawHoverGuides();
    this._drawLinks();
    this._drawEntities();
    this._drawGhostPlacement();
    this._drawPendingLink();
    ctx.restore();
    this._drawCoordinateTooltip(rect);
  }

  /* ---------- internals: events ---------- */

  _bindEvents() {
    this.canvas.addEventListener('pointerdown', (e) => this._onPointerDown(e));
    this.canvas.addEventListener('pointermove', (e) => this._onPointerMove(e));
    this.canvas.addEventListener('pointerup', (e) => this._onPointerUp(e));
    this.canvas.addEventListener('pointercancel', (e) => this._onPointerUp(e));
    this.canvas.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
    this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    this.canvas.addEventListener('pointerleave', () => {
      this.pointerScreen = null;
      this.draw();
    });
    /* Keyboard shortcuts only when canvas region is focused */
    this.canvas.tabIndex = 0;
    this.canvas.addEventListener('keydown', (e) => this._onKeyDown(e));
  }

  _onPointerDown(event) {
    if (!this.layout) return;
    this.canvas.setPointerCapture(event.pointerId);
    this.canvas.focus();
    const screen = this._screenPoint(event);
    const world = this._toWorld(screen);
    const hitEntity = this._hitEntity(world);
    const hitLink = this._hitLink(world);
    this.pointer = world;
    this.pointerScreen = screen;

    if (event.button === 1 || event.button === 2) {
      this.drag = { kind: 'pan', start: screen, offset: { ...this.offset } };
      return;
    }

    if (this._isPlacementTool()) {
      if (hitEntity) { this.selectEntity(hitEntity.id); return; }
      if (hitLink) { this.selectLink(hitLink.id); return; }
      if (!this._isInsideGrid(world)) {
        this.clearSelection();
        this.drag = { kind: 'pan', start: screen, offset: { ...this.offset } };
        return;
      }
      this._addEntity(this.tool, world.x, world.y);
      return;
    }

    if (this.tool === 'link') {
      if (hitEntity) this._handleLinkPick(hitEntity);
      return;
    }

    if (hitEntity) {
      this.selectEntity(hitEntity.id);
      this.drag = {
        kind: 'entity',
        id: hitEntity.id,
        startWorld: world,
        startEntity: { x: hitEntity.x, y: hitEntity.y },
      };
      return;
    }
    if (hitLink) { this.selectLink(hitLink.id); return; }

    this.clearSelection();
    this.drag = { kind: 'pan', start: screen, offset: { ...this.offset } };
  }

  _onPointerMove(event) {
    const screen = this._screenPoint(event);
    const world = this._toWorld(screen);
    this.pointer = world;
    this.pointerScreen = screen;
    if (!this.drag) {
      /* Always redraw on hover so the coordinate tooltip and the placement
       * ghost preview track the cursor. Cheap for the entity counts we have. */
      this.draw();
      return;
    }
    if (this.drag.kind === 'pan') {
      this.offset.x = this.drag.offset.x + screen.x - this.drag.start.x;
      this.offset.y = this.drag.offset.y + screen.y - this.drag.start.y;
      this.draw();
    } else if (this.drag.kind === 'entity') {
      const dx = world.x - this.drag.startWorld.x;
      const dy = world.y - this.drag.startWorld.y;
      const x = snap(this.drag.startEntity.x + dx, POSITION_SNAP);
      const y = snap(this.drag.startEntity.y + dy, POSITION_SNAP);
      this.updateEntity(this.drag.id, this._clampToGrid({ x, y }));
    }
  }

  _onPointerUp(event) {
    if (this.canvas.hasPointerCapture(event.pointerId)) {
      this.canvas.releasePointerCapture(event.pointerId);
    }
    this.drag = null;
  }

  _onWheel(event) {
    if (!this.layout) return;
    event.preventDefault();
    const screen = this._screenPoint(event);
    const before = this._toWorld(screen);
    const zoom = Math.exp(-event.deltaY * 0.001);
    this.scale = clamp(this.scale * zoom, 0.25, 3.2);
    const after = this._toScreen(before);
    this.offset.x += screen.x - after.x;
    this.offset.y += screen.y - after.y;
    this.draw();
  }

  _onKeyDown(event) {
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      this.deleteSelected();
    } else if (event.key === 'Escape') {
      this.linkStartId = null;
      this.clearSelection();
    } else if (event.key.toLowerCase() === 's') {
      this.setTool('select');
    } else if (event.key.toLowerCase() === 'g') {
      this.setTool('gate');
    } else if (event.key.toLowerCase() === 'f') {
      this.setTool('fato');
    } else if (event.key.toLowerCase() === 'n') {
      this.setTool('node');
    } else if (event.key.toLowerCase() === 't') {
      this.setTool('takeoffPoint');
    } else if (event.key.toLowerCase() === 'l') {
      this.setTool('landingPoint');
    } else if (event.key.toLowerCase() === 'c') {
      this.setTool('commonAirPoint');
    } else if (event.key.toLowerCase() === 'k') {
      this.setTool('link');
    }
  }

  /* ---------- internals: state ops ---------- */

  _addEntity(type, x, y) {
    const id = this._nextId(ENTITY_PREFIX[type] || type);
    const entity = {
      id,
      type,
      name: `${ENTITY_LABELS[type]} ${this._countType(type) + 1}`,
      x: this._snapX(x),
      y: this._snapY(y),
    };
    if (type === 'fato') entity.fatoMode = this.fatoMode;
    if (isAirPoint(type)) {
      entity.altitude = DEFAULT_ALTITUDE[type];
    }
    this.layout.entities.push(entity);
    this.selectedId = id;
    this.selectedLinkId = null;
    this._markDirty();
    return entity;
  }

  _handleLinkPick(entity) {
    if (!this.linkStartId) {
      this.linkStartId = entity.id;
      this.selectEntity(entity.id);
      this._emit('tool');
      return;
    }
    const created = this._addLink(this.linkStartId, entity.id);
    if (created) this.linkStartId = entity.id;
    this._emit('tool');
  }

  _addLink(fromId, toId) {
    if (!fromId || !toId || fromId === toId) return null;
    const from = this.layout.entities.find((e) => e.id === fromId);
    const to = this.layout.entities.find((e) => e.id === toId);
    if (!from || !to) return null;

    /* compatibility check: air points only connect to FATO with matching mode */
    const err = this._validateLinkCompat(from, to);
    if (err) {
      console.warn(err);
      return null;
    }
    /* prevent duplicates */
    if (this.layout.links.some((l) => sameEdge(l, fromId, toId))) return null;
    const link = { id: this._nextId('link'), from: fromId, to: toId };
    this.layout.links.push(link);
    this.selectedLinkId = link.id;
    this.selectedId = null;
    this._markDirty();
    return link;
  }

  _validateLinkCompat(a, b) {
    const aAir = isAirPoint(a.type);
    const bAir = isAirPoint(b.type);
    if (!aAir && !bAir) return null;
    let fato, air;
    if (a.type === 'fato' && bAir) { fato = a; air = b; }
    else if (b.type === 'fato' && aAir) { fato = b; air = a; }
    else return '이륙점/착륙점은 FATO와만 연결할 수 있습니다.';
    const mode = fato.fatoMode || 'both';
    if (air.type === 'takeoffPoint' && !['takeoff', 'both'].includes(mode)) {
      return '이륙점은 이륙/공용 FATO와만 연결할 수 있습니다.';
    }
    if (air.type === 'landingPoint' && !['landing', 'both'].includes(mode)) {
      return '착륙점은 착륙/공용 FATO와만 연결할 수 있습니다.';
    }
    if (air.type === 'commonAirPoint' && mode !== 'both') {
      return 'Common air points can only connect to shared FATO.';
    }
    return null;
  }

  _normalizeCoords() {
    if (!this.layout?.entities) return;
    for (const ent of this.layout.entities) {
      ent.x = this._snapX(ent.x);
      ent.y = this._snapY(ent.y);
    }
  }

  _markDirty() {
    this.dirty = true;
    this._emit('layout');
    this._emit('dirty');
  }

  _emit(type) {
    this.dispatchEvent(new CustomEvent('change', { detail: { type } }));
    this.draw();
  }

  /* ---------- internals: helpers ---------- */

  _isPlacementTool() {
    return ['gate', 'fato', 'node', 'takeoffPoint', 'landingPoint', 'commonAirPoint'].includes(this.tool);
  }
  _isInsideGrid(p) {
    const { width, height } = this.layout.grid;
    return p.x >= 0 && p.x <= width && p.y >= 0 && p.y <= height;
  }
  _clampToGrid(p) {
    const { width, height } = this.layout.grid;
    return { x: clamp(p.x, 0, width), y: clamp(p.y, 0, height) };
  }
  _snapX(v) { return clamp(snap(Number(v) || 0, POSITION_SNAP), 0, this.layout?.grid?.width ?? 1e9); }
  _snapY(v) { return clamp(snap(Number(v) || 0, POSITION_SNAP), 0, this.layout?.grid?.height ?? 1e9); }
  _countType(type) { return this.layout.entities.filter((e) => e.type === type).length; }
  _nextId(prefix) {
    const ids = new Set([
      ...this.layout.entities.map((e) => e.id),
      ...this.layout.links.map((l) => l.id),
    ]);
    let i = 1;
    while (ids.has(`${prefix}-${i}`)) i += 1;
    return `${prefix}-${i}`;
  }
  _screenPoint(event) {
    const rect = this.canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }
  _toWorld(p) {
    return { x: (p.x - this.offset.x) / this.scale, y: (p.y - this.offset.y) / this.scale };
  }
  _toScreen(p) {
    return { x: p.x * this.scale + this.offset.x, y: p.y * this.scale + this.offset.y };
  }
  _hitEntity(world) {
    for (let i = this.layout.entities.length - 1; i >= 0; i -= 1) {
      const ent = this.layout.entities[i];
      const r = (RADII[ent.type] || 10) + 6 / this.scale;
      if (Math.hypot(world.x - ent.x, world.y - ent.y) <= r) return ent;
    }
    return null;
  }
  _hitLink(world) {
    const map = new Map(this.layout.entities.map((e) => [e.id, e]));
    for (let i = this.layout.links.length - 1; i >= 0; i -= 1) {
      const link = this.layout.links[i];
      const a = map.get(link.from); const b = map.get(link.to);
      if (!a || !b) continue;
      if (distanceToSegment(world, a, b) <= 8 / this.scale) return link;
    }
    return null;
  }

  /* ---------- drawing ---------- */

  _drawGrid() {
    const { width, height, size } = this.layout.grid;
    const ctx = this.ctx;
    /* surface fill (slightly lighter than canvas backdrop so edges are clear) */
    ctx.fillStyle = COLORS.gridFill;
    ctx.fillRect(0, 0, width, height);

    /* minor lines (every cell, e.g. 20m) */
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 0.6 / this.scale;
    ctx.beginPath();
    for (let x = 0; x <= width; x += size) {
      if (x % (size * 5) === 0) continue;
      ctx.moveTo(x, 0); ctx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += size) {
      if (y % (size * 5) === 0) continue;
      ctx.moveTo(0, y); ctx.lineTo(width, y);
    }
    ctx.stroke();

    /* major lines (every 5 cells, e.g. 100m) */
    ctx.strokeStyle = COLORS.gridMajor;
    ctx.lineWidth = 1.2 / this.scale;
    ctx.beginPath();
    for (let x = 0; x <= width; x += size * 5) {
      ctx.moveTo(x, 0); ctx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += size * 5) {
      ctx.moveTo(0, y); ctx.lineTo(width, y);
    }
    ctx.stroke();

    /* outer boundary */
    ctx.strokeStyle = COLORS.gridBorder;
    ctx.lineWidth = 1.6 / this.scale;
    ctx.strokeRect(0, 0, width, height);
  }

  _drawAxisLabels() {
    const { width, height, size } = this.layout.grid;
    const ctx = this.ctx;
    const step = size * 5;
    /* hide labels when zoomed too far out so they don't clutter */
    if (this.scale < 0.35) return;
    const fs = Math.max(9, 11 / this.scale);
    ctx.save();
    ctx.fillStyle = COLORS.axisLabel;
    ctx.font = `600 ${fs}px var(--mono, "JetBrains Mono"), monospace`;
    ctx.textBaseline = 'top';
    ctx.textAlign = 'center';
    /* top edge: x labels */
    for (let x = 0; x <= width; x += step) {
      ctx.fillText(`${x}`, x, -16 / this.scale);
    }
    /* left edge: y labels */
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let y = 0; y <= height; y += step) {
      ctx.fillText(`${y}`, -8 / this.scale, y);
    }
    ctx.restore();
  }

  _drawHoverGuides() {
    /* thin guide lines (cross-hairs) at the cursor's grid-snapped position */
    if (!this.pointerScreen || !this._isInsideGrid(this.pointer)) return;
    const ctx = this.ctx;
    const { width, height } = this.layout.grid;
    const x = clamp(snap(this.pointer.x, POSITION_SNAP), 0, width);
    const y = clamp(snap(this.pointer.y, POSITION_SNAP), 0, height);
    ctx.save();
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.28)';
    ctx.lineWidth = 1 / this.scale;
    ctx.setLineDash([4 / this.scale, 4 / this.scale]);
    ctx.beginPath();
    ctx.moveTo(x, 0); ctx.lineTo(x, height);
    ctx.moveTo(0, y); ctx.lineTo(width, y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  _drawGhostPlacement() {
    /* When a placement tool is active and cursor is over the grid, show a
     * faint preview of where the new entity will land. */
    if (!this._isPlacementTool() || !this.pointerScreen || !this._isInsideGrid(this.pointer)) return;
    if (this.drag) return;
    const ctx = this.ctx;
    const x = clamp(snap(this.pointer.x, POSITION_SNAP), 0, this.layout.grid.width);
    const y = clamp(snap(this.pointer.y, POSITION_SNAP), 0, this.layout.grid.height);
    const type = this.tool;
    const r = RADII[type];
    const color = entityColor({ type, fatoMode: this.fatoMode });
    ctx.save();
    ctx.globalAlpha = 0.45;
    ctx.translate(x, y);
    if (type === 'node') {
      ctx.beginPath();
      ctx.arc(0, 0, RADII.node, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.node;
      ctx.fill();
    } else if (isAirPoint(type)) {
      ctx.beginPath();
      ctx.moveTo(0, -r); ctx.lineTo(r, 0); ctx.lineTo(0, r); ctx.lineTo(-r, 0); ctx.closePath();
      ctx.fillStyle = COLORS.gridFill;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.4 / this.scale;
      ctx.fill();
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.gridFill;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.4 / this.scale;
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  _drawCoordinateTooltip(rect) {
    if (!this.pointerScreen || !this.layout || !this._isInsideGrid(this.pointer)) return;
    const { width, height } = this.layout.grid;
    const x = clamp(snap(this.pointer.x, POSITION_SNAP), 0, width);
    const y = clamp(snap(this.pointer.y, POSITION_SNAP), 0, height);
    const text = `X ${x} m  ·  Y ${y} m`;
    const ctx = this.ctx;
    ctx.save();
    ctx.font = '700 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const padX = 9, h = 24;
    const w = Math.ceil(ctx.measureText(text).width + padX * 2);
    let bx = this.pointerScreen.x + 14;
    let by = this.pointerScreen.y + 16;
    if (bx + w > rect.width - 8) bx = this.pointerScreen.x - w - 14;
    if (by + h > rect.height - 8) by = this.pointerScreen.y - h - 14;
    bx = clamp(bx, 8, Math.max(8, rect.width - w - 8));
    by = clamp(by, 8, Math.max(8, rect.height - h - 8));
    /* rounded box */
    const r = 6;
    ctx.beginPath();
    ctx.moveTo(bx + r, by);
    ctx.arcTo(bx + w, by, bx + w, by + h, r);
    ctx.arcTo(bx + w, by + h, bx, by + h, r);
    ctx.arcTo(bx, by + h, bx, by, r);
    ctx.arcTo(bx, by, bx + w, by, r);
    ctx.closePath();
    ctx.fillStyle = 'rgba(15, 26, 40, 0.94)';
    ctx.strokeStyle = 'rgba(90, 122, 168, 0.6)';
    ctx.lineWidth = 1;
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = COLORS.text;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, bx + w / 2, by + h / 2 + 0.5);
    ctx.restore();
  }

  _drawLinks() {
    const ctx = this.ctx;
    const map = new Map(this.layout.entities.map((e) => [e.id, e]));
    for (const link of this.layout.links) {
      const a = map.get(link.from); const b = map.get(link.to);
      if (!a || !b) continue;
      const selected = this.selectedLinkId === link.id;
      const airEnd = isAirPoint(a.type) ? a : isAirPoint(b.type) ? b : null;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = selected ? COLORS.selected : airEnd ? COLORS.airLink : COLORS.link;
      ctx.lineWidth = (selected ? 5 : airEnd ? 3.4 : 3.2) / this.scale;
      ctx.lineCap = 'round';
      if (airEnd) ctx.setLineDash([10 / this.scale, 6 / this.scale]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }

  _drawEntities() {
    for (const ent of this.layout.entities) {
      const selected = this.selectedId === ent.id || this.linkStartId === ent.id;
      if (ent.type === 'node') this._drawNode(ent, selected);
      else if (isAirPoint(ent.type)) this._drawAirPoint(ent, selected);
      else this._drawCircleEntity(ent, selected);
    }
  }

  _drawCircleEntity(ent, selected) {
    const ctx = this.ctx;
    const r = RADII[ent.type];
    const color = entityColor(ent);
    ctx.save();
    ctx.translate(ent.x, ent.y);
    if (selected) {
      ctx.beginPath();
      ctx.arc(0, 0, r + 7, 0, Math.PI * 2);
      ctx.strokeStyle = COLORS.selected;
      ctx.lineWidth = 2.5 / this.scale;
      ctx.setLineDash([7 / this.scale, 5 / this.scale]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fillStyle = '#0f1a28';
    ctx.strokeStyle = color;
    ctx.lineWidth = 3 / this.scale;
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = `700 ${Math.max(13 / this.scale, 14)}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(ent.type === 'gate' ? 'G' : 'V', 0, 1);
    ctx.fillStyle = COLORS.text;
    ctx.font = `600 ${12 / this.scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillText(ent.name, 0, r + 16 / this.scale);
    ctx.restore();
  }

  _drawAirPoint(ent, selected) {
    const ctx = this.ctx;
    const r = RADII[ent.type];
    const color = entityColor(ent);
    ctx.save();
    ctx.translate(ent.x, ent.y);
    if (selected) {
      ctx.beginPath();
      ctx.arc(0, 0, r + 8, 0, Math.PI * 2);
      ctx.strokeStyle = COLORS.selected;
      ctx.lineWidth = 2.5 / this.scale;
      ctx.setLineDash([7 / this.scale, 5 / this.scale]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath();
    ctx.moveTo(0, -r); ctx.lineTo(r, 0); ctx.lineTo(0, r); ctx.lineTo(-r, 0); ctx.closePath();
    ctx.fillStyle = '#0f1a28';
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.4 / this.scale;
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = `800 ${Math.max(11 / this.scale, 13)}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(airPointLabel(ent.type), 0, 1);
    ctx.fillStyle = COLORS.text;
    ctx.font = `600 ${11 / this.scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillText(ent.name, 0, r + 14 / this.scale);
    ctx.fillStyle = COLORS.subtext;
    ctx.fillText(`${Math.round(ent.altitude || 0)} m`, 0, r + 28 / this.scale);
    ctx.restore();
  }

  _drawNode(ent, selected) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(ent.x, ent.y);
    if (selected) {
      ctx.beginPath();
      ctx.arc(0, 0, RADII.node + 6, 0, Math.PI * 2);
      ctx.strokeStyle = COLORS.selected;
      ctx.lineWidth = 2 / this.scale;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(0, 0, RADII.node, 0, Math.PI * 2);
    ctx.fillStyle = COLORS.node;
    ctx.fill();
    ctx.fillStyle = COLORS.subtext;
    ctx.font = `600 ${10 / this.scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(ent.name, 0, RADII.node + 4 / this.scale);
    ctx.restore();
  }

  _drawPendingLink() {
    if (this.tool !== 'link' || !this.linkStartId) return;
    const ent = this.layout.entities.find((e) => e.id === this.linkStartId);
    if (!ent) return;
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.moveTo(ent.x, ent.y);
    ctx.lineTo(this.pointer.x, this.pointer.y);
    ctx.strokeStyle = COLORS.selected;
    ctx.lineWidth = 2 / this.scale;
    ctx.setLineDash([6 / this.scale, 6 / this.scale]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function isAirPoint(type) { return type === 'takeoffPoint' || type === 'landingPoint' || type === 'commonAirPoint'; }
function airPointLabel(type) {
  if (type === 'takeoffPoint') return 'T';
  if (type === 'landingPoint') return 'L';
  return 'C';
}
function entityColor(ent) {
  if (ent.type === 'fato') {
    if (ent.fatoMode === 'takeoff') return COLORS.fatoTakeoff;
    if (ent.fatoMode === 'landing') return COLORS.fatoLanding;
    return COLORS.fato;
  }
  return COLORS[ent.type] || COLORS.node;
}
function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
function snap(v, s) { return Math.round(v / s) * s; }
function sameEdge(link, a, b) {
  return (link.from === a && link.to === b) || (link.from === b && link.to === a);
}
function distanceToSegment(p, a, b) {
  const dx = b.x - a.x; const dy = b.y - a.y;
  if (dx === 0 && dy === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  const t = clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy), 0, 1);
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

window.LayoutEditor = {
  create(canvas, opts) { return new LayoutEditor(canvas, opts); },
  blankLayout,
};
