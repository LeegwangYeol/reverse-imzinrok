/**
 * 8-Directional A* Pathfinding Engine with Corner-Cutting Prevention,
 * Elevation Step Constraints, and Line-of-Sight Path Smoothing.
 */

/**
 * Min-Heap Priority Queue for high-speed A* node processing.
 */
export class BinaryHeap {
    /**
     * @param {function(any): number} scoreFunction - Returns numerical priority (lower is higher priority)
     */
    constructor(scoreFunction) {
        this.content = [];
        this.scoreFunction = scoreFunction;
    }

    push(element) {
        this.content.push(element);
        this.bubbleUp(this.content.length - 1);
    }

    pop() {
        const result = this.content[0];
        const end = this.content.pop();
        if (this.content.length > 0) {
            this.content[0] = end;
            this.sinkDown(0);
        }
        return result;
    }

    peek() {
        return this.content[0];
    }

    size() {
        return this.content.length;
    }

    bubbleUp(n) {
        const element = this.content[n];
        const score = this.scoreFunction(element);
        while (n > 0) {
            const parentN = Math.floor((n + 1) / 2) - 1;
            const parent = this.content[parentN];
            if (score >= this.scoreFunction(parent)) break;
            this.content[parentN] = element;
            this.content[n] = parent;
            n = parentN;
        }
    }

    sinkDown(n) {
        const length = this.content.length;
        const element = this.content[n];
        const elemScore = this.scoreFunction(element);

        while (true) {
            const child2N = (n + 1) * 2;
            const child1N = child2N - 1;
            let swap = null;
            let child1Score;

            if (child1N < length) {
                const child1 = this.content[child1N];
                child1Score = this.scoreFunction(child1);
                if (child1Score < elemScore) {
                    swap = child1N;
                }
            }

            if (child2N < length) {
                const child2 = this.content[child2N];
                const child2Score = this.scoreFunction(child2);
                if (child2Score < (swap === null ? elemScore : child1Score)) {
                    swap = child2N;
                }
            }

            if (swap === null) break;

            this.content[n] = this.content[swap];
            this.content[swap] = element;
            n = swap;
        }
    }
}

export class PathFinder {
    /**
     * Finds the shortest walkable path between start and target on the grid.
     *
     * @param {Object} grid - GameGrid instance
     * @param {number} startGx - Starting tile grid X
     * @param {number} startGy - Starting tile grid Y
     * @param {number} targetGx - Target tile grid X
     * @param {number} targetGy - Target tile grid Y
     * @param {Object} [options={}] - Search configuration
     * @param {number} [options.maxSearchNodes=2000] - Search node limit to prevent lag
     * @param {boolean} [options.smooth=true] - Whether to apply line-of-sight path smoothing
     * @param {boolean} [options.ignoreUnits=true] - Whether to ignore unit occupancy
     * @returns {Array<{ gx: number, gy: number }>} List of path waypoints
     */
    static findPath(grid, startGx, startGy, targetGx, targetGy, options = {}) {
        const maxSearchNodes = options.maxSearchNodes || 2000;
        const smooth = options.smooth !== undefined ? options.smooth : true;
        const ignoreUnits = options.ignoreUnits !== undefined ? options.ignoreUnits : true;

        // If start is same as target, no movement needed
        if (startGx === targetGx && startGy === targetGy) {
            return [];
        }

        // Clamp coordinates within bounds
        startGx = Math.max(0, Math.min(grid.width - 1, Math.floor(startGx)));
        startGy = Math.max(0, Math.min(grid.height - 1, Math.floor(startGy)));
        targetGx = Math.max(0, Math.min(grid.width - 1, Math.floor(targetGx)));
        targetGy = Math.max(0, Math.min(grid.height - 1, Math.floor(targetGy)));

        // If target is unwalkable, redirect to nearest walkable adjacent tile
        if (!grid.isWalkable(targetGx, targetGy, ignoreUnits)) {
            const nearest = this.findNearestWalkable(grid, targetGx, targetGy, ignoreUnits);
            if (!nearest) return [];
            targetGx = nearest.gx;
            targetGy = nearest.gy;
            if (startGx === targetGx && startGy === targetGy) return [];
        }

        const width = grid.width;
        const height = grid.height;
        const startIdx = startGy * width + startGx;
        const targetIdx = targetGy * width + targetGx;

        const openSet = new BinaryHeap((node) => node.f);
        const closedSet = new Uint8Array(grid.size);
        const gScores = new Float32Array(grid.size).fill(Infinity);
        const parents = new Int32Array(grid.size).fill(-1);

        gScores[startIdx] = 0;
        const h0 = this.heuristic(startGx, startGy, targetGx, targetGy);
        openSet.push({ idx: startIdx, gx: startGx, gy: startGy, f: h0 });

        let nodesExamined = 0;

        // 8-directional movement offsets: [dx, dy, cost]
        // Orthogonal: 10, Diagonal: 14 (~10 * sqrt(2))
        const neighbors = [
            [0, -1, 10],  // N
            [1, 0, 10],   // E
            [0, 1, 10],   // S
            [-1, 0, 10],  // W
            [1, -1, 14],  // NE
            [1, 1, 14],   // SE
            [-1, 1, 14],  // SW
            [-1, -1, 14]  // NW
        ];

        while (openSet.size() > 0 && nodesExamined < maxSearchNodes) {
            nodesExamined++;
            const current = openSet.pop();
            const currIdx = current.idx;

            if (currIdx === targetIdx) {
                const rawPath = this.reconstructPath(parents, currIdx, width);
                return smooth ? this.smoothPath(grid, rawPath, startGx, startGy) : rawPath;
            }

            closedSet[currIdx] = 1;
            const currElev = grid.elevation[currIdx];

            for (let i = 0; i < 8; i++) {
                const [dx, dy, cost] = neighbors[i];
                const ngx = current.gx + dx;
                const ngy = current.gy + dy;

                if (ngx < 0 || ngx >= width || ngy < 0 || ngy >= height) continue;
                const nIdx = ngy * width + ngx;
                if (closedSet[nIdx]) continue;

                // Passability check
                if (!grid.isWalkable(ngx, ngy, ignoreUnits)) continue;

                // Elevation step limit (max height difference 1 between adjacent tiles)
                const nextElev = grid.elevation[nIdx];
                if (Math.abs(nextElev - currElev) > 1) continue;

                // Corner-cutting prevention for diagonal moves
                if (dx !== 0 && dy !== 0) {
                    const c1x = current.gx + dx;
                    const c1y = current.gy;
                    const c2x = current.gx;
                    const c2y = current.gy + dy;

                    if (!grid.isWalkable(c1x, c1y, ignoreUnits) ||
                        !grid.isWalkable(c2x, c2y, ignoreUnits)) {
                        continue;
                    }

                    // Cliff elevation corner check: neither adjacent corner tile can be a cliff (>1 elevation delta)
                    const e1 = grid.getElevation(c1x, c1y);
                    const e2 = grid.getElevation(c2x, c2y);
                    if (Math.abs(e1 - currElev) > 1 || Math.abs(e2 - currElev) > 1 ||
                        Math.abs(e1 - nextElev) > 1 || Math.abs(e2 - nextElev) > 1) {
                        continue;
                    }
                }

                const tentativeG = gScores[currIdx] + cost;
                if (tentativeG < gScores[nIdx]) {
                    parents[nIdx] = currIdx;
                    gScores[nIdx] = tentativeG;
                    const f = tentativeG + this.heuristic(ngx, ngy, targetGx, targetGy);
                    openSet.push({ idx: nIdx, gx: ngx, gy: ngy, f });
                }
            }
        }

        return []; // No path found within search budget
    }

    /**
     * Octile distance heuristic for 8-directional movement.
     */
    static heuristic(x1, y1, x2, y2) {
        const dx = Math.abs(x1 - x2);
        const dy = Math.abs(y1 - y2);
        return 10 * (dx + dy) + (14 - 20) * Math.min(dx, dy);
    }

    /**
     * Backtracks parent pointers to build path array from start to target.
     */
    static reconstructPath(parents, targetIdx, width) {
        const path = [];
        let curr = targetIdx;
        while (curr !== -1) {
            path.push({
                gx: curr % width,
                gy: Math.floor(curr / width)
            });
            curr = parents[curr];
        }
        path.reverse();
        path.shift(); // Remove starting tile itself
        return path;
    }

    /**
     * Searches outward in expanding rings to find the nearest walkable tile.
     *
     * @param {Object} grid - GameGrid instance
     * @param {number} gx - Center grid X
     * @param {number} gy - Center grid Y
     * @param {boolean} [ignoreUnits=true]
     * @param {number} [maxRadius=5]
     * @returns {{ gx: number, gy: number }|null} Nearest walkable coordinate
     */
    static findNearestWalkable(grid, gx, gy, ignoreUnits = true, maxRadius = 5) {
        for (let r = 1; r <= maxRadius; r++) {
            for (let dy = -r; dy <= r; dy++) {
                for (let dx = -r; dx <= r; dx++) {
                    if (Math.abs(dx) !== r && Math.abs(dy) !== r) continue;
                    const nx = gx + dx;
                    const ny = gy + dy;
                    if (grid.isWalkable(nx, ny, ignoreUnits)) {
                        return { gx: nx, gy: ny };
                    }
                }
            }
        }
        return null;
    }

    /**
     * Performs line-of-sight raycasting to eliminate redundant zig-zag waypoints.
     *
     * @param {Object} grid - GameGrid instance
     * @param {Array<{ gx: number, gy: number }>} path - Raw A* waypoints
     * @param {number} startGx - Start tile X
     * @param {number} startGy - Start tile Y
     * @returns {Array<{ gx: number, gy: number }>} Smoothed waypoint list
     */
    static smoothPath(grid, path, startGx, startGy) {
        if (!path || path.length <= 2) return path;

        const fullPath = [{ gx: startGx, gy: startGy }, ...path];
        const smoothed = [];
        let currentIdx = 0;

        while (currentIdx < fullPath.length - 1) {
            let furthestVisible = currentIdx + 1;

            // Look ahead for the furthest directly visible waypoint
            for (let testIdx = fullPath.length - 1; testIdx > currentIdx + 1; testIdx--) {
                if (this.hasLineOfSight(grid, fullPath[currentIdx], fullPath[testIdx])) {
                    furthestVisible = testIdx;
                    break;
                }
            }

            smoothed.push(fullPath[furthestVisible]);
            currentIdx = furthestVisible;
        }

        return smoothed;
    }

    /**
     * Tests if an unobstructed straight line of sight exists between two tiles.
     *
     * @param {Object} grid - GameGrid instance
     * @param {{ gx: number, gy: number }} p1 - Starting tile
     * @param {{ gx: number, gy: number }} p2 - Ending tile
     * @returns {boolean} True if unobstructed line exists
     */
    static hasLineOfSight(grid, p1, p2) {
        let x0 = p1.gx;
        let y0 = p1.gy;
        const x1 = p2.gx;
        const y1 = p2.gy;

        const dx = Math.abs(x1 - x0);
        const dy = Math.abs(y1 - y0);
        const sx = (x0 < x1) ? 1 : -1;
        const sy = (y0 < y1) ? 1 : -1;
        let err = dx - dy;

        let prevX = x0;
        let prevY = y0;
        let prevElev = grid.getElevation(prevX, prevY);

        while (true) {
            if (x0 === x1 && y0 === y1) break;

            const e2 = 2 * err;
            let stepX = 0;
            let stepY = 0;

            if (e2 > -dy) {
                err -= dy;
                x0 += sx;
                stepX = sx;
            }
            if (e2 < dx) {
                err += dx;
                y0 += sy;
                stepY = sy;
            }

            // Boundary check
            if (!grid.isValid(x0, y0)) return false;

            // Passability check
            if (!grid.isWalkable(x0, y0)) return false;

            // Elevation step limit (max height difference 1)
            const currElev = grid.getElevation(x0, y0);
            if (Math.abs(currElev - prevElev) > 1) return false;

            // Corner cutting check for diagonal step
            if (stepX !== 0 && stepY !== 0) {
                const c1x = prevX + stepX;
                const c1y = prevY;
                const c2x = prevX;
                const c2y = prevY + stepY;

                if (!grid.isWalkable(c1x, c1y) || !grid.isWalkable(c2x, c2y)) {
                    return false;
                }

                // Cliff elevation corner check: neither adjacent corner tile can be a cliff (>1 elevation delta)
                const e1 = grid.getElevation(c1x, c1y);
                const e2 = grid.getElevation(c2x, c2y);
                if (Math.abs(e1 - prevElev) > 1 || Math.abs(e2 - prevElev) > 1 ||
                    Math.abs(e1 - currElev) > 1 || Math.abs(e2 - currElev) > 1) {
                    return false;
                }
            }

            prevX = x0;
            prevY = y0;
            prevElev = currElev;
        }

        return true;
    }
}
