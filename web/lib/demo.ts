/** Scripted ~40 s NexState replay that flows through the same throttled
 * commit path as live SSE. Deterministic — every playback is identical. */

import type {
  Bucket,
  CurrentState,
  HistoryRecord,
  Ledger,
  LogEntry,
  LogKind,
  NexusState,
  Step,
} from "./types";
import { DEMO_SHOTS } from "./demoShots";

const RUN_ID = "5eed1a7";
const GOAL =
  "Find the three most popular wireless headphones on Flipkart (sorted by popularity), compare price, ratings and battery life, and recommend the best buy.";

const STEP_SEARCH: Step = {
  instruction: "Open Flipkart, search 'wireless headphones' and confirm the results grid loads.",
  expected_outcome: "Search results for wireless headphones visible with the total item count.",
};
const STEP_SORT: Step = {
  instruction:
    "Sort the wireless headphone results by Popularity and capture the top three organic products: exact title, price and absolute product URL for each, using get_page_text with include_links: true.",
  expected_outcome: "URL contains sort=popularity and three products with prices and URLs are recorded.",
};
const STEP_REVIEWS_A: Step = {
  instruction:
    "Navigate directly to https://www.flipkart.com/leaf-bass-bluetooth-headset/product-reviews and record the total rating count plus two verbatim review quotes.",
  expected_outcome: "Rating count and review text visible on the Leaf Bass product-reviews page.",
};
const STEP_REVIEWS_B: Step = {
  instruction:
    "Open the https://www.flipkart.com/zebronics-zeb-thunder/product-reviews page and record the total rating count plus one verbatim review quote.",
  expected_outcome: "Rating count and review text visible on the Zeb-Thunder product-reviews page.",
};
const STEP_RECHECK: Step = {
  instruction:
    "Recheck the battery-life and discount badges on all three captured product pages and confirm prices are unchanged.",
  expected_outcome: "Battery figure and current offer price re-verified on each of the three product pages.",
};

const URL_SEARCH = "https://www.flipkart.com/search?q=wireless+headphones";
const URL_SORTED = "https://www.flipkart.com/search?q=wireless+headphones&sort=popularity";
const URL_REVIEWS_A = "https://www.flipkart.com/leaf-bass-bluetooth-headset/product-reviews";
const URL_REVIEWS_B = "https://www.flipkart.com/zebronics-zeb-thunder/product-reviews";
const URL_ZEB = "https://www.flipkart.com/zebronics-zeb-thunder/p/itmzebth02";
const URL_TREAD = "https://www.flipkart.com/treadmill-headphone/p/itmtread03";

interface Deltas {
  cloudCalls?: number;
  cloudIn?: number;
  cloudOut?: number;
  cloudBytes?: number;
  cloudImages?: number;
  openCalls?: number;
  openIn?: number;
  openOut?: number;
  openBytes?: number;
  openImages?: number;
}

export function runDemo(
  commit: (next: NexusState) => void,
  cancelled: () => boolean
): void {
  const timers: number[] = [];
  const at = (seconds: number, fn: () => void): void => {
    timers.push(
      window.setTimeout(() => {
        if (!cancelled()) fn();
      }, seconds * 1000)
    );
  };

  let d: NexusState = {
    goal: "",
    run_id: "",
    status: "starting",
    outcome: "",
    thought: "",
    plan: [],
    history: [],
    evidences: [],
    current: {},
    log: [],
    report: "",
    report_path: "",
  };

  let clock = 9 * 3600 + 41 * 60 + 2;
  const history: HistoryRecord[] = [];

  const cloud: Bucket = { calls: 0, prompt_tokens: 0, completion_tokens: 0, bytes_out: 0, images_out: 0 };
  const open: Bucket = { calls: 0, prompt_tokens: 0, completion_tokens: 0, bytes_out: 0, images_out: 0 };
  let plannerCalls = 0;

  const ledger = (): Ledger => {
    const openTokens = open.prompt_tokens + open.completion_tokens;
    const cloudTokens = cloud.prompt_tokens + cloud.completion_tokens;
    const total = openTokens + cloudTokens;
    return {
      cloud: { ...cloud },
      open: { ...open },
      by_role: {
        planner: { ...cloud },
        executor: { ...open },
        verifier: { ...open },
        reporter: { ...cloud },
      },
      planner_calls: plannerCalls,
      open_token_share: total > 0 ? round(openTokens / total, 4) : 0,
    };
  };

  const pushLog = (kind: LogKind, text: string, stepSeconds = 1.4): void => {
    clock += Math.round(stepSeconds);
    const entry: LogEntry = { t: fmtClock(clock), kind, text };
    d = { ...d, log: [...d.log, entry] };
  };

  const snap = (): void => {
    if (cancelled()) return;
    commit({
      ...d,
      plan: d.plan.map((s) => ({ ...s })),
      history: [...history],
      evidences: d.evidences.map((e) => ({ ...e })),
      current: { ...d.current },
      log: [...d.log],
      ledger: ledger(),
    });
  };

  const bump = (delta: Deltas): void => {
    if (delta.cloudCalls) cloud.calls += delta.cloudCalls;
    if (delta.cloudIn) cloud.prompt_tokens += delta.cloudIn;
    if (delta.cloudOut) cloud.completion_tokens += delta.cloudOut;
    if (delta.cloudBytes) cloud.bytes_out += delta.cloudBytes;
    if (delta.cloudImages) cloud.images_out += delta.cloudImages;
    if (delta.openCalls) open.calls += delta.openCalls;
    if (delta.openIn) open.prompt_tokens += delta.openIn;
    if (delta.openOut) open.completion_tokens += delta.openOut;
    if (delta.openBytes) open.bytes_out += delta.openBytes;
    if (delta.openImages) open.images_out += delta.openImages;
  };

  const shotOf = (n: number): string => DEMO_SHOTS[n - 1];
  const frame = (n: number, url: string, title: string): Partial<CurrentState> => {
    bump({ openCalls: 1, openIn: 2540, openOut: 230, openBytes: 118_400, openImages: 1 });
    return { shot: shotOf(n), url, title, iteration: (d.current.iteration ?? 0) + 1 };
  };

  const action = (name: string, args: string): void => {
    pushLog("action", `${name}(${args})`, 0.9);
    bump({ openCalls: 1, openIn: 2620, openOut: 210 });
    d = { ...d, current: { ...d.current, last_action: `${name}(${args})` } };
  };

  const result = (name: string, text: string): void => {
    pushLog("ok", `${name}: ${text}`, 1.1);
    bump({ openCalls: 1, openIn: 2980, openOut: 60, openBytes: 9400, openImages: 1 });
  };

  const executorReport = (report: string): void => {
    pushLog("action", "Executor reported back", 1.2);
    bump({ openCalls: 1, openIn: 3400, openOut: 340 });
    d = { ...d, current: { ...d.current, report } };
  };

  const evidenceCheck = (okCount: number, failed: number): void => {
    pushLog(failed ? "failed" : "ok", `Evidence check: ${okCount} ok, ${failed} dropped`, 0.7);
  };

  const verify = (
    record: Omit<HistoryRecord, "verdict" | "complete" | "evidences" | "report">,
    partial: {
      verdict: HistoryRecord["verdict"];
      complete?: boolean;
      evidences?: HistoryRecord["evidences"];
      report?: string;
    }
  ): void => {
    const complete = partial.complete ?? partial.verdict === "done";
    const built: HistoryRecord = {
      ...record,
      verdict: partial.verdict,
      complete,
      evidences: partial.evidences ?? [],
      report:
        partial.report ??
        "STATUS: PARTIAL\nCURRENT STATE: see current page.\nDONE: recorded observations.\nINFO: captured evidence appended.",
    };
    history.push(built);
    pushLog(complete ? "ok" : "failed", `Step ${complete ? "verified" : "NOT complete"}: ${built.assessment}`, 1.5);
    if (built.evidences.length) {
      d = { ...d, evidences: [...d.evidences, ...built.evidences.map((e) => ({ ...e }))] };
      bump({ openCalls: 1, openIn: 3150, openOut: 260 });
    } else {
      bump({ openCalls: 1, openIn: 3150, openOut: 220 });
    }
  };

  const plan = (round: number, steps: Step[], thought: string, kind: LogKind = "plan"): void => {
    plannerCalls = Math.max(plannerCalls, round);
    bump({ cloudCalls: 1, cloudIn: 1520 + round * 380, cloudOut: 280, cloudBytes: 6200 });
    d = {
      ...d,
      status: "running",
      thought,
      plan: steps.map((s) => ({ ...s })),
      current: { ...d.current, instruction: steps[0]?.instruction },
    };
    pushLog(kind, `Round ${round}: continue, ${steps.length} step(s) planned. ${thought}`, 1);
  };

  // ---- 00.0 empty boot ----------------------------------------------------
  at(0.15, snap);

  // ---- 00.4 run + first plan ---------------------------------------------
  at(0.4, () => {
    d = { ...d, goal: GOAL, run_id: RUN_ID, status: "running" };
    pushLog("plan", `Run ${RUN_ID} started`, 0);
    snap();
  });
  at(1.1, () => {
    plan(
      1,
      [STEP_SEARCH, STEP_SORT, STEP_REVIEWS_A, STEP_REVIEWS_B, STEP_RECHECK],
      "Fresh navigation; begin with a direct search on Flipkart."
    );
    snap();
  });

  // ---- Step 1: search -----------------------------------------------------
  at(2.2, () => {
    action("type_text", '{"index": 10, "text": "wireless headphones", "submit": true}');
    snap();
  });
  at(2.8, () => {
    result("type_text", "Typed 19 characters into element 10 and pressed Enter.");
    d = { ...d, current: { ...d.current, ...frame(1, URL_SEARCH, "Headphones - Flipkart.com") } };
    snap();
  });
  at(3.6, () => {
    action("get_page_text", '{"include_links": true}');
    snap();
  });
  at(4.1, () => {
    result("get_page_text", "Characters 0-1,506 of 4,211 (links appended).");
    d = { ...d, current: { ...d.current, ...frame(1, URL_SEARCH, "Headphones - Flipkart.com") } };
    snap();
  });
  at(4.8, () => {
    action("extract", '{"fields": ["item count", "URL"]}');
    snap();
  });
  at(5.2, () => {
    executorReport(
      "STATUS: SUCCESS\nCURRENT STATE: Results grid for wireless headphones.\nDONE: Searched Flipkart and loaded the results grid.\nINFO: 152,742 items found for 'wireless headphones'; results grid fully rendered."
    );
    snap();
  });
  at(5.6, () => {
    verify(
      {
        instruction: STEP_SEARCH.instruction,
        expected_outcome: STEP_SEARCH.expected_outcome,
        assessment: "Results grid confirmed: 152,742 items found for 'wireless headphones'.",
        url: URL_SEARCH,
        shot: shotOf(1),
      },
      {
        verdict: "done",
        report:
          "STATUS: SUCCESS\nCURRENT STATE: Results grid for wireless headphones.\nDONE: Searched Flipkart and loaded the results grid.\nINFO: 152,742 items found for 'wireless headphones'; results grid fully rendered.",
        evidences: [
          {
            id: "E1",
            url: URL_SEARCH,
            original_text: "Headphones | Wireless - 152,742 items found for 'wireless headphones'",
            summarized: "The search returned 152,742 wireless headphone listings on Flipkart.",
            shot: shotOf(1),
          },
        ],
      }
    );
    evidenceCheck(1, 0);
    d = { ...d, current: { ...d.current, instruction: STEP_SORT.instruction, report: undefined } };
    snap();
  });

  // ---- Step 2: popularity sort (one retry) --------------------------------
  at(6.6, () => {
    action('click', '{"index": 43}');
    snap();
  });
  at(7.1, () => {
    pushLog("error", "click: Clicked element 43. Results order unchanged; active sort stayed Relevance.", 1.1);
    bump({ openCalls: 1, openIn: 2760, openOut: 190 });
    d = { ...d, current: { ...d.current, ...frame(2, URL_SEARCH, "Headphones - Flipkart.com") } };
    snap();
  });
  at(7.7, () => {
    executorReport(
      "STATUS: PARTIAL\nCURRENT STATE: Results page, sort untouched.\nDONE: Clicked the Popularity sort chip (element 43).\nINFO: Click produced no state change; active sort still shows Relevance."
    );
    snap();
  });
  at(8.1, () => {
    verify(
      {
        instruction: STEP_SORT.instruction,
        expected_outcome: STEP_SORT.expected_outcome,
        assessment:
          "Clicking the sort chip did not change the order: the URL is unchanged and the active sort still reads Relevance. Navigate directly to the URL with sort=popularity.",
        url: URL_SEARCH,
        shot: shotOf(2),
      },
      { verdict: "retry" }
    );
    d = { ...d, current: { ...d.current, report: undefined } };
    snap();
  });
  at(9.1, () => {
    action(
      "navigate",
      '{"url": "https://www.flipkart.com/search?q=wireless+headphones&sort=popularity"}'
    );
    snap();
  });
  at(9.6, () => {
    result("navigate", `Navigated to ${URL_SORTED} (HTTP 200).`);
    d = { ...d, current: { ...d.current, ...frame(2, URL_SORTED, "Headphones - Flipkart.com | Popularity") } };
    snap();
  });
  at(10.4, () => {
    action("get_page_text", '{"include_links": true}');
    snap();
  });
  at(10.9, () => {
    result("get_page_text", "Characters 0-2,204 of 5,937 (3 product URLs captured).");
    d = { ...d, current: { ...d.current, ...frame(2, URL_SORTED, "Headphones - Flipkart.com | Popularity") } };
    snap();
  });
  at(11.6, () => {
    executorReport(
      "STATUS: SUCCESS\nCURRENT STATE: Sorted results page.\nDONE: Applied popularity sort via direct URL; captured top three organic products.\nINFO: Leaf Bass ₹799 · Zeb-Thunder ₹999 · Treadmill ₹361 with absolute product URLs recorded."
    );
    snap();
  });
  at(12.0, () => {
    verify(
      {
        instruction: STEP_SORT.instruction,
        expected_outcome: STEP_SORT.expected_outcome,
        assessment: "Sorted list captured: three products with titles, prices and absolute URLs.",
        url: URL_SORTED,
        shot: shotOf(2),
      },
      {
        verdict: "done",
        report:
          "STATUS: SUCCESS\nCURRENT STATE: Sorted results page.\nDONE: Applied popularity sort via direct URL; captured top three organic products.\nINFO: Leaf Bass ₹799 · Zeb-Thunder ₹999 · Treadmill ₹361 with absolute product URLs recorded.",
        evidences: [
          {
            id: "E2",
            url: URL_SORTED,
            original_text:
              "Leaf Bass Bluetooth Headset (Black, On the Ear) ₹799 63% off 4.2 12,846 Ratings\nZEBRONICS Zeb-Thunder Wireless Bluetooth Over The Ear Headphone with ENC Mic (Black) ₹999 47% off 4.1 84,187 Ratings\nTreadmill SPORTS RUNNING HEADPHPONE (White, In the Ear) ₹361 71% off 3.8 36 Ratings",
            summarized:
              "Top three by popularity: Leaf Bass ₹799 (4.2★, 12,846 ratings), Zeb-Thunder ₹999 (4.1★, 84,187 ratings), Treadmill ₹361 (3.8★, 36 ratings).",
            shot: shotOf(2),
          },
        ],
      }
    );
    evidenceCheck(1, 0);
    d = {
      ...d,
      current: { ...d.current, instruction: STEP_REVIEWS_A.instruction, report: undefined },
    };
    snap();
  });

  // ---- Round 2: replan for reviews pages ----------------------------------
  at(13.0, () => {
    plan(
      2,
      [STEP_REVIEWS_A, STEP_REVIEWS_B, STEP_RECHECK],
      "Reviews live on a dedicated /product-reviews/ sub-page; navigate directly instead of in-page click.",
      "plan"
    );
    snap();
  });

  // ---- Step 3: Leaf Bass reviews ------------------------------------------
  at(14.1, () => {
    action("navigate", `{"url": "${URL_REVIEWS_A}"}`);
    snap();
  });
  at(14.6, () => {
    result("navigate", `Navigated to ${URL_REVIEWS_A} (HTTP 200).`);
    d = { ...d, current: { ...d.current, ...frame(3, URL_REVIEWS_A, "Leaf Bass Bluetooth Headset Reviews") } };
    snap();
  });
  at(15.4, () => {
    action("get_page_text", '{"index": null, "start": 0}');
    snap();
  });
  at(15.9, () => {
    result("get_page_text", "Characters 0-1,977 of 6,486.");
    d = { ...d, current: { ...d.current, ...frame(3, URL_REVIEWS_A, "Leaf Bass Bluetooth Headset Reviews") } };
    snap();
  });
  at(16.6, () => {
    executorReport(
      "STATUS: SUCCESS\nCURRENT STATE: Leaf Bass product-reviews page.\nDONE: Opened the dedicated reviews page and recorded counts plus two verbatim quotes.\nINFO: 12,846 ratings; quotes recorded verbatim."
    );
    snap();
  });
  at(17.0, () => {
    verify(
      {
        instruction: STEP_REVIEWS_A.instruction,
        expected_outcome: STEP_REVIEWS_A.expected_outcome,
        assessment: "Reviews page loaded; counts and both quotes present verbatim.",
        url: URL_REVIEWS_A,
        shot: shotOf(3),
      },
      {
        verdict: "done",
        report:
          "STATUS: SUCCESS\nCURRENT STATE: Leaf Bass product-reviews page.\nDONE: Opened the dedicated reviews page and recorded counts plus two verbatim quotes.\nINFO: 12,846 ratings; quotes recorded verbatim.",
        evidences: [
          {
            id: "E3",
            url: URL_REVIEWS_A,
            original_text: "12,846 Ratings & 5,142 Reviews for Leaf Bass Bluetooth Headset",
            summarized: "12,846 ratings on the Leaf Bass reviews page — a large sample.",
            shot: shotOf(3),
          },
          {
            id: "E4",
            url: URL_REVIEWS_A,
            original_text: "Battery life is seriously good - managed two full days of calls before charging",
            summarized: "Reviewers confirm real-world battery life well beyond one day.",
            shot: shotOf(3),
          },
          {
            id: "E5",
            url: URL_REVIEWS_A,
            original_text: "Sound is clear for the price, bass is acceptable and the controls are easy",
            summarized: "Reviews note clear sound at the price point with usable controls.",
            shot: shotOf(3),
          },
        ],
      }
    );
    evidenceCheck(3, 1);
    d = { ...d, current: { ...d.current, instruction: STEP_REVIEWS_B.instruction, report: undefined } };
    snap();
  });

  // ---- Step 4: Zeb-Thunder reviews ----------------------------------------
  at(18.0, () => {
    action("navigate", `{"url": "${URL_REVIEWS_B}"}`);
    snap();
  });
  at(18.5, () => {
    result("navigate", `Navigated to ${URL_REVIEWS_B} (HTTP 200).`);
    d = { ...d, current: { ...d.current, ...frame(4, URL_REVIEWS_B, "Zeb-Thunder Wireless Headphones Reviews") } };
    snap();
  });
  at(19.3, () => {
    action("get_page_text", '{"index": null, "start": 0}');
    snap();
  });
  at(19.8, () => {
    result("get_page_text", "Characters 0-1,804 of 9,245.");
    d = { ...d, current: { ...d.current, ...frame(4, URL_REVIEWS_B, "Zeb-Thunder Wireless Headphones Reviews") } };
    snap();
  });
  at(20.5, () => {
    executorReport(
      "STATUS: SUCCESS\nCURRENT STATE: Zeb-Thunder product-reviews page.\nDONE: Opened the dedicated reviews page and captured counts plus a verbatim quote.\nINFO: 84,187 ratings with 9,402 written reviews."
    );
    snap();
  });
  at(20.9, () => {
    verify(
      {
        instruction: STEP_REVIEWS_B.instruction,
        expected_outcome: STEP_REVIEWS_B.expected_outcome,
        assessment: "Reviews page loaded; count and quote verified verbatim.",
        url: URL_REVIEWS_B,
        shot: shotOf(4),
      },
      {
        verdict: "done",
        report:
          "STATUS: SUCCESS\nCURRENT STATE: Zeb-Thunder product-reviews page.\nDONE: Opened the dedicated reviews page and captured counts plus a verbatim quote.\nINFO: 84,187 ratings with 9,402 written reviews.",
        evidences: [
          {
            id: "E6",
            url: URL_REVIEWS_B,
            original_text: "84,187 Ratings & 9,402 Reviews for Zeb-Thunder Wireless Bluetooth Headphone",
            summarized: "84,187 ratings on the Zeb-Thunder reviews page — the largest sample.",
            shot: shotOf(4),
          },
          {
            id: "E7",
            url: URL_REVIEWS_B,
            original_text: "Battery claim by my count is closer to 40 hours than the advertised 60 hours",
            summarized: "A reviewer counts real battery closer to 40 h vs the advertised 60 h.",
            shot: shotOf(4),
          },
        ],
      }
    );
    evidenceCheck(2, 0);
    d = { ...d, current: { ...d.current, instruction: STEP_RECHECK.instruction, report: undefined } };
    snap();
  });

  // ---- Step 5: battery + price recheck ------------------------------------
  at(21.9, () => {
    action("navigate", `{"url": "${URL_ZEB}"}`);
    snap();
  });
  at(22.4, () => {
    result("navigate", `Navigated to product page (HTTP 200).`);
    d = { ...d, current: { ...d.current, ...frame(5, URL_ZEB, "ZEBRONICS Zeb-Thunder") } };
    snap();
  });
  at(23.1, () => {
    action("get_page_text", '{"include_links": false}');
    snap();
  });
  at(23.5, () => {
    result("get_page_text", "Battery for Talktime: 60 Hrs line captured.");
    d = { ...d, current: { ...d.current, ...frame(5, URL_ZEB, "ZEBRONICS Zeb-Thunder") } };
    snap();
  });
  at(24.2, () => {
    action("navigate", `{"url": "${URL_TREAD}"}`);
    snap();
  });
  at(24.7, () => {
    result("navigate", "Navigated to product page (HTTP 200).");
    d = { ...d, current: { ...d.current, ...frame(6, URL_TREAD, "Treadmill SPORTS RUNNING HEADPHPONE") } };
    snap();
  });
  at(25.4, () => {
    action("get_page_text", '{"include_links": false}');
    snap();
  });
  at(25.8, () => {
    result("get_page_text", "Battery backup: 8 Hrs line captured; ₹361 confirmed.");
    d = { ...d, current: { ...d.current, ...frame(6, URL_TREAD, "Treadmill SPORTS RUNNING HEADPHPONE") } };
    snap();
  });
  at(26.5, () => {
    executorReport(
      "STATUS: SUCCESS\nCURRENT STATE: Third product page.\nDONE: Rechecked battery and offers on all three pages.\nINFO: Leaf Bass 60 Hrs · Zeb 60 Hrs (ENC mic) · Treadmill 8 Hrs; prices unchanged."
    );
    snap();
  });
  at(26.9, () => {
    verify(
      {
        instruction: STEP_RECHECK.instruction,
        expected_outcome: STEP_RECHECK.expected_outcome,
        assessment: "Battery figures and prices re-verified verbatim on all three product pages.",
        url: URL_TREAD,
        shot: shotOf(6),
      },
      {
        verdict: "done",
        report:
          "STATUS: SUCCESS\nCURRENT STATE: Third product page.\nDONE: Rechecked battery and offers on all three pages.\nINFO: Leaf Bass 60 Hrs · Zeb 60 Hrs (ENC mic) · Treadmill 8 Hrs; prices unchanged.",
        evidences: [
          {
            id: "E8",
            url: URL_ZEB,
            original_text: "Up to 60 Hrs Playback with ENC Mic - 40mm Dynamic Drivers",
            summarized: "Zeb-Thunder spec: 60 h claimed playback with ENC call mic.",
            shot: shotOf(5),
          },
          {
            id: "E9",
            url: URL_TREAD,
            original_text: "₹361 with 71% off - Battery backup: 8 Hrs",
            summarized: "Treadmill unit: ₹361 after 71% off, only 8 h battery.",
            shot: shotOf(6),
          },
        ],
      }
    );
    evidenceCheck(2, 0);
    snap();
  });

  // ---- Round 3: goal achieved, report streams ------------------------------
  at(28.2, () => {
    plannerCalls = 3;
    bump({ cloudCalls: 1, cloudIn: 2860, cloudOut: 240, cloudBytes: 7900 });
    d = {
      ...d,
      status: "goal_achieved",
      plan: [],
      thought: "Every part of the goal has verbatim evidence; hand the final report to the reporter.",
      current: { ...d.current, report: undefined },
    };
    pushLog("plan", "Round 3: goal_achieved, plan complete. Opening the report.", 1);
    snap();
  });
  at(28.8, () => {
    pushLog("plan", "Escalated to the planner: plan_empty", 0.9);
    snap();
  });

  const REPORT =
    "# Best buy among the top three popular wireless headphones\n\n**Recommendation: the Leaf Bass Bluetooth Headset (₹799)** — the highest rating (4.2/5 across 12,846 ratings) at the lowest of the three prices, with 60-hour claimed playback [E2], [E3], [E4].\n\n## The shortlist (sorted by popularity)\n\n| Product | Price | Rating | Battery |\n|---|---|---|---|\n| Leaf Bass Bluetooth Headset | ₹799 · 63% off [E2] | 4.2/5 · 12,846 ratings [E3] | 60 Hrs [E4] |\n| ZEBRONICS Zeb-Thunder, ENC mic | ₹999 · 47% off [E2] | 4.1/5 · 84,187 ratings [E6] | 60 Hrs [E8] |\n| Treadmill SPORTS RUNNING HEADPHPONE | ₹361 · 71% off [E2] | 3.8/5 · 36 ratings | 8 Hrs [E9] |\n\n## Trade-offs\n\n- **Sample size matters.** The Treadmill's 3.8/5 rests on only 36 ratings; treat it as a weak signal compared with the two large samples [E2].\n- **Claimed vs counted battery.** Zeb-Thunder advertises 60 Hrs [E8], but a reviewer counts real-world usage closer to 40 Hrs [E7]; the Leaf Bass reviews independently praise battery life [E4].\n- **Call quality** is an argument for the Zeb only: it is the sole unit with an ENC call microphone at this price [E2], [E8].\n\n## Gaps and caveats\n\n- Quotes were extracted verbatim from the dedicated product-reviews pages [E4], [E5], [E7]; star-distribution and verified-purchase splits were outside the goal.\n- Prices were stable across the recheck step; no stock or discount change was observed [E8], [E9].\n\n## Sources\n\n- Flipkart search, popularity sort — [E1], [E2]\n- Leaf Bass product-reviews — [E3], [E4], [E5]\n- Zeb-Thunder product-reviews and product page — [E6], [E7], [E8]\n- Treadmill product page — [E9]\n";

  const chunks = splitStream(REPORT, 12);
  let streamed = "";

  at(29.3, () => {
    // Reporter (cloud) opens its one call; tokens stream in per chunk below.
    bump({ cloudCalls: 1, cloudIn: 2620, cloudOut: 0, cloudBytes: 8100 });
    d = { ...d, status: "reporting", report_path: `reports/report_${RUN_ID}.md` };
    pushLog("plan", "Writing the final report", 0.4);
    snap();
  });

  chunks.forEach((chunk, i) => {
    at(29.9 + i * 0.75, () => {
      streamed += chunk;
      bump({ cloudOut: chunk.length / 3.6, cloudBytes: chunk.length });
      d = { ...d, status: "reporting", report: streamed };
      snap();
    });
  });

  const endAt = 29.9 + chunks.length * 0.75 + 0.5;
  at(endAt, () => {
    pushLog("ok", `Report saved to reports/report_${RUN_ID}.md`, 1);
    d = { ...d, status: "goal_achieved", outcome: "goal_achieved" };
    snap();
  });
  at(endAt + 0.9, () => {
    pushLog("ok", `Finished · goal_achieved in ${Math.round(endAt)}s`, 0.8);
    snap();
  });

  // Safety: timers stay pending until they fire; cancelled() guards every
  // callback, so a torn-down store simply drops the remaining frames.
}

function fmtClock(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600) % 24;
  const m = Math.floor(totalSeconds / 60) % 60;
  const s = Math.floor(totalSeconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function round(v: number, digits: number): number {
  const p = 10 ** digits;
  return Math.round(v * p) / p;
}

function splitStream(text: string, pieces: number): string[] {
  const out: string[] = [];
  const approx = Math.ceil(text.length / pieces);
  let start = 0;
  for (let i = 0; i < pieces; i++) {
    const last = i === pieces - 1;
    let end = last ? text.length : Math.min(start + approx, text.length);
    if (!last) {
      // Prefer breaking at a paragraph break near the boundary, but never
      // move `end` past the next chunk's natural region (cursor-based, so
      // chunks stay contiguous: no lost or replayed text).
      const from = Math.max(end - 40, start + 1);
      const nl = text.indexOf("\n\n", from);
      if (nl > start) end = nl + 2;
    }
    out.push(text.slice(start, end));
    start = end;
  }
  return out.filter((c) => c.length > 0);
}
