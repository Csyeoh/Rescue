export interface Point {
  x: number;
  y: number;
}

/**
 * Groups adjacent points into contiguous clusters.
 * Uses a basic flood-fill algorithm (4-way connectivity).
 */
export function clusterTiles(tiles: Point[]): Point[][] {
  const clusters: Point[][] = [];
  const unvisited = new Set(tiles.map(t => `${t.x},${t.y}`));

  while (unvisited.size > 0) {
    // Get an unvisited starting point
    const startObj = unvisited.values().next().value;
    if (!startObj) break;

    const [sx, sy] = startObj.split(',').map(Number);
    const cluster: Point[] = [];
    const queue: Point[] = [{ x: sx, y: sy }];
    unvisited.delete(startObj);
    
    while (queue.length > 0) {
      const curr = queue.shift()!;
      cluster.push(curr);
      
      const neighbors = [
        { x: curr.x + 1, y: curr.y },
        { x: curr.x - 1, y: curr.y },
        { x: curr.x, y: curr.y + 1 },
        { x: curr.x, y: curr.y - 1 }
      ];
      
      for (const n of neighbors) {
        const key = `${n.x},${n.y}`;
        if (unvisited.has(key)) {
          unvisited.delete(key);
          queue.push(n);
        }
      }
    }
    clusters.push(cluster);
  }
  return clusters;
}

/**
 * Traces the boundary edges of a tile cluster.
 * Returns an array of paths (loops). Supports clusters with holes.
 * The tile is defined from (x, y) to (x+1, y+1) locally.
 */
export function traceBoundaryPaths(cluster: Point[]): Point[][] {
  // Directed edges. Format for start,end keys: "x1,y1|x2,y2"
  const edges = new Map<string, {start: Point, end: Point}>();
  
  for (const c of cluster) {
    // Top edge: ->
    const top = { start: { x: c.x, y: c.y }, end: { x: c.x + 1, y: c.y } };
    // Right edge: v
    const right = { start: { x: c.x + 1, y: c.y }, end: { x: c.x + 1, y: c.y + 1 } };
    // Bottom edge: <-
    const bottom = { start: { x: c.x + 1, y: c.y + 1 }, end: { x: c.x, y: c.y + 1 } };
    // Left edge: ^
    const left = { start: { x: c.x, y: c.y + 1 }, end: { x: c.x, y: c.y } };
    
    const tileEdges = [top, right, bottom, left];
    for (const e of tileEdges) {
      const forwardKey = `${e.start.x},${e.start.y}|${e.end.x},${e.end.y}`;
      const backwardKey = `${e.end.x},${e.end.y}|${e.start.x},${e.start.y}`;
      
      // If the backward edge exists, it means the adjacent tile shares this edge.
      // They cancel each other out (leaving only exterior perimeter edges).
      if (edges.has(backwardKey)) {
        edges.delete(backwardKey);
      } else {
        edges.set(forwardKey, e);
      }
    }
  }

  // To build loops, we repeatedly extract connected edges.
  const edgeMap = new Map<string, {start: Point, end: Point}>();
  for (const e of edges.values()) {
    edgeMap.set(`${e.start.x},${e.start.y}`, e);
  }

  const loops: Point[][] = [];
  
  while (edgeMap.size > 0) {
    let currentEdge = edgeMap.values().next().value;
    if (!currentEdge) break;

    const startKey = `${currentEdge.start.x},${currentEdge.start.y}`;
    const loop: Point[] = [];
    
    while (currentEdge) {
      loop.push(currentEdge.start);
      edgeMap.delete(`${currentEdge.start.x},${currentEdge.start.y}`);
      
      const nextKey = `${currentEdge.end.x},${currentEdge.end.y}`;
      if (nextKey === startKey) {
        break; // Closed the loop
      }
      
      currentEdge = edgeMap.get(nextKey);
      if (!currentEdge) {
        break; 
      }
    }
    // Shrink the loop slightly to create gaps before smoothing
    const shrunkLoop = shrinkPolygon(loop, 0.15); // inset by roughly 15% towards centroid
    loops.push(chaikinSmooth(shrunkLoop, 3)); // Apply strong smoothing over 3 iterations for organic blob borders
  }
  
  return loops;
}

/**
 * Mathematically scales a polygon inwards towards its centroid.
 */
export function shrinkPolygon(loop: Point[], insetRatio: number): Point[] {
  if (loop.length === 0) return [];
  
  let cx = 0;
  let cy = 0;
  for (const p of loop) {
    cx += p.x;
    cy += p.y;
  }
  cx /= loop.length;
  cy /= loop.length;
  
  return loop.map(p => ({
    x: p.x + (cx - p.x) * insetRatio,
    y: p.y + (cy - p.y) * insetRatio
  }));
}

/**
 * Chaikin's Corner Cutting Algorithm 
 * Converts hard right-angle arrays into smooth bezier-like organic curves.
 */
export function chaikinSmooth(loop: Point[], iterations: number = 1): Point[] {
  if (loop.length === 0) return [];
  let current = [...loop];
  
  for (let iter = 0; iter < iterations; iter++) {
    const next: Point[] = [];
    for (let i = 0; i < current.length; i++) {
      const p1 = current[i];
      const p2 = current[(i + 1) % current.length];
      
      // Cut at 20% and 80% to maintain good area volume but deep organic rounding
      next.push({ x: p1.x * 0.8 + p2.x * 0.2, y: p1.y * 0.8 + p2.y * 0.2 });
      next.push({ x: p1.x * 0.2 + p2.x * 0.8, y: p1.y * 0.2 + p2.y * 0.8 });
    }
    current = next;
  }
  return current;
}

/**
 * Builds an SVG 'd' path string from the boundary loops.
 */
export function buildSvgPath(loops: Point[][], scaleMultiplier: number): string {
  if (loops.length === 0) return '';
  return loops.map(loop => {
    // Start at first point (M), log remaining lines (L), close path (Z)
    const points = loop.map((p, i) => {
      const x = p.x * scaleMultiplier;
      const y = p.y * scaleMultiplier;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
    return `${points} Z`;
  }).join(' ');
}
