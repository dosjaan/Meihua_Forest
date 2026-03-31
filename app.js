const TOKENS = ["EMPTY", "R2", "R1", "FAKE"];
const EXIT_BLOCKS = new Set([10, 12]);
const ENTRANCE_LINKS = [2];
const ENTRANCE_HEIGHT = 0;
const STEP_MM = 600;
const FORBIDDEN_R1_BLOCKS = new Set([5, 8]);
const R1_AVOID_RADIUS = 2;

const DEFAULT_HEIGHTS = {
  1: 400, 2: 200, 3: 400,
  4: 200, 5: 400, 6: 600,
  7: 400, 8: 600, 9: 400,
  10: 200, 11: 400, 12: 200,
};

const GRAPH = {
  1: [2, 4],
  2: [1, 3, 5],
  3: [2, 6],
  4: [1, 5, 7],
  5: [2, 4, 6, 8],
  6: [3, 5, 9],
  7: [4, 8, 10],
  8: [5, 7, 9, 11],
  9: [6, 8, 12],
  10: [7, 11],
  11: [8, 10, 12],
  12: [9, 11],
};

let autoState = {
  blocks: createDefaultBlocks(),
  plans: [],
  selectedPlan: null,
};

let manualState = {
  blocks: createDefaultBlocks(),
  plans: [],
  selectedPlan: null,
};

let planningMode = "practical";

function createDefaultBlocks() {
  const blocks = [];
  for (let id = 1; id <= 12; id += 1) {
    blocks.push({ id, h: DEFAULT_HEIGHTS[id], token: "EMPTY" });
  }
  return blocks;
}

function cloneBlocks(blocks) {
  return blocks.map((b) => ({ ...b }));
}

function setupTabs() {
  const autoBtn = document.getElementById("tab-auto-btn");
  const manualBtn = document.getElementById("tab-manual-btn");
  const autoTab = document.getElementById("tab-auto");
  const manualTab = document.getElementById("tab-manual");

  autoBtn.addEventListener("click", () => {
    autoBtn.classList.add("active");
    manualBtn.classList.remove("active");
    autoTab.classList.add("active");
    manualTab.classList.remove("active");
    autoBtn.setAttribute("aria-selected", "true");
    manualBtn.setAttribute("aria-selected", "false");
  });

  manualBtn.addEventListener("click", () => {
    manualBtn.classList.add("active");
    autoBtn.classList.remove("active");
    manualTab.classList.add("active");
    autoTab.classList.remove("active");
    manualBtn.setAttribute("aria-selected", "true");
    autoBtn.setAttribute("aria-selected", "false");
  });

  const modeSelect = document.getElementById("planning-mode");
  if (modeSelect) {
    modeSelect.value = planningMode;
    modeSelect.addEventListener("change", () => {
      planningMode = modeSelect.value;
      autoState.plans = [];
      autoState.selectedPlan = null;
      manualState.plans = [];
      manualState.selectedPlan = null;
      document.getElementById("auto-summary").innerHTML = "";
      document.getElementById("auto-results").innerHTML = "";
      document.getElementById("manual-results").innerHTML = "";
      document.getElementById("manual-validation").innerHTML = "";
      renderAuto();
      renderManual();
    });
  }
}

function tokenClass(token) {
  if (token === "R2") return "kfs-r2";
  if (token === "R1") return "kfs-r1";
  if (token === "FAKE") return "kfs-fake";
  return "kfs-empty";
}

function blockBgByHeight(h) {
  if (h === 200) return "rgb(41,82,16)";
  if (h === 400) return "rgb(42,113,56)";
  return "rgb(152,166,80)";
}

function getBlock(blocks, id) {
  return blocks.find((b) => b.id === id);
}

function getNeighbors(node) {
  if (node === "E") return ENTRANCE_LINKS.slice();
  return GRAPH[node] || [];
}

function getHeight(blocks, node) {
  if (node === "E") return ENTRANCE_HEIGHT;
  return getBlock(blocks, node).h;
}

function validateMove(blocks, from, to) {
  const connected = getNeighbors(from).includes(to);
  if (!connected) return { ok: false, reason: "Not adjacent" };

  // Violation rule: R2 touching Fake KFS is not allowed.
  // R1 KFS blocks are passable only after waiting for R1 to collect.
  const toBlock = to === "E" ? null : getBlock(blocks, to);
  if (toBlock && toBlock.token === "FAKE") {
    return { ok: false, reason: "Violation: touched FAKE KFS" };
  }

  const dh = Math.abs(getHeight(blocks, to) - getHeight(blocks, from));
  if (dh > 200) return { ok: false, reason: "|Δh| > 200mm" };
  if (from === "E" && dh !== 200) return { ok: false, reason: "Entry boundary must be exactly 200mm" };

  const angle = (Math.atan2(dh, STEP_MM) * 180) / Math.PI;
  if (angle > 20) return { ok: false, reason: "Slope > 20°" };

  return { ok: true, reason: "OK", dh };
}

function validateExitBoundary(blocks, exitBlockId) {
  if (!EXIT_BLOCKS.has(exitBlockId)) return { ok: false, reason: "Not a valid exit block" };
  const dh = Math.abs(getHeight(blocks, exitBlockId) - ENTRANCE_HEIGHT);
  if (dh !== 200) return { ok: false, reason: "Exit boundary must be exactly 200mm" };
  return { ok: true, reason: "OK" };
}

function shortestPath(blocks, start, goal) {
  const queue = [{ node: start, cost: 0 }];
  const prev = new Map();
  const dist = new Map();
  dist.set(start, 0);

  while (queue.length > 0) {
    queue.sort((a, b) => a.cost - b.cost);
    const current = queue.shift();

    if (current.node === goal) break;
    for (const nb of getNeighbors(current.node)) {
      const mv = validateMove(blocks, current.node, nb);
      if (!mv.ok) continue;

      const stepCost = 1 + mv.dh / 200;
      const nd = current.cost + stepCost;
      if (!dist.has(nb) || nd < dist.get(nb)) {
        dist.set(nb, nd);
        prev.set(nb, current.node);
        queue.push({ node: nb, cost: nd });
      }
    }
  }

  if (!dist.has(goal)) return null;

  const path = [];
  let cur = goal;
  while (cur !== undefined) {
    path.push(cur);
    cur = prev.get(cur);
  }
  path.reverse();
  return path;
}

function pathCost(blocks, path) {
  if (!path || path.length <= 1) return 0;
  let cost = 0;
  for (let i = 1; i < path.length; i += 1) {
    const mv = validateMove(blocks, path[i - 1], path[i]);
    if (!mv.ok) return Infinity;
    cost += 1 + mv.dh / 200;
  }
  return cost;
}

function canPickupFrom(currentNode, targetBlockId) {
  return getNeighbors(currentNode).includes(targetBlockId);
}

function countR1TouchesOnPath(blocks, path) {
  if (!path || path.length === 0) return 0;
  let n = 0;
  for (const node of path) {
    if (node === "E") continue;
    const b = getBlock(blocks, node);
    if (b && b.token === "R1") n += 1;
  }
  return n;
}

function getAdjacentR2Targets(blocks, node) {
  const out = [];
  for (const nb of getNeighbors(node)) {
    const b = getBlock(blocks, nb);
    if (b && b.token === "R2") out.push(nb);
  }
  return out;
}

function getPickupAnchors(targetBlockId) {
  const anchors = new Set(getNeighbors(targetBlockId));
  if (ENTRANCE_LINKS.includes(targetBlockId)) anchors.add("E");
  return Array.from(anchors);
}

function planPickupSequence(blocks, startNode, pickupOrder) {
  let best = null;

  function dfs(idx, currentNode, parts, totalCost, totalTouch) {
    if (idx === pickupOrder.length) {
      best = { parts, endNode: currentNode, totalCost, totalTouch };
      return;
    }

    const target = pickupOrder[idx];
    const anchors = getPickupAnchors(target);
    for (const anchor of anchors) {
      const seg = shortestPath(blocks, currentNode, anchor);
      if (!seg) continue;
      if (!canPickupFrom(anchor, target)) continue;
      const segCost = pathCost(blocks, seg);
      if (!Number.isFinite(segCost)) continue;
      const segTouch = countR1TouchesOnPath(blocks, seg);

      const nextCost = totalCost + segCost;
      const nextTouch = totalTouch + segTouch;
      if (best) {
        if (nextCost > best.totalCost) continue;
        if (nextCost === best.totalCost && nextTouch >= best.totalTouch) continue;
      }
      dfs(idx + 1, anchor, parts.concat([seg]), nextCost, nextTouch);
    }
  }

  dfs(0, startNode, [], 0, 0);
  return best;
}

function findNearestPickupFromEntrance(blocks, targets) {
  let bestTarget = null;
  let bestCost = Infinity;
  for (const t of targets) {
    const anchors = getPickupAnchors(t);
    for (const a of anchors) {
      const seg = shortestPath(blocks, "E", a);
      if (!seg) continue;
      if (!canPickupFrom(a, t)) continue;
      const c = pathCost(blocks, seg);
      if (c < bestCost) {
        bestCost = c;
        bestTarget = t;
      }
    }
  }
  return bestTarget;
}

function encounterOrderAlongRoute(blocks, route) {
  const order = [];
  const seen = new Set();
  for (const node of route) {
    const candidates = getAdjacentR2Targets(blocks, node);
    for (const t of candidates) {
      if (!seen.has(t)) {
        seen.add(t);
        order.push(t);
      }
    }
  }
  return order;
}

function combinePaths(parts) {
  const result = [];
  parts.forEach((segment, idx) => {
    if (!segment || segment.length === 0) return;
    if (idx === 0) {
      result.push(...segment);
    } else {
      result.push(...segment.slice(1));
    }
  });
  return result;
}

function permutation(list) {
  if (list.length <= 1) return [list.slice()];
  const out = [];
  for (let i = 0; i < list.length; i += 1) {
    const head = list[i];
    const rest = list.slice(0, i).concat(list.slice(i + 1));
    for (const p of permutation(rest)) {
      out.push([head, ...p]);
    }
  }
  return out;
}

function combinations(arr, size) {
  const out = [];
  function pick(start, cur) {
    if (cur.length === size) {
      out.push(cur.slice());
      return;
    }
    for (let i = start; i < arr.length; i += 1) {
      cur.push(arr[i]);
      pick(i + 1, cur);
      cur.pop();
    }
  }
  pick(0, []);
  return out;
}

function validateLayout(blocks, strict = true) {
  const errors = [];
  const counts = { R2: 0, R1: 0, FAKE: 0 };

  blocks.forEach((b) => {
    if (b.token === "R2") counts.R2 += 1;
    if (b.token === "R1") {
      counts.R1 += 1;
      if (FORBIDDEN_R1_BLOCKS.has(b.id)) {
        errors.push(`R1 KFS cannot be placed on block ${b.id}.`);
      }
    }
    if (b.token === "FAKE") {
      counts.FAKE += 1;
      if ([1, 2, 3].includes(b.id)) {
        errors.push("Fake KFS cannot be placed on entrance blocks 1,2,3.");
      }
    }
  });

  if (strict) {
    if (counts.R2 !== 4) errors.push("R2 KFS count must be exactly 4.");
    if (counts.R1 !== 3) errors.push("R1 KFS count must be exactly 3.");
    if (counts.FAKE !== 1) errors.push("Fake KFS count must be exactly 1.");
  } else {
    if (counts.R2 < 1) errors.push("Need at least 1 R2 KFS for planning.");
  }

  return { ok: errors.length === 0, errors, counts };
}

function evaluatePlan(blocks, route, pickups, scenarioLabel = "") {
  let steps = 0;
  let climb = 0;
  let riskyEdges = 0;
  let climbActions = 0;
  let descendActions = 0;
  let pickupActions = 0;
  let dropActions = 0;
  let gripOccupied = false;
  let waitActions = 0;
  let r1TouchCount = 0;
  let r1NearCount = 0;
  let r1ProximityCost = 0;
  let policyDropActions = 0;
  let policyPenalty = 0;

  for (let i = 1; i < route.length; i += 1) {
    const from = route[i - 1];
    const to = route[i];
    const mv = validateMove(blocks, from, to);
    if (!mv.ok) {
      return { valid: false, reason: mv.reason };
    }
    steps += 1;
    const delta = getHeight(blocks, to) - getHeight(blocks, from);
    climb += Math.max(0, delta);
    if (delta > 0) climbActions += 1;
    if (delta < 0) descendActions += 1;
    if (mv.dh === 200) riskyEdges += 1;
  }

  // User strategy rule: R2 should stay as far as possible from R1 scroll zones.
  // We model this as a proximity penalty on path nodes vs nearest R1 block.
  const r1Blocks = blocks.filter((b) => b.token === "R1").map((b) => b.id);
  if (r1Blocks.length > 0) {
    for (const node of route) {
      const d = minHopDistance(node, r1Blocks);
      if (d === 0) {
        r1TouchCount += 1;
        waitActions += 1;
      }
      if (d === 1) r1NearCount += 1;
      if (d <= R1_AVOID_RADIUS) {
        r1ProximityCost += (R1_AVOID_RADIUS + 1 - d);
      }
    }
  }

  // User rule: if grip already has a box and next R2 box is to be picked,
  // robot drops current grip box first, then picks.
  for (const _pickupBlock of pickups) {
    if (gripOccupied) {
      dropActions += 1;
      gripOccupied = false;
    }
    pickupActions += 1;
    gripOccupied = true;
  }

  // First/last pickup policy is used only in strict mode.
  if (planningMode === "strict") {
    const encounter = encounterOrderAlongRoute(blocks, route);
    if (encounter.length > 0 && pickups.length > 0) {
      const preferredFirst = encounter[0];
      const preferredLast = encounter[encounter.length - 1];
      const nearestFromEntry = findNearestPickupFromEntrance(blocks, encounter) || preferredFirst;

      if (pickups[0] !== preferredFirst && pickups[0] !== nearestFromEntry) {
        policyPenalty += 8;
      }
      if (pickups[pickups.length - 1] !== preferredLast) {
        policyPenalty += 6;
      }
      for (const p of pickups) {
        if (p !== preferredFirst && p !== preferredLast) {
          policyDropActions += 1;
        }
      }
    }
    dropActions += policyDropActions;
  }

  const terrainActions = climbActions + descendActions;
  const ops = pickupActions + dropActions + waitActions + terrainActions;
  const pickupTime = pickupActions * 0.8 + dropActions * 0.6;
  const waitTime = waitActions * 1.4;
  const moveTime = steps * 1.2;
  const time = +(pickupTime + waitTime + moveTime).toFixed(2);
  const energy = +(steps * 0.1 + climb * 0.002).toFixed(2);
  const oneScrollPenalty = pickups.length === 1 ? 10 : 0;
  const strategicExitPoints = planningMode === "strict" && route[route.length - 1] === 10 ? 8 : 0;
  const exitBlock = route[route.length - 1];
  const exitBlockObj = getBlock(blocks, exitBlock);
  const hasExitPickup = pickups.includes(exitBlock);
  const exitPickupPoints = exitBlockObj && exitBlockObj.token === "R2" && hasExitPickup ? 7 : 0;
  const missedExitPickupPenalty = exitBlockObj && exitBlockObj.token === "R2" && !hasExitPickup ? 7 : 0;
  const risk = +(riskyEdges * 1.5 + dropActions * 1.2 + waitActions * 1.4 + r1ProximityCost * 1.6).toFixed(2);
  const modeIsPractical = planningMode === "practical";
  const opWeight = modeIsPractical ? 4.5 : 2.5;
  const riskWeight = modeIsPractical ? 1.3 : 1.8;
  const waitDropPenalty = waitActions * 4 + dropActions * 3;
  const score = +(time * 1 + risk * riskWeight + steps * 0.3 + energy * 0.7 + ops * opWeight + waitDropPenalty + oneScrollPenalty + missedExitPickupPenalty + policyPenalty - strategicExitPoints - exitPickupPoints).toFixed(2);

  return {
    valid: true,
    scenarioLabel,
    route,
    pickups,
    exit: route[route.length - 1],
    steps,
    climb,
    time,
    energy,
    risk,
    pickupActions,
    dropActions,
    waitActions,
    climbActions,
    descendActions,
    terrainActions,
    ops,
    waitDropActions: waitActions + dropActions,
    waitDropPenalty,
    r1TouchCount,
    r1NearCount,
    r1ProximityCost: +r1ProximityCost.toFixed(2),
    policyDropActions,
    policyPenalty,
    oneScrollPenalty,
    strategicExitPoints,
    exitPickupPoints,
    missedExitPickupPenalty,
    score,
  };
}

function computePlans(blocks, topN = 5) {
  const r2Blocks = blocks.filter((b) => b.token === "R2").map((b) => b.id);
  if (r2Blocks.length === 0) return [];

  const targetSets = [];
  const preferredSizes = r2Blocks.length >= 2 ? [2, 1] : [1];
  for (const size of preferredSizes) {
    for (const group of combinations(r2Blocks, size)) targetSets.push(group);
  }

  const plans = [];

  for (const targets of targetSets) {
    for (const order of permutation(targets)) {
      for (const exit of EXIT_BLOCKS) {
        const exitBlockObj = getBlock(blocks, exit);
        if (exitBlockObj && exitBlockObj.token === "R2" && !order.includes(exit)) {
          // Hard rule: if exit block has R2 KFS, pickup list must include that exit block.
          continue;
        }

        let current = "E";
        const parts = [];
        const pickupPlan = planPickupSequence(blocks, current, order);
        if (!pickupPlan) continue;
        parts.push(...pickupPlan.parts);
        current = pickupPlan.endNode;

        const exitSeg = shortestPath(blocks, current, exit);
        if (!exitSeg) continue;
        const exitBoundary = validateExitBoundary(blocks, exit);
        if (!exitBoundary.ok) continue;
        parts.push(exitSeg);

        const fullRoute = combinePaths(parts);
        if (!EXIT_BLOCKS.has(fullRoute[fullRoute.length - 1])) continue;

        const pl = evaluatePlan(blocks, fullRoute, order);
        if (pl.valid) plans.push(pl);
      }
    }
  }

  plans.sort((a, b) => {
    if (planningMode === "practical") {
      if (a.waitDropActions !== b.waitDropActions) return a.waitDropActions - b.waitDropActions;
      if (a.ops !== b.ops) return a.ops - b.ops;
    }
    return a.score - b.score;
  });

  const unique = [];
  const seen = new Set();
  for (const p of plans) {
    const key = `${p.route.join("-")}|${p.pickups.join(",")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(p);
  }

  // If there are valid 2-scroll plans, only show those first.
  const twoScroll = unique.filter((p) => p.pickups.length === 2);
  if (twoScroll.length > 0) return twoScroll.slice(0, topN);
  return unique.slice(0, topN);
}

function minHopDistance(start, goalNodes) {
  if (goalNodes.includes(start)) return 0;
  const q = [{ node: start, d: 0 }];
  const visited = new Set([start]);
  while (q.length > 0) {
    const cur = q.shift();
    for (const nb of getNeighbors(cur.node)) {
      if (visited.has(nb)) continue;
      if (goalNodes.includes(nb)) return cur.d + 1;
      visited.add(nb);
      q.push({ node: nb, d: cur.d + 1 });
    }
  }
  return 99;
}

function randomScenarioBlocks() {
  const blocks = createDefaultBlocks();
  for (const b of blocks) {
    b.token = "EMPTY";
  }

  const ids = blocks.map((b) => b.id);
  shuffle(ids);

  ids.slice(0, 4).forEach((id) => {
    getBlock(blocks, id).token = "R2";
  });

  const remaining = ids.filter((id) => getBlock(blocks, id).token === "EMPTY");
  const r1Candidates = remaining.filter((id) => !FORBIDDEN_R1_BLOCKS.has(id));
  r1Candidates.slice(0, 3).forEach((id) => {
    getBlock(blocks, id).token = "R1";
  });

  const remainingAfterR1 = ids.filter((id) => getBlock(blocks, id).token === "EMPTY");
  const fakeCandidates = remainingAfterR1.filter((id) => ![1, 2, 3].includes(id));
  if (fakeCandidates.length > 0) {
    getBlock(blocks, fakeCandidates[0]).token = "FAKE";
  }

  return blocks;
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

function renderMap(containerId, blocks, path = [], robotNode = null, onClick = null) {
  const root = document.getElementById(containerId);
  root.innerHTML = "";

  blocks.forEach((b) => {
    const stepIdx = path.indexOf(b.id);
    const el = document.createElement("div");
    el.className = "block";
    if (path.includes(b.id)) el.classList.add("path");
    if (path.length > 0 && !path.includes(b.id)) el.classList.add("dimmed");
    if (stepIdx === 0) el.classList.add("path-start");
    if (stepIdx === path.length - 1 && stepIdx >= 0) el.classList.add("path-end");
    if (robotNode === b.id) el.classList.add("robot");

    el.style.background = blockBgByHeight(b.h);
    el.innerHTML = `
      <div class="block-id">#${b.id}${ENTRANCE_LINKS.includes(b.id) ? " (Ent)" : ""}${EXIT_BLOCKS.has(b.id) ? " (Exit)" : ""}</div>
      <div class="block-h">H=${b.h}mm</div>
      <div class="block-kfs ${tokenClass(b.token)}">${b.token}</div>
      ${stepIdx >= 0 ? `<div class="path-step">${stepIdx + 1}</div>` : ""}
    `;

    if (typeof onClick === "function") {
      el.addEventListener("click", () => onClick(b.id));
    }

    root.appendChild(el);
  });
}

function renderPlans(containerId, plans, onSelect, selectedPlan) {
  const root = document.getElementById(containerId);
  root.innerHTML = "";
  if (!plans.length) {
    root.innerHTML = '<p class="small">No valid plans found.</p>';
    return;
  }

  plans.forEach((p, idx) => {
    const card = document.createElement("div");
    card.className = "plan-card";
    if (selectedPlan && selectedPlan.route.join("-") === p.route.join("-")) {
      card.classList.add("selected");
    }
    const pickupText = p.pickups.length ? p.pickups.join(", ") : "-";
    const waitDropText = `${p.waitDropActions} (penalty ${p.waitDropPenalty})`;
    card.innerHTML = `
      <div class="plan-head">
        <div><strong>#${idx + 1}</strong> ${p.scenarioLabel ? `(${p.scenarioLabel})` : ""}</div>
        <div class="score-pill">Score ${p.score}</div>
      </div>
      <div class="small key">Route</div>
      <div class="small">E → ${p.route.join(" → ")}</div>
      <div class="small"><strong>Pickup:</strong> ${pickupText} | <strong>Exit:</strong> ${p.exit}</div>
      <div class="small"><strong>Steps:</strong> ${p.steps} | <strong>Climb:</strong> ${p.climb}mm | <strong>Time:</strong> ${p.time}s | <strong>Risk:</strong> ${p.risk}</div>
      <div class="small key">Actions</div>
      <div class="small">Total ${p.ops} = move/climb ${p.climbActions + p.descendActions + p.terrainActions} + pickup ${p.pickupActions} + drop ${p.dropActions} + wait ${p.waitActions}</div>
      <div class="small warn"><strong>Wait+Drop:</strong> ${waitDropText}</div>
      <div class="small">R1 avoid: touch ${p.r1TouchCount}, near ${p.r1NearCount}, proximity ${p.r1ProximityCost}, 1-scroll penalty ${p.oneScrollPenalty}</div>
      <div class="small">Policy: middle-drop ${p.policyDropActions}, policy penalty ${p.policyPenalty}</div>
      <div class="small">Strategic: exit bonus ${p.strategicExitPoints}, exit-pickup bonus ${p.exitPickupPoints}, missed-exit-pick penalty ${p.missedExitPickupPenalty}</div>
    `;
    card.addEventListener("click", () => onSelect(p));
    root.appendChild(card);
  });
}

function setupAutoTab() {
  document.getElementById("auto-run").addEventListener("click", () => {
    const count = Number(document.getElementById("auto-scenarios").value || 30);
    const topN = Number(document.getElementById("auto-topn").value || 5);
    const strict = document.getElementById("auto-strict").checked;

    let allPlans = [];
    let bestScenarioBlocks = null;

    for (let i = 0; i < count; i += 1) {
      const blocks = randomScenarioBlocks();
      const lv = validateLayout(blocks, strict);
      if (!lv.ok) continue;

      const plans = computePlans(blocks, topN);
      plans.forEach((p) => {
        p.scenarioLabel = `S${i + 1}`;
        p._blocks = cloneBlocks(blocks);
      });
      allPlans = allPlans.concat(plans);
    }

    allPlans.sort((a, b) => a.score - b.score);
    autoState.plans = allPlans.slice(0, topN);
    autoState.selectedPlan = autoState.plans[0] || null;

    if (autoState.selectedPlan) {
      bestScenarioBlocks = cloneBlocks(autoState.selectedPlan._blocks);
      autoState.blocks = bestScenarioBlocks;
    }

    document.getElementById("auto-summary").innerHTML = autoState.selectedPlan
      ? `<span class="good">Best score: ${autoState.selectedPlan.score}</span> | Scenario ${autoState.selectedPlan.scenarioLabel} | Route E → ${autoState.selectedPlan.route.join(" → ")}`
      : '<span class="bad">No valid plans found for generated scenarios.</span>';

    renderPlans("auto-results", autoState.plans, (plan) => {
      autoState.selectedPlan = plan;
      autoState.blocks = cloneBlocks(plan._blocks);
      renderAuto();
    }, autoState.selectedPlan);

    renderAuto();
  });

  document.getElementById("auto-simulate").addEventListener("click", () => {
    simulatePath("auto-map", autoState.blocks, autoState.selectedPlan);
  });
}

function setupManualTab() {
  document.getElementById("manual-validate").addEventListener("click", () => {
    const strict = document.getElementById("manual-strict").checked;
    const lv = validateLayout(manualState.blocks, strict);
    const cls = lv.ok ? "good" : "bad";
    const lines = [
      `<span class="${cls}">${lv.ok ? "Layout valid" : "Layout invalid"}</span>`,
      `R2=${lv.counts.R2}, R1=${lv.counts.R1}, Fake=${lv.counts.FAKE}`,
    ];
    if (!lv.ok) {
      lines.push(...lv.errors);
    }
    document.getElementById("manual-validation").innerHTML = lines.map((x) => `<div>${x}</div>`).join("");
  });

  document.getElementById("manual-plan").addEventListener("click", () => {
    const strict = document.getElementById("manual-strict").checked;
    const topN = Number(document.getElementById("manual-topn").value || 5);
    const lv = validateLayout(manualState.blocks, strict);
    if (!lv.ok) {
      document.getElementById("manual-validation").innerHTML = `<div class="bad">${lv.errors.join("<br />")}</div>`;
      manualState.plans = [];
      manualState.selectedPlan = null;
      renderManual();
      return;
    }

    manualState.plans = computePlans(manualState.blocks, topN);
    manualState.selectedPlan = manualState.plans[0] || null;

    renderPlans("manual-results", manualState.plans, (plan) => {
      manualState.selectedPlan = plan;
      renderManual();
    }, manualState.selectedPlan);

    document.getElementById("manual-validation").innerHTML = manualState.selectedPlan
      ? `<div class="good">Computed ${manualState.plans.length} plan(s). Best score: ${manualState.selectedPlan.score}</div>`
      : `<div class="bad">No valid path found for this layout.</div>`;

    renderManual();
  });

  document.getElementById("manual-reset").addEventListener("click", () => {
    manualState.blocks = createDefaultBlocks();
    manualState.plans = [];
    manualState.selectedPlan = null;
    document.getElementById("manual-results").innerHTML = "";
    document.getElementById("manual-validation").innerHTML = "";
    renderManual();
  });

  document.getElementById("manual-simulate").addEventListener("click", () => {
    simulatePath("manual-map", manualState.blocks, manualState.selectedPlan, true);
  });
}

function getSelectedTool() {
  const el = document.querySelector('input[name="place-tool"]:checked');
  return el ? el.value : "EMPTY";
}

function renderAuto() {
  const path = autoState.selectedPlan ? autoState.selectedPlan.route : [];
  renderMap("auto-map", autoState.blocks, path, null, null);
  renderPlans("auto-results", autoState.plans, (plan) => {
    autoState.selectedPlan = plan;
    autoState.blocks = cloneBlocks(plan._blocks);
    renderAuto();
  }, autoState.selectedPlan);
}

function renderManual() {
  const path = manualState.selectedPlan ? manualState.selectedPlan.route : [];
  renderMap(
    "manual-map",
    manualState.blocks,
    path,
    null,
    (id) => {
      const tool = getSelectedTool();
      getBlock(manualState.blocks, id).token = tool;
      renderManual();
    },
  );
  renderPlans("manual-results", manualState.plans, (plan) => {
    manualState.selectedPlan = plan;
    renderManual();
  }, manualState.selectedPlan);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function simulatePath(mapId, blocks, plan, editable = false) {
  if (!plan) return;
  for (const node of plan.route) {
    renderMap(
      mapId,
      blocks,
      plan.route,
      node,
      editable
        ? (id) => {
            const tool = getSelectedTool();
            getBlock(manualState.blocks, id).token = tool;
            renderManual();
          }
        : null,
    );
    await sleep(380);
  }
  if (editable) {
    renderManual();
  } else {
    renderAuto();
  }
}

function seedManualDefault() {
  const b = manualState.blocks;
  getBlock(b, 1).token = "R2";
  getBlock(b, 3).token = "R2";
  getBlock(b, 6).token = "R2";
  getBlock(b, 11).token = "R2";
  getBlock(b, 2).token = "R1";
  getBlock(b, 4).token = "R1";
  getBlock(b, 8).token = "R1";
  getBlock(b, 12).token = "FAKE";
}

function init() {
  setupTabs();
  setupAutoTab();
  setupManualTab();
  seedManualDefault();
  renderAuto();
  renderManual();
}

init();
